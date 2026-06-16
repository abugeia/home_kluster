# Playlists Navidrome

Fichiers de **smart playlists** Navidrome (`.nsp`). Ils ne sont **pas** déployés
par ArgoCD (le chemin `apps/media/navidrome` est synchronisé en mode directory ;
un `.nsp` y serait pris pour un manifeste et casserait le sync). Ils vivent ici
comme **source de vérité versionnée**, et sont déposés manuellement sur le partage
NFS (voir ci-dessous).

## `Offline - Musique_sync.nsp`

Smart playlist qui capture **tout ce qui est dans le dossier `Musique_sync/`**, via
le critère `filepath contains "Musique_sync/"` (+ `missing: false` pour exclure
les entrées fantômes des fichiers déplacés par beets). Elle sert de **handle offline**
pour Symfonium : Symfonium ne sait pas mettre « un dossier » hors-ligne (browsing
par métadonnées, pas par arborescence), mais il sait auto-cacher une playlist.

Champs confirmés dans le code Navidrome (`model/criteria/fields.go`) : `filepath`
et `library_id` existent. La playlist se rafraîchit toute seule
(`SmartPlaylistRefreshDelay`, ~5 s).

### Déploiement (manuel, une fois)

1. Déposer le fichier sur le partage NFS, dans la bibliothèque maître (stable, hors
   du churn de staging) → via **Filebrowser** : `/srv/data/Musique/Offline - Musique_sync.nsp`
   (= `/tank_data/data/Musique/...` sur le Proxmox).
   - Navidrome scanne toute la bibliothèque pour les playlists (`PlaylistsPath`
     vide par défaut + `AutoImportPlaylists=true`), donc l'emplacement dans
     `Musique/` suffit ; pas besoin de le mettre dans `Musique_sync/`.
2. Attendre le prochain scan / refresh → la playlist **« Offline - Musique_sync »**
   apparaît dans Navidrome (et via Subsonic).
3. Dans **Symfonium** (chaque appareil) : ouvrir la playlist → activer le
   **cache offline automatique** dessus (Settings > offline auto rules, ou
   l'option « auto download/cache » sur la playlist). Symfonium maintient alors le
   contenu de `Musique_sync/` hors-ligne, et le met à jour tout seul.

> Pourquoi pas le « cache par bibliothèque » de Symfonium ? Cette option est
> temporairement retirée de Symfonium (le dev a annoncé son retour) ; le workaround
> officiel est précisément la smart playlist filtrée + auto-cache.
