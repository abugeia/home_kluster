# Serveur dédié Satisfactory sur Kubernetes

Serveur dédié **Satisfactory** (1.x) via l'image `robtme/satisfactory-server`
(ex-`wolveix`). Contrairement à ASA, le serveur est un binaire **Linux natif** :
pas de Wine/Proton.

## 1. Ressources
- **Mémoire** : 6 Gi réservés, limite 12 Gi. Le wiki officiel recommande 8-16 Go ;
  remonter la limite en fin de partie ou à 4+ joueurs.
- **Stockage** :
  - `satisfactory-gamefiles-pvc` (`nfs-csi-nvme`, 30 Gi) : binaires du serveur
    (~8 Go), re-téléchargés/mis à jour par SteamCMD à chaque démarrage.
  - `satisfactory-config-pvc-local` (`local-path`, 10 Gi) : saves, blueprints,
    config serveur et backups (`/config/saved`, `/config/backups`).

## 2. Réseau
IP MetalLB **10.0.0.106** (partagée entre les Services TCP et UDP) :

| Port | Proto | Usage |
|------|-------|-------|
| 7777 | UDP   | Jeu |
| 7777 | TCP   | API HTTPS (Server Manager) |
| 8888 | TCP   | Messaging fiable (depuis la 1.0) |

## 3. Première connexion
1. En jeu : *Server Manager* → *Add Server* → `10.0.0.106`, port `7777`.
2. Accepter le certificat auto-signé.
3. Le premier joueur « réclame » le serveur : il définit son nom et le mot de
   passe admin, puis crée ou charge une partie.

## 4. Arrêt / relance
Mettre `replicas: 0` dans `satisfactory.yaml` pour arrêter le serveur ; PVC et
Services sont conservés.
