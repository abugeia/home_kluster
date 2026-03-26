# Suppression des PVCs ARK: Survival Evolved

> L'app ArgoCD `ark` a été désactivée (renommée en `ark.yaml.off`).
> Les PVCs sont conservés pour l'instant. Voici la procédure de nettoyage quand tu seras prêt.

## PVCs à supprimer

| Nom | Taille | Contenu |
|-----|--------|---------|
| `ark-data-pvc` | 60 Gi | Fichiers serveur ASE, SteamCMD, configs Goldberg |
| `ark-backups-pvc` | 20 Gi | Backups arkmanager |
| `ark-filebrowser-config` | 1 Gi | Base de données filebrowser |

## Procédure

```bash
# 1. Vérifier que les deployments ARK sont bien supprimés
kubectl get deployments -n games | grep ark
# Aucun résultat attendu (ArgoCD a pruné les resources)

# 2. Vérifier l'état des PVCs
kubectl get pvc -n games | grep ark

# 3. Supprimer les PVCs (IRRÉVERSIBLE)
kubectl delete pvc ark-data-pvc -n games
kubectl delete pvc ark-backups-pvc -n games
kubectl delete pvc ark-filebrowser-config -n games

# 4. Vérifier que les PV associés sont aussi libérés
kubectl get pv | grep ark
# Si le reclaim policy est "Retain", supprimer manuellement :
# kubectl delete pv <nom-du-pv>
```

## Vérification NFS

Les PVCs utilisent `storageClassName: nfs-csi-nvme`. Après suppression, vérifier que l'espace est libéré sur le NAS/NVMe :
```bash
# Sur le noeud NFS ou via kubectl exec dans le pod nfs-csi
df -h | grep nvme
```
