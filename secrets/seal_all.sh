#!/bin/bash
# Scelle avec kubeseal les secrets en clair, vers sealed/<fichier>.yaml.
# Un fichier déjà scellé est sauté (supprimer sealed/<fichier> pour le refaire).
#
# Deux sources possibles :
#   ./seal_all.sh            dossier clear/ local (comportement historique)
#   ./seal_all.sh --bws      projet bws `k8s-clusters`, entrées préfixées par
#                            $PREFIX ; le champ `note` porte le chemin d'origine
#                            (<repo>/secrets/clear/<fichier>), qui donne le nom
#                            du fichier scellé. Rien n'est écrit en clair sur disque.
#
# Prérequis --bws : BWS_ACCESS_TOKEN et BWS_SERVER_URL (cf. ~/.bws_infra_token).
# Certificat : $LOCAL_CERT s'il existe, sinon l'entrée bws
# ${PREFIX}_SEALED_SECRETS_CERT.

set -euo pipefail

# --- spécifique au repo -------------------------------------------------------
PREFIX="HK"
LOCAL_CERT_REL="clear/sealed-secrets.pem"
# -----------------------------------------------------------------------------
BWS_PROJECT_ID=1cd86dc3-7991-45ae-b25f-b506001c00be  # k8s-clusters (pas un secret)
CONTROLLER_NAME="sealed-secrets"
CONTROLLER_NAMESPACE="security"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CLEAR_DIR="${SCRIPT_DIR}/clear"
SEALED_DIR="${SCRIPT_DIR}/sealed"
LOCAL_CERT="${SCRIPT_DIR}/${LOCAL_CERT_REL}"

mode=local
case "${1:-}" in
  "") ;;
  --bws) mode=bws ;;
  *) echo "usage: $0 [--bws]" >&2; exit 2 ;;
esac

mkdir -p "$SEALED_DIR"

seal() {  # seal <fichier de sortie> ; secret en clair sur stdin
  kubeseal \
    --controller-name="$CONTROLLER_NAME" \
    --controller-namespace="$CONTROLLER_NAMESPACE" \
    --format=yaml \
    --cert="$CERT" > "$1"
}

if [ "$mode" = local ]; then
  CERT="$LOCAL_CERT"
  for file in "$CLEAR_DIR"/*.yaml; do
    name=$(basename "$file")
    out="$SEALED_DIR/${name}"
    if [ -f "$out" ]; then
      echo "[SKIP] $out existe déjà, on saute."
      continue
    fi
    echo "Chiffre $file -> $out"
    seal "$out" < "$file"
  done
  exit 0
fi

: "${BWS_ACCESS_TOKEN:?absent : bw unlock && chezmoi apply ~/.bws_infra_token}"
secrets=$(bws secret list "$BWS_PROJECT_ID")

tmpcert=""
trap '[ -n "$tmpcert" ] && rm -f "$tmpcert"' EXIT
if [ -f "$LOCAL_CERT" ]; then
  CERT="$LOCAL_CERT"
else
  tmpcert=$(mktemp)
  jq -er --arg k "${PREFIX}_SEALED_SECRETS_CERT" '.[] | select(.key == $k) | .value' \
    <<<"$secrets" > "$tmpcert" \
    || { echo "Certificat introuvable (ni local, ni ${PREFIX}_SEALED_SECRETS_CERT)" >&2; exit 1; }
  CERT="$tmpcert"
fi

# Entrées du préfixe dont la note pointe un .yaml (exclut le cert et les .json).
jq -r --arg p "${PREFIX}_" \
  '.[] | select((.key | startswith($p)) and (.note | endswith(".yaml"))) | .id' \
  <<<"$secrets" | while read -r id; do
  entry=$(jq -c --arg id "$id" '.[] | select(.id == $id)' <<<"$secrets")
  key=$(jq -r .key <<<"$entry")
  name=$(basename "$(jq -r .note <<<"$entry")")
  out="$SEALED_DIR/${name}"
  if [ -f "$out" ]; then
    echo "[SKIP] $out existe déjà, on saute."
    continue
  fi
  echo "Chiffre bws:$key -> $out"
  jq -r .value <<<"$entry" | seal "$out"
done
