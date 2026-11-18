# home_kluster

Homelab GitOps : cluster k3s Oracle Cloud piloté par Argo CD.

## Agent skills

### Issue tracker

Les issues vivent dans les GitHub Issues du repo `abugeia/home_kluster`, manipulées
via la CLI `gh`. Voir `docs/agents/issue-tracker.md`.

### Triage labels

Vocabulaire canonique par défaut : `needs-triage`, `needs-info`, `ready-for-agent`,
`ready-for-human`, `wontfix`. Voir `docs/agents/triage-labels.md`.

### Domain docs

Repo single-context : `CONTEXT.md` et `docs/adr/` à la racine, créés à la demande.
Voir `docs/agents/domain.md`.

## Secrets

Source de vérité des secrets en clair : projet bws **`k8s-clusters`** (partagé
avec orarm, plan gratuit limité à 3 projets), entrées préfixées **`HK_`**.

- Une entrée par manifest Secret : clé `HK_<NOM_DU_FICHIER>`, valeur = le YAML
  complet, `note` = `home_kluster/secrets/clear/<fichier>.yaml`.
- Tout nouveau secret va dans bws **avant** d'être scellé ; ne jamais le
  laisser seulement sur un poste (`secrets/clear/` est gitignoré, local).
- Scellement : `secrets/seal_all.sh` (depuis `secrets/clear/`) ou
  `secrets/seal_all.sh --bws` (depuis bws, rien en clair sur disque).
- bw (coffre perso) ne garde que ce qu'un humain saisit : mots de passe
  d'apps, clé privée sealed-secrets.
