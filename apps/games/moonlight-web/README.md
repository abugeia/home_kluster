# Moonlight Web : jouer sur `ai-gaming` (815) depuis un navigateur

[`moonlight-web-stream`](https://github.com/MrCreativ3001/moonlight-web-stream)
est un client Moonlight qui tourne côté serveur. Il appaire Sunshine (VM 815,
`10.0.0.15`) et renvoie le flux au navigateur. Il sert au **poste du boulot**,
qui n'a ni Moonlight-Qt ni Tailscale sous Windows mais a Tailscale dans WSL.
Les machines perso gardent le client Moonlight natif sur le tailnet.

Étude complète et mesures : `TODO_MOONLIGHT_WEB.md` du repo `infra_proxmox`.

## Choix d'exposition

- **Tailnet uniquement** (`ingress.yaml`, ingress de classe `tailscale`) :
  `https://moonlight-web.tail6060fb.ts.net`. Rien n'est publié sur Internet,
  il n'y a donc ni ingress Traefik ni TinyAuth.
- **HTTPS fourni par Tailscale** : le certificat `*.ts.net` est valide, ce qui
  fait de la page un *secure context*. WebCodecs, Gamepad API et Keyboard Lock
  y fonctionnent.
- **Transport WebSocket** : l'UDP ne sort pas du réseau du boulot, donc le
  WebRTC est exclu et aucun port UDP n'est exposé.

## Mise en route (une fois)

1. Démarrer une session graphique sur la 815 depuis SSH : `gpu-mode game`.
2. Ouvrir l'UI. Le **premier compte créé devient admin**.
3. Ajouter le PC `10.0.0.15`, puis saisir le PIN affiché dans l'UI Sunshine
   de la 815.
4. Dans les réglages du stream : **Data Transport → Web Sockets**.

## Accès

- **Machines du tailnet** (portable, téléphone) : ouvrir directement
  `https://moonlight-web.tail6060fb.ts.net`.
- **Poste du boulot** (Windows sans Tailscale) : le navigateur passe par le
  conteneur `tailscale-exit` de Docker Desktop (nœud `dinum-exit-proxy`), qui
  publie un proxy HTTP sur `127.0.0.1:1056` et un proxy SOCKS5 sur
  `127.0.0.1:1055`. Il suffit de router `*.ts.net` vers ce proxy HTTP, par
  exemple avec un fichier PAC ou une extension de proxy, pour ne pas y
  envoyer le reste du trafic.
