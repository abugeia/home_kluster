#!/bin/bash
# Script pour chiffrer tous les secrets YAML du dossier clear avec kubeseal

set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

CERT="${SCRIPT_DIR}/clear/clear/sealed-secrets.pem"
CONTROLLER_NAME="sealed-secrets"
CONTROLLER_NAMESPACE="security"
CLEAR_DIR="${SCRIPT_DIR}/clear"
SEALED_DIR="${SCRIPT_DIR}/sealed"

mkdir -p "$SEALED_DIR"


for file in "$CLEAR_DIR"/*.yaml; do
  name=$(basename "$file")
  out="$SEALED_DIR/${name}"
  if [ -f "$out" ]; then
    echo "[SKIP] $out existe déjà, on saute."
    continue
  fi
  echo "Chiffre $file -> $out"
  kubeseal \
    --controller-name="$CONTROLLER_NAME" \
    --controller-namespace="$CONTROLLER_NAMESPACE" \
    --format=yaml \
    --cert="$CERT" \
    < "$file" > "$out"
done
