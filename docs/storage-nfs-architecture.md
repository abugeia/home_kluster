# NFS — Architecture et infrastructure

## 1. Architecture physique du host Proxmox (`pve1` — 10.0.0.10)

### Disques

| Disque | Taille | Usage |
|--------|--------|-------|
| `nvme0n1` | 1.8 TB | OS Proxmox + LVM (`pve-root` 96GB, `pve-data` 1.67TB) |
| `nvme1n1` | 953.9 GB | ZFS : `p1` → `tank_data` (special vdev NVMe), `p2` → `scratch` |
| `nvme2n1` | 476.9 GB | ZFS : `p1` → `tank_data` (special vdev NVMe), `p2` → `scratch` |
| `sda` + `sdb` | 14.6 TB × 2 | ZFS : `tank_data` (mirror HDD) |

### Pools ZFS

**`tank_data`** (14.8 TB total — RAID-1 HDD avec special vdev NVMe mirroré)

Architecture hybride : données et gros blocs sur HDD en miroir, metadata + petits blocs sur NVMe mirroré (special vdev). Optimise les IOPS sans sacrifier la capacité.

| Dataset | Utilisé | Point de montage | Exporté NFS |
|---------|---------|-----------------|-------------|
| `tank_data/data` | 2.55 TB | `/tank_data/data` | oui |
| `tank_data/video` | 3.23 TB | `/tank_data/video` | oui |
| `tank_data/immich` | 444 GB | `/tank_data/immich` | oui |
| `tank_data/k8s` | 4.98 GB | `/tank_data/k8s` | oui |
| `tank_data/object_storage` | ~0 | `/tank_data/object_storage` | oui |

**`scratch`** (828 GB — stripe NVMe, non mirroré)
- nvme1n1p2 + nvme2n1p2 en stripe
- Usage : données temporaires, non critiques
- Monté sur `/scratch`

### LVM (`pve-data` sur nvme0n1p3)

LVM-thin pool de 1.67 TB contenant les images disque des VMs :

| Volume | Taille | Usage |
|--------|--------|-------|
| `vm-811-disk-0` | 100 GB | VM k3s prod (`ubuntu-srv-k3s-prod`, 10.0.0.11) |
| `vm-817-disk-1` | 80 GB | VM arch-lab |
| `vm-113-disk-0` | 60 GB | — |
| `vm-112-disk-0` | 20 GB | — |
| `vm-116-disk-0` | 4 GB | — |

---

## 2. NFS server

### Configuration (`/etc/exports`)

```
/mnt/nfs         *(rw,sync,no_subtree_check,no_root_squash)
/tank_data/video *(rw,sync,no_subtree_check,no_root_squash)
/tank_data/immich *(rw,sync,no_subtree_check,no_root_squash)
/tank_data/data  *(rw,sync,no_subtree_check,no_root_squash)
/tank_data/import *(rw,sync,no_subtree_check,no_root_squash)
/tank_data/k8s   *(rw,sync,no_subtree_check,no_root_squash)
/tank_data/object_storage *(rw,sync,no_subtree_check,no_root_squash)
```

`no_root_squash` : root côté client = root côté serveur. Nécessaire pour que le kubelet (qui monte les volumes en root) puisse écrire sur les PVCs.

`/mnt/nfs` est sur `pve-root` (LVM ext4 sur nvme0n1). C'est là que le csi-driver-nfs crée les sous-dossiers par PVC (`/mnt/nfs/pvc-<uuid>/`).

### Déployé via Ansible

Role : `roles/proxmox_config/tasks/nfs_server.yml`  
Playbook : `proxmox_config.yml`

---

## 3. StorageClasses Kubernetes

| StorageClass | Backend | Provisioner | ReclaimPolicy |
|---|---|---|---|
| `nfs-csi-nvme` | `/mnt/nfs` (pve-root, NVMe LVM) | nfs.csi.k8s.io | Delete |
| `nfs-csi-hdd` | `/tank_data/k8s` (ZFS HDD) | nfs.csi.k8s.io | Retain |
| `local-path` *(default)* | `/var/lib/rancher/k3s/storage/` (disque VM) | rancher.io/local-path | Delete |

---

## 4. Chemin d'une écriture NFS (cas loopback)

Pour un pod dans la VM k3s (10.0.0.11) accédant à un PVC `nfs-csi-nvme` :

```
Process dans le pod (uid=7777)
  → syscall write()
  → kernel NFS client (VM ubuntu-srv-k3s-prod)
  → TCP via vmbr0 (réseau virtuel, même host physique)
  → kernel NFS server (Proxmox pve1)
  → ext4 sur pve-root (LVM-thin sur nvme0n1)
  → NVMe nvme0n1
```

**5 couches** pour accéder à un disque physiquement sur le même host.

---

## 5. Problèmes connus et limites

### 5.1 Permissions UID/GID avec Kubernetes

**Contexte** : Kubernetes gère les permissions volumes via `fsGroup` / `fsGroupChangePolicy` dans le pod spec. Ces mécanismes font des `chown` sur les fichiers au démarrage du pod, via le kubelet (root). Avec `no_root_squash`, ces chown atterrissent réellement sur le NFS server.

Cela peut entrer en conflit avec :
- Les `initContainers` qui font leur propre `chown`
- Les applications qui créent des fichiers avec des UIDs spécifiques

La priorité d'exécution : `initContainer` → kubelet fsGroup chown → démarrage container.  
Si le kubelet chown passe après l'initContainer, il peut écraser ses permissions.

**Workaround** : supprimer `fsGroupChangePolicy: "Always"` du pod spec pour que le kubelet ne re-chown pas à chaque démarrage. Ou gérer les permissions directement sur le NFS server.

### 5.2 Stale NFS handles

NFS est stateless. Après un reboot du host, un crash du service NFS, ou une coupure réseau, les file handles ouverts par les clients deviennent `stale`. Avec des montages `hard` (défaut), le client va retenter indéfiniment — le pod se bloque. Avec des montages `soft`, le client abandonne après timeout et retourne une erreur I/O.

Comportement avec `csi-driver-nfs` après reboot : les montages sont refaits automatiquement, mais les applications qui tenaient des fichiers ouverts peuvent ne pas se rendre compte que le handle est stale. Les writes suivants échouent silencieusement ou retournent `ESTALE`.

### 5.3 Complexité de débogage

Un `Permission denied` ou un write silencieusement raté peut venir de :
1. Permissions filesystem côté NFS server
2. Options d'export (`root_squash`, `squash_ids`)
3. kubelet fsGroup chown
4. initContainer
5. `securityContext` du pod/container

Cinq couches à inspecter séquentiellement.

### 5.4 Loopback réseau virtuel

VM et NFS server sur le même host physique : inutile d'avoir un aller-retour réseau. Légèrement pénalisant en latence vs un accès disque direct, mais négligeable pour la plupart des workloads (saves de jeu, fichiers médias, etc.).

---

## 6. Améliorations possibles

### Court terme

**Migrer les workloads write-intensifs vers `local-path`**  
Les PVCs petites et fréquemment écrites (ex: saves de jeux) n'ont pas besoin de NFS. `local-path` = disque VM = zéro problème de permissions NFS, zéro stale handle, latence minimale.  
Contrainte : disque VM de 100 GB → à surveiller pour les gros volumes.

**Documenter les `chown` initiaux dans Ansible**  
Le NFS server ne fait pas de `chown` initial sur `/mnt/nfs` — les PVCs créées par `csi-driver-nfs` héritent des permissions root. Ajouter dans Ansible un `setgid` ou un `chown` post-création pour les cas où les pods tournent avec des UIDs fixes.

### Moyen terme

**Séparer `/mnt/nfs` sur un dataset ZFS dédié**  
Actuellement sur `pve-root` (ext4, LVM), donc partagé avec l'OS Proxmox. Un dataset ZFS dédié permettrait : snapshots automatiques, quotas par PVC (via `zfs set quota`), compression transparente.

**Ajouter des snapshots ZFS sur `tank_data`**  
`tank_data/k8s` et les données critiques n'ont pas de snapshots automatiques configurés (à confirmer). Un `zfs-auto-snapshot` ou équivalent Ansible ajouterait une protection supplémentaire.

### Long terme — multi-nœuds

Si un second nœud k3s est ajouté, `local-path` et `nfs-csi-nvme` posent des problèmes de scheduling : les pods sont épinglés au nœud qui a le volume. Options :

| Solution | Avantages | Inconvénients |
|---|---|---|
| NFS actuel partagé | Multi-nœuds transparent | Toutes les limitations actuelles |
| **Longhorn** | Réplication entre nœuds, snapshots k8s natifs, UI | Overhead CPU/RAM, complexité |
| Ceph / Rook | Très scalable | Beaucoup trop lourd pour homelab |
| NFS sur VM dédiée | Séparation claire | VM supplémentaire à maintenir |

Pour un homelab à 2-3 nœuds, **Longhorn** est le meilleur rapport simplicité/fonctionnalités.
