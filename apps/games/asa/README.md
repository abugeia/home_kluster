# Serveur ARK: Survival Ascended (ASA) sur Kubernetes

Ce dossier contient le manifeste de déploiement d'un serveur dédié **ARK: Survival Ascended** via l'image Docker `acekorneya/asa_server` qui utilise Proton/Wine pour faire tourner l'exécutable Windows sur notre cluster K3s (`home_kluster`).

## 1. Prérequis Infrastructure (Proxmox / K3s)
ASA est extrêmement gourmand. Il nécessite certaines configurations hôtes pour fonctionner sans crasher :
- **CPU** : Le processeur de la VM Proxmox (`k3s-prod`) DOIT être réglé sur le type `"host"`.
- **Mémoire** : Minimum 16 Go de RAM allouée (le processus monte généralement à 10-12 Go).
- **Kernel Host** : K3s nécessite un réglage sysctl sur la machine hôte pour le moteur Unreal Engine 5.
  ```bash
  sysctl -w vm.max_map_count=262144
  ```

## 2. Déploiement K8s
L'image `acekorneya/asa_server:2_1_latest` (et supérieures) s'exécute sous l'utilisateur `pok` (UID: `7777`).
Il est indispensable que les permissions des dossiers montés depuis le PVC NFS soient correctes. Le manifeste `asa.yaml` gère cela automatiquement via un `initContainer` qui effectue un `chown -R 7777:7777 /home/pok/arkserver`.

- **Stockage** : Prévoyez au moins 60-140 Go pour le dossier racine (`asa-serverfiles-pvc`) afin d'anticiper le téléchargement du jeu (≈ 14 Go) et l'ajout massif de mods (très lourds sous UE5).

## 3. Connexion au serveur
L'intégration au "Navigateur des Serveurs Steam" (port 27015) est obsolète depuis ARK: Ascended (remplacé par l'écosystème Epic EOS).

Pour rejoindre le serveur :
1. Lancez le jeu.
2. Ouvrez la console du jeu (Souvent `Tab` ou `~`).
3. Tapez : `open 10.0.0.103:7777`
4. Vérifiez que la console "ne renvoie pas une erreur Instantanée", l'écran noir/chargement devrait s'estomper une fois la connexion établie (≈ 2 mins lors du premier cache shader).
