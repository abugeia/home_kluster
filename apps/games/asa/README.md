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

## 3. Ajout d'un Crack / OnlineFix (RexaGames)
Le serveur téléchargé par l'image via SteamCMD est officiel (Vanilla). Pour qu'il accepte les joueurs utilisant une version crackée du jeu (générant des tickets Spacewar/EOS), **il faut appliquer le crack côté serveur également.**

*Avertissement : Les DLL d'Epic Online Services (EOS) et SteamAPI sont maintenues en mémoire par la VM Wine. Il est indispensable de les effacer (unlink) avant de copier les fichiers crackés sur un stockage NFS pour éviter l'erreur `Device or resource busy` (ou `File exists` via tar).*

### Procédure de patch (Client K8s vers Pod) :

1. Placer votre terminal dans le dossier du crack local (`Dedicated Fix/` fourni par RexaGames/OnlineFix).
2. Supprimer les fichiers de sécurité existants en écrasant les droits d'écriture sur le Pod en cours d'exécution :
   ```bash
   MSYS_NO_PATHCONV=1 kubectl exec -i -n games deployment/asa-server -c asa-server -- bash -c "chmod -R u+w /home/pok/arkserver/Engine /home/pok/arkserver/ShooterGame && rm -f /home/pok/arkserver/ShooterGame/Binaries/Win64/RedpointEOS/EOSSDK-Win64-Shipping.dll /home/pok/arkserver/Engine/Binaries/ThirdParty/Steamworks/Steamv157/Win64/steam_api64.dll"
   ```
3. Injecter le dossier crack via `tar` :
   ```bash
   MSYS_NO_PATHCONV=1 tar -cf - . | MSYS_NO_PATHCONV=1 kubectl exec -i -n games deployment/asa-server -c asa-server -- tar -xf - --no-same-owner -C /home/pok/arkserver/
   ```
4. Forcer la prise en charge des fausses DLLs par Wine/Proton. *(Déjà inclus dans le manifeste `asa.yaml` sous forme de variable d'environnement : `WINEDLLOVERRIDES="winmm=n,b;OnlineFix64=n,b"`).*
5. Redémarrer le serveur pour que le patch prenne effet :
   ```bash
   kubectl delete pod -n games -l app=asa-server
   ```

## 4. Connexion au serveur
L'intégration au "Navigateur des Serveurs Steam" (port 27015) est obsolète depuis ARK: Ascended (remplacé par l'écosystème Epic EOS).

Pour rejoindre avec la version Crackée :
1. Lancez **Steam** en arrière-plan (requis pour le contournement Spacewar).
2. Lancez le jeu.
3. Ouvrez la console du jeu (Souvent `Tab` ou `~`).
4. Tapez : `open 10.0.0.103:7777`
5. Vérifiez que la console "ne renvoie pas une erreur Instantanée", l'écran noir/chargement devrait s'estomper une fois la connexion établie (≈ 2 mins lors du premier cache shader).
