# TODO Kluster

## Réseau / DNS
- [ ] **Problème ndots: 5** : Investiguer pourquoi la résolution DNS échoue (ServFail ou timeout) pour les domaines externes sans un `ndots: 1` explicite. Le comportement par défaut de K8s (`ndots: 5`) semble entrer en conflit avec le resolver ou le DNS amont dans certains Pods (MeTube, Syncthing).

## Proxmox / Hôte pve1
- [ ] **Stabiliser le nom de l'interface réseau** : à chaque ajout de matériel PCIe (NVMe, GPU…), l'énumération du bus PCI décale et l'interface change de nom (ex. `enp5s0` → `enp6s0`), ce qui casse `vmbr0` dans `/etc/network/interfaces` et coupe le réseau de l'hôte. Solution durable : ajouter un `.link` systemd qui épingle le nom (ex. `lan0`) à la MAC de la NIC, puis mettre à jour `/etc/network/interfaces` pour référencer ce nom stable. À automatiser dans le rôle Ansible `proxmox_config` (repo `infra_proxmox`).
