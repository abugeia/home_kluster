# TODO Kluster

## Réseau / DNS
- [ ] **Problème ndots: 5** : Investiguer pourquoi la résolution DNS échoue (ServFail ou timeout) pour les domaines externes sans un `ndots: 1` explicite. Le comportement par défaut de K8s (`ndots: 5`) semble entrer en conflit avec le resolver ou le DNS amont dans certains Pods (MeTube, Syncthing).

## Stockage / StorageClass
- [ ] **Généraliser `reclaimPolicy: Retain` sur `nfs-csi-nvme`** : aujourd'hui la SC est en `Delete`, donc **23 PV de configs/DB** (home-assistant, grafana, navidrome, jellyfin, immich, clickhouse, saves ASA, qbittorrent, syncthing…) sont détruits si leur PVC est supprimé (refactor, suppression de namespace, prune ArgoCD). Seul `nfs-csi-hdd` est en `Retain`. Correction en 3 temps : (1) éditer `conf/nfs.yaml` (SC nvme → `Retain`) ; (2) recréer la SC (immutable → delete+apply) ; (3) patcher les 23 PV existants en `Retain` (one-shot, car le reclaimPolicy est figé à la création du PV). Compromis à assumer : avec `Retain`, un PVC supprimé laisse un PV `Released` + un dossier NFS orphelins à nettoyer manuellement. Limite gitops : les PV dynamiques ne sont jamais versionnés, seule la SC est déclarative et n'agit qu'aux créations futures.

## Proxmox / Hôte pve1
- [ ] **Stabiliser le nom de l'interface réseau** : à chaque ajout de matériel PCIe (NVMe, GPU…), l'énumération du bus PCI décale et l'interface change de nom (ex. `enp5s0` → `enp6s0`), ce qui casse `vmbr0` dans `/etc/network/interfaces` et coupe le réseau de l'hôte. Solution durable : ajouter un `.link` systemd qui épingle le nom (ex. `lan0`) à la MAC de la NIC, puis mettre à jour `/etc/network/interfaces` pour référencer ce nom stable. À automatiser dans le rôle Ansible `proxmox_config` (repo `infra_proxmox`).
