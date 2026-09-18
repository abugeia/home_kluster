# TODO Kluster

## Réseau / DNS
- [ ] **Problème ndots: 5** : Investiguer pourquoi la résolution DNS échoue (ServFail ou timeout) pour les domaines externes sans un `ndots: 1` explicite. Le comportement par défaut de K8s (`ndots: 5`) semble entrer en conflit avec le resolver ou le DNS amont dans certains Pods (MeTube, Syncthing).

## Stockage / StorageClass
- [ ] **Généraliser `reclaimPolicy: Retain` sur `nfs-csi-nvme`** : aujourd'hui la SC est en `Delete`, donc **23 PV de configs/DB** (home-assistant, grafana, navidrome, jellyfin, immich, clickhouse, saves ASA, qbittorrent, syncthing…) sont détruits si leur PVC est supprimé (refactor, suppression de namespace, prune ArgoCD). Seul `nfs-csi-hdd` est en `Retain`. Correction en 3 temps : (1) éditer `conf/nfs.yaml` (SC nvme → `Retain`) ; (2) recréer la SC (immutable → delete+apply) ; (3) patcher les 23 PV existants en `Retain` (one-shot, car le reclaimPolicy est figé à la création du PV). Compromis à assumer : avec `Retain`, un PVC supprimé laisse un PV `Released` + un dossier NFS orphelins à nettoyer manuellement. Limite gitops : les PV dynamiques ne sont jamais versionnés, seule la SC est déclarative et n'agit qu'aux créations futures.

## Proxmox / Hôte pve1
- [ ] **Stabiliser le nom de l'interface réseau** : à chaque ajout de matériel PCIe (NVMe, GPU…), l'énumération du bus PCI décale et l'interface change de nom (ex. `enp5s0` → `enp6s0`), ce qui casse `vmbr0` dans `/etc/network/interfaces` et coupe le réseau de l'hôte. Solution durable : ajouter un `.link` systemd qui épingle le nom (ex. `lan0`) à la MAC de la NIC, puis mettre à jour `/etc/network/interfaces` pour référencer ce nom stable. À automatiser dans le rôle Ansible `proxmox_config` (repo `infra_proxmox`).

## Sécurité / Harbor
- [ ] **Secrets Harbor laissés aux valeurs par défaut du chart** : `secretKey` vaut
  littéralement `not-a-secure-key` et `REGISTRY_CREDENTIAL_PASSWORD` vaut
  `harbor_registry_password` — les deux sont publiés dans le `values.yaml` du chart
  goharbor (vérifié le 2026-09-18 en comparant les empreintes SHA-256, sans décoder).
  L'OIDC devant `harbor.valab.top` ne couvre ni l'un ni l'autre : (1) `secretKey`
  chiffre des credentials stockés dans PostgreSQL (10.0.0.12), donc un dump ou un
  backup suffit à les déchiffrer ; (2) le service `harbor-registry` est en ClusterIP
  sans aucune NetworkPolicy dans `storage`, donc n'importe quel pod du cluster peut
  s'authentifier en direct sur le registry avec ce mot de passe public et
  court-circuiter harbor-core — vecteur réel vu les deux runners GitHub self-hosted.
  Correction : sceller les deux valeurs et les câbler via `existingSecretSecretKey`
  et `registry.credentials.existingSecret`. **Piège** : changer `secretKey` rend
  illisible tout ce qui a été chiffré avec l'ancienne (credentials des endpoints de
  réplication) — vérifier d'abord s'il en existe, sinon les recréer après.
- [ ] **Harbor se redéploie en boucle (768 révisions)** : même cause racine que
  Grafana (corrigé le 2026-09-18). Le `lookup` des templates du chart renvoie
  toujours vide en `helm template`, mode de rendu d'ArgoCD, donc `core.secret`,
  `CSRF_KEY`, `JOBSERVICE_SECRET` et `REGISTRY_HTTP_SECRET` sont régénérés à chaque
  rendu. Pire, `tls.crt`/`tls.key` viennent d'un `genCA "harbor-token-ca" 365` **sans
  aucun lookup** : le CA de signature des tokens est recréé à chaque fois, ce qui
  invalide les opérations pull/push en vol. Corriger en figeant ces valeurs dans des
  secrets scellés (`core.existingSecret`, `core.existingXsrfSecret`,
  `jobservice.existingSecret`, `registry.secret`, `core.secretName`).

