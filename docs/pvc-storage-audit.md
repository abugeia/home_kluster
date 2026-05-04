# Audit des PVCs — StorageClass & Recommandations

## Contexte

Le cluster k3s tourne sur **une seule VM** (`ubuntu-srv-k3s-prod`, 10.0.0.11) hébergée sur le host Proxmox `pve1` (10.0.0.10), qui est aussi le serveur NFS.  
Tout accès NFS = aller-retour réseau virtuel sur le même host physique.

**Règle de base :**
- `local-path` → PVCs petites, write-intensives, non partagées (configs, DBs)
- `nfs-csi-nvme` → PVCs de taille moyenne nécessitant un accès cross-pod (rare)
- `nfs-csi-hdd` → Gros volumes partagés (médias, photos)

---

## Audit complet

| PVC | Namespace | Taille | StorageClass actuelle | Recommandation | Raison |
|-----|-----------|--------|-----------------------|----------------|--------|
| `syncthing-config` | media | 50Mi | ~~nfs-csi-nvme~~ → **local-path** | ✅ Migré | Config app + DB — `permission denied` récurrents |
| `asa-shootergame-pvc-local` | games | 10Gi | **local-path** | ✅ OK | Saves de jeu write-intensives |
| `tinyauth-pvc` | security | 1Gi | *(défaut : local-path)* | ✅ OK | Pas de storageClass explicite = local-path k3s |
| `pocketid-data` | security | 1Gi | *(défaut : local-path)* | ✅ OK | Idem |
| `filebrowser-config` | media | 100Mi | nfs-csi-nvme | 🔴 → **local-path** | SQLite DB, un seul pod, write fréquent |
| `navidrome-data` | media | 1Gi | nfs-csi-nvme | 🔴 → **local-path** | SQLite DB + metadata, un seul pod |
| `jellyfin-config` | media | 1Gi | nfs-csi-nvme | 🔴 → **local-path** | Config + metadata DB Jellyfin, un seul pod |
| `metube-state` | media | 100Mi | nfs-csi-nvme | 🔴 → **local-path** | État des téléchargements, un seul pod |
| `webtop-config` | tools | 10Gi | nfs-csi-nvme | 🟡 → **local-path** | Config desktop, un seul pod. Attention : 10Gi sur disque VM (100Gi total) |
| `asa-cluster-pvc` | games | 1Gi | nfs-csi-nvme | 🟡 → **local-path** | Transferts cross-serveur via fichiers. Garder NFS si multi-instance ARK un jour |
| `asa-serverfiles-pvc` | games | 140Gi | nfs-csi-nvme | 🟢 Garder NFS | Trop gros pour disque VM (100Gi total). NFS inévitable ici |
| `pvc-media-data` | media | 10Ti | nfs-csi-hdd | 🟢 Garder NFS | Partagé entre filebrowser, navidrome, metube (ReadWriteMany) |
| `pvc-media-video` | media | 10Ti | nfs-csi-hdd | 🟢 Garder NFS | Partagé entre filebrowser, jellyfin, metube (ReadWriteMany) |
| `immich-library` | media | 100Gi | nfs-csi-hdd | 🟢 Garder NFS | Partagé entre immich-server et machine-learning (ReadWriteMany) |
| `pvc-samba-nvme` | storage | 1Ti | nfs-csi-nvme | 🟢 Garder NFS | Exposé via Samba — NFS est le backend par design |
| `pvc-samba-video` | storage | 1Gi | nfs-csi-hdd | 🟢 Garder NFS | Idem, partage Samba |
| `pvc-samba-data` | storage | 1Gi | nfs-csi-hdd | 🟢 Garder NFS | Idem, partage Samba |

---

## Récapitulatif des migrations prioritaires

| Priorité | PVC | Risque perte de données |
|----------|-----|------------------------|
| 🔴 Haute | `filebrowser-config` | Faible (SQLite recréée) |
| 🔴 Haute | `navidrome-data` | Moyen (DB + metadata musicale) |
| 🔴 Haute | `jellyfin-config` | Moyen (config + metadata media) |
| 🔴 Haute | `metube-state` | Faible (état queue reconstitué) |
| 🟡 Moyenne | `webtop-config` | Moyen (config desktop) |
| 🟡 Moyenne | `asa-cluster-pvc` | Faible (données de transfert temporaires) |

---

## Procédure de migration NFS → local-path

### Prérequis

La storageClass d'un PVC **ne peut pas être modifiée** sur un PVC existant. Il faut obligatoirement supprimer et recréer le PVC. Si des données doivent être préservées, les copier avant.

### Procédure générique

```bash
APP=<nom-app>
NAMESPACE=<namespace>
PVC=<nom-pvc>
```

#### Étape 1 — (Si données importantes) Backup

```bash
# Lancer un pod temporaire pour copier les données
kubectl run backup-pod -n $NAMESPACE --rm -it \
  --image=busybox --restart=Never \
  --overrides="{
    \"spec\": {
      \"volumes\": [{\"name\": \"data\", \"persistentVolumeClaim\": {\"claimName\": \"$PVC\"}}],
      \"containers\": [{
        \"name\": \"backup\",
        \"image\": \"busybox\",
        \"command\": [\"sh\"],
        \"volumeMounts\": [{\"name\": \"data\", \"mountPath\": \"/mnt/data\"}]
      }]
    }
  }" -- /bin/sh

# Dans le pod, copier les données vers un tar :
# tar czf /tmp/backup.tar.gz -C /mnt/data .
# exit
```

Ou via `kubectl cp` depuis un pod existant :
```bash
kubectl cp $NAMESPACE/<pod>:/chemin/config ./backup-$APP/
```

#### Étape 2 — Scale down

```bash
kubectl scale deployment $APP -n $NAMESPACE --replicas=0
```

#### Étape 3 — Modifier le `pvc.yaml`

Changer `storageClassName` :
```yaml
# Avant
storageClassName: nfs-csi-nvme

# Après
storageClassName: local-path
```

#### Étape 4 — Supprimer l'ancien PVC et en créer un neuf

```bash
kubectl delete pvc $PVC -n $NAMESPACE
kubectl apply -f apps/<path>/pvc.yaml
```

#### Étape 5 — (Si backup) Restaurer les données

```bash
# Lancer un pod temporaire avec le nouveau PVC
kubectl run restore-pod -n $NAMESPACE --rm -it \
  --image=busybox --restart=Never \
  --overrides="{
    \"spec\": {
      \"volumes\": [{\"name\": \"data\", \"persistentVolumeClaim\": {\"claimName\": \"$PVC\"}}],
      \"containers\": [{
        \"name\": \"restore\",
        \"image\": \"busybox\",
        \"command\": [\"sh\"],
        \"volumeMounts\": [{\"name\": \"data\", \"mountPath\": \"/mnt/data\"}]
      }]
    }
  }" -- /bin/sh

# Dans le pod, restaurer :
# tar xzf /tmp/backup.tar.gz -C /mnt/data
```

Ou via `kubectl cp` :
```bash
kubectl cp ./backup-$APP/ $NAMESPACE/<restore-pod>:/mnt/data/
```

#### Étape 6 — Scale up

```bash
kubectl apply -f apps/<path>/deployment.yaml  # ou kubectl scale ... --replicas=1
```

---

## Cas par cas — Commandes prêtes

### filebrowser-config (sans backup nécessaire — SQLite recréée)

```bash
kubectl scale deployment filebrowser -n media --replicas=0
kubectl delete pvc filebrowser-config -n media
# Modifier apps/media/filebrowser/pvc.yaml : nfs-csi-nvme → local-path
kubectl apply -f apps/media/filebrowser/pvc.yaml
kubectl scale deployment filebrowser -n media --replicas=1
```

### navidrome-data (backup recommandé)

```bash
# Backup
kubectl cp media/$(kubectl get pod -n media -l app=navidrome -o jsonpath='{.items[0].metadata.name}'):/data ./backup-navidrome/

kubectl scale deployment navidrome -n media --replicas=0
kubectl delete pvc navidrome-data -n media
# Modifier apps/media/navidrome/pvc.yaml : nfs-csi-nvme → local-path
kubectl apply -f apps/media/navidrome/pvc.yaml
kubectl scale deployment navidrome -n media --replicas=1

# Restaurer si nécessaire
kubectl cp ./backup-navidrome/ media/$(kubectl get pod -n media -l app=navidrome -o jsonpath='{.items[0].metadata.name}'):/data/
```

### jellyfin-config (backup recommandé — metadata et config transcoding)

```bash
# Backup
kubectl cp media/$(kubectl get pod -n media -l app.kubernetes.io/name=jellyfin -o jsonpath='{.items[0].metadata.name}'):/config ./backup-jellyfin/

kubectl scale deployment -n media -l app.kubernetes.io/name=jellyfin --replicas=0
kubectl delete pvc jellyfin-config -n media
# Modifier apps/media/jellyfin/pvc.yaml : nfs-csi-nvme → local-path
kubectl apply -f apps/media/jellyfin/pvc.yaml
kubectl scale deployment -n media -l app.kubernetes.io/name=jellyfin --replicas=1
```

### metube-state (sans backup nécessaire)

```bash
kubectl scale deployment metube -n media --replicas=0
kubectl delete pvc metube-state -n media
# Modifier apps/media/metube/pvc.yaml : nfs-csi-nvme → local-path
kubectl apply -f apps/media/metube/pvc.yaml
kubectl scale deployment metube -n media --replicas=1
```

---

## Note sur les limites du disque VM

Le disque VM (`ubuntu-srv-k3s-prod`) fait **100 Gi**. Les PVCs `local-path` consomment de l'espace sur ce disque.

Avant de migrer `webtop-config` (10Gi), vérifier l'espace disponible :
```bash
kubectl exec -n kube-system -l app=local-path-provisioner -- df -h /var/lib/rancher/k3s/storage/
```
