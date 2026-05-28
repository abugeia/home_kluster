# Dashboards Grafana

## Dashboards maison (versionnés en GitOps)

Gérés ici via `kustomization.yaml` → ConfigMap labelisé `grafana_dashboard=1`
→ chargé par le sidecar Grafana. Édition possible dans l'UI pour itérer,
mais le sidecar réimpose la version git au prochain sync (donc on commit
le JSON exporté pour pérenniser).

| Fichier | UID | Contenu |
|---|---|---|
| `homelab-power-env.json` | `homelab-power-env` | Conso/état RTX 5070 Ti (PVE host / ai-gaming / windows-11) + onduleur NUT + capteurs température/humidité pi0 |

### Workflow d'ajout / édition

1. Éditer ou créer le dashboard dans l'UI Grafana
2. Export : *Dashboard settings → JSON Model* (garde l'`uid`) → copier dans un `.json` ici
3. Ajouter une entry `configMapGenerator` dans `kustomization.yaml`
4. Commit + push → ArgoCD sync → sidecar charge sous ~30s

## Dashboards communautaires (NON versionnés — import manuel UI)

Ces modèles sont maintenus en amont sur grafana.com. On ne les fige PAS
en JSON ici (on perdrait les updates upstream et ça pollue le repo de
plusieurs centaines de Ko de JSON tiers). Ils restent importés
manuellement via l'UI Grafana (*Dashboards → New → Import → par ID*).

| Dashboard | ID grafana.com | Note |
|---|---|---|
| Node Exporter Full | `1860` | LE dashboard node_exporter de référence |
| K8S Dashboard | _à compléter_ | monitoring cluster k3s |
| Garage | _à compléter_ | stockage objet Garage |
| PostgreSQL Database | _à compléter_ | postgres_exporter |

> Les panels custom NUT/capteurs qui avaient été ajoutés au dashboard
> "K8S Dashboard" ont été **déplacés** vers `homelab-power-env.json`
> (dashboard maison), pour laisser le modèle K8S communautaire vanilla
> (réimportable proprement par ID sans perdre nos ajouts).

## Datasource

Les dashboards maison référencent VictoriaMetrics via la variable de
templating `${DS_VICTORIAMETRICS}` (type `prometheus`). La datasource
est provisionnée par le chart Grafana (`apps/tools/grafana/values.yaml`).

> TODO robustesse : fixer un `uid` stable sur la datasource VictoriaMetrics
> dans values.yaml (actuellement uid auto-généré `P4169E866C3094E38`).
> Sans ça, si Grafana/la datasource est recréé, l'uid change et les
> dashboards référençant l'ancien uid en dur cassent.
