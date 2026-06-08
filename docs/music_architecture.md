# Architecture de Gestion Musicale

Voici un schéma simplifié de ton installation actuelle pour gérer la musique, qui devrait aider à visualiser les flux de données et discuter des éventuelles améliorations d'architecture.

```mermaid
flowchart TD
    %% Define Styles
    classDef user fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px,color:#000
    classDef app fill:#fff3e0,stroke:#ff9800,stroke-width:2px,color:#000
    classDef storage fill:#e8f5e9,stroke:#4caf50,stroke-width:2px,color:#000
    classDef external fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px,color:#000

    %% Users and Devices
    User(("Toi / Ta copine")):::user
    Phone["📱 Téléphone / PC"]:::user

    %% External Sources
    Youtube["🌐 YouTube / SoundCloud"]:::external

    %% Applications
    MeTube["📥 MeTube\n(Téléchargeur)"]:::app
    Navidrome["🎵 Navidrome\n(Lecteur Streaming)"]:::app
    Syncthing["🔄 Syncthing\n(Synchronisation)"]:::app

    %% Storage (PVC)
    subgraph Cluster Kubernetes
        subgraph pvc-media-data [💾 Disque: pvc-media-data]
            DirSync["📁 Dossier: Musique_sync\n(Nouveaux téléchargements)"]:::storage
            DirMusic["📁 Dossier: Music\n(Bibliothèque organisée ?)"]:::storage
        end

        MeTube
        Navidrome
        Syncthing
    end

    %% Workflows
    User -- "Demande un téléchargement\n(Lien web)" --> MeTube
    MeTube -- "Télécharge l'audio" --> Youtube
    MeTube -- "Sauvegarde le fichier" --> DirSync

    DirSync -. "Scanné automatiquement" .-> Navidrome
    DirMusic -. "Scanné automatiquement" .-> Navidrome

    User -- "Écoute en streaming\n(via Tailscale)" --> Navidrome

    DirSync -. "Accès total" .-> Syncthing
    DirMusic -. "Accès total" .-> Syncthing

    Syncthing <== "Synchronise les fichiers\n(Pour écoute hors-ligne)" ==> Phone
    User -- "Ajoute de la musique manuellement" --> Phone
```

## Comment lire ce schéma

1.  **L'entrée (Téléchargement) :** Vous donnez un lien YouTube à **MeTube**. Il télécharge uniquement l'audio et le place dans le dossier `Musique_sync`.
2.  **L'écoute (Streaming) :** **Navidrome** surveille en permanence le dossier `Musique_sync` (et un autre dossier `Music`). Dès qu'un nouveau son arrive, il apparaît dans l'application Navidrome et vous pouvez l'écouter partout (tant que Tailscale est activé).
3.  **La sauvegarde / L'écoute hors-ligne (Syncthing) :** **Syncthing** voit tous ces dossiers. Si vous le configurez sur vos téléphones, il peut télécharger automatiquement en arrière-plan les musiques de `Musique_sync` pour que vous puissiez les écouter même dans l'avion ou sans connexion.

## Choix d'architecture (Questions à se poser)

*   **Organisation :** Actuellement, tout ce qui est téléchargé via MeTube va dans `Musique_sync` en vrac. Voulez-vous un système pour trier cette musique (par artiste/album) avant qu'elle n'aille dans le dossier final `Music` lu par Navidrome ?
*   **Synchronisation bidirectionnelle :** Si tu ajoutes des MP3 depuis ton PC vers le dossier `Music` via Syncthing, Navidrome les lira. Est-ce le comportement souhaité ?
*   **Nettoyage :** Que se passe-t-il quand vous supprimez une musique ? Si tu la supprimes sur ton téléphone, Syncthing la supprimera-t-il du cluster ? (Ça dépend de comment tu configures le dossier Syncthing : "Send Only", "Receive Only", ou "Send & Receive").
