# ASA — Problèmes de sauvegarde et storage

## Contexte

Le serveur ARK Survival Ascended tourne dans Kubernetes (namespace `games`) via l'image `acekorneya/asa_server:2_1_latest` (Wine/Proton sous Linux). Le monde est sauvegardé sur NFS via la PVC `asa-shootergame-pvc`.

---

## 1. Volumes PVC

| PVC | StorageClass | Taille | Contenu |
|-----|-------------|--------|---------|
| `asa-serverfiles-pvc` | `nfs-csi-nvme` | 140 GB | Binaires du jeu (~65 GB utilisés) |
| `asa-shootergame-pvc` | `nfs-csi-nvme` | 10 GB | Saves, configs, logs |
| `asa-cluster-pvc` | `nfs-csi-nvme` | 1 GB | Données cluster multi-serveur |

Chemin NFS réel des saves :
```
/mnt/nfs/pvc-02c6c006-21cb-41ce-b19a-4eb00dfe3623/SavedArks/TheIsland_WP/
```

---

## 2. Mécanisme de sauvegarde ARK

### Fichiers de save

| Fichier | Rôle |
|---------|------|
| `TheIsland_WP.ark` | Save principale (~65 MB) |
| `TheIsland_WP_DD.MM.YYYY_HH.MM.SS.arkrbf` | Backups rotatifs (crées à chaque save) |
| `TheIsland_WP_AntiCorruptionBackup.bak` | Backup créé si ARK détecte un shutdown sale |

### Mécanisme anti-corruption ARK

ARK a un système de protection contre la corruption :
- **Shutdown propre** (saveworld avant arrêt) → redémarrage normal, charge `TheIsland_WP.ark`
- **Shutdown sale** (SIGKILL sans saveworld) → au redémarrage, ARK crée `AntiCorruptionBackup.bak` depuis `TheIsland_WP.ark`, puis **rollback** vers la dernière save "propre"

Ce mécanisme était la cause principale de perte de progression : toute la journée de jeu perdue si le pod était tué sans `saveworld`.

### Durée d'une save

~0.3 secondes pour 65 MB sur NFS. L'autosave ne bloque pas le gameplay.

---

## 3. Problème 1 — Perte de progression au kill du pod (RÉSOLU)

### Cause
Kubernetes tue le pod avec SIGKILL sans déclencher de `saveworld` → ARK détecte un shutdown sale → rollback.

### Solution : PreStop hook

```yaml
lifecycle:
  preStop:
    exec:
      command:
        - "/bin/bash"
        - "-c"
        - |
          echo "PreStop: Saving world before shutdown..."
          /home/pok/scripts/rcon_interface.sh -saveworld
          echo "PreStop: Save done, waiting for completion..."
          sleep 5
```

**Attention** : le script correct est `rcon_interface.sh -saveworld`, PAS `rcon_commands.sh saveworld`. Le second ne dispatch pas les arguments et n'exécute rien (exit 0 silencieux).

### Vérification

Après un kill, le fichier `.arkrbf` doit avoir le timestamp du kill :
```bash
ls -lht /home/pok/arkserver/ShooterGame/Saved/SavedArks/TheIsland_WP/*.arkrbf | head -2
```

Et `AntiCorruptionBackup.bak` ne doit **pas** être créé au redémarrage suivant.

---

## 4. Problème 2 — Permissions root:root après reboot (EN COURS)

### Symptôme

Après reboot du host Proxmox, les fichiers `.ark` deviennent `root:root` :
```
-rw-rw-r-- 1 root root 68042752 TheIsland_WP.ark
```

Le process ARK (uid=7777) n'a que la lecture → les autosaves échouent silencieusement. `rcon_interface.sh -saveworld` retourne `World Saved` mais le timestamp du fichier ne change pas.

### Cause

ARK (via Wine) fait un write atomique : il écrit dans un fichier temporaire puis fait un `rename()` vers `TheIsland_WP.ark`. Le nouveau fichier créé lors du `rename` prend les permissions du process Wine dans le contexte NFS, qui sont `root:root` en raison du `no_root_squash`.

Les `chown` de l'initContainer et le `fsGroupChangePolicy` Kubernetes se marchent dessus, et après le reboot le fichier se retrouve en `root:root`.

### Workaround actuel

```bash
ssh root@10.0.0.10 "chown -R 7777:7777 /mnt/nfs/pvc-02c6c006-21cb-41ce-b19a-4eb00dfe3623/"
```

À faire manuellement après chaque reboot du host (ou après chaque redémarrage du pod si le problème se reproduit).

### Fix partiel appliqué

Suppression de `fsGroupChangePolicy: "Always"` dans `asa.yaml` : retire le re-chown du kubelet au démarrage. Insuffisant seul car ARK recrée le fichier en `root:root` via le `rename` atomique.

### Solutions envisagées

| Solution | Statut |
|---|---|
| Supprimer `fsGroupChangePolicy: "Always"` | Appliqué, insuffisant |
| `chown` manuel post-reboot | Workaround actuel |
| Service systemd one-shot Ansible sur le host (chown après NFS démarré) | Non fait |
| Migrer `asa-shootergame-pvc` vers `local-path` | **Recommandé** — voir ci-dessous |

---

## 5. Solution recommandée : migrer vers `local-path`

Migrer `asa-shootergame-pvc` (saves, 10 GB) vers `local-path` élimine définitivement le problème de permissions NFS sur ce volume critique. Les binaires (`asa-serverfiles-pvc`, 140 GB) restent en NFS car le disque VM fait 100 GB.

### Plan de migration

1. Suspendre la sync ArgoCD
2. Scale deployment à 0
3. Créer un pod busybox monté sur l'ancien PVC
4. `kubectl apply` d'un nouveau PVC `asa-shootergame-pvc-local` en `local-path`
5. Créer un pod busybox monté sur le nouveau PVC
6. `rsync` des données
7. Modifier `asa.yaml` pour pointer sur le nouveau PVC
8. Supprimer l'ancien PVC NFS
9. Réactiver ArgoCD

---

## 6. Configuration autosave

Dans `GameUserSettings.ini` sur le PVC (chemin dans le pod) :
```
/home/pok/arkserver/ShooterGame/Saved/Config/WindowsServer/GameUserSettings.ini
```

Paramètre clé :
```ini
AutoSavePeriodMinutes=10
```

Valeur par défaut ARK : 15 minutes. Réduit à 10 min pour limiter la perte max en cas d'incident.

---

## 7. Commandes utiles

```bash
# Forcer une sauvegarde
kubectl exec -n games $(kubectl get pod -n games -l app=asa-server -o jsonpath='{.items[0].metadata.name}') -- /home/pok/scripts/rcon_interface.sh -saveworld

# Vérifier timestamp de la dernière save
kubectl exec -n games $(kubectl get pod -n games -l app=asa-server -o jsonpath='{.items[0].metadata.name}') -- stat --format="%y %s" /home/pok/arkserver/ShooterGame/Saved/SavedArks/TheIsland_WP/TheIsland_WP.ark

# Vérifier permissions
kubectl exec -n games $(kubectl get pod -n games -l app=asa-server -o jsonpath='{.items[0].metadata.name}') -- ls -la /home/pok/arkserver/ShooterGame/Saved/SavedArks/TheIsland_WP/TheIsland_WP.ark

# Tester écriture NFS depuis le pod
kubectl exec -n games $(kubectl get pod -n games -l app=asa-server -o jsonpath='{.items[0].metadata.name}') -- bash -c 'echo test >> /home/pok/arkserver/ShooterGame/Saved/Logs/ShooterGame.log && echo "OK" || echo "ECHEC"'

# Corriger les permissions depuis le host (workaround)
ssh root@10.0.0.10 "chown -R 7777:7777 /mnt/nfs/pvc-02c6c006-21cb-41ce-b19a-4eb00dfe3623/"

# Voir les derniers logs ARK
kubectl exec -n games $(kubectl get pod -n games -l app=asa-server -o jsonpath='{.items[0].metadata.name}') -- tail -30 /home/pok/arkserver/ShooterGame/Saved/Logs/ShooterGame.log
```
