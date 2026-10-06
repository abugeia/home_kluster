# Moonlight Web : jouer sur `ai-gaming` (815) depuis un navigateur

[`moonlight-web-stream`](https://github.com/MrCreativ3001/moonlight-web-stream)
est un client Moonlight qui tourne côté serveur. Il appaire Sunshine (VM 815,
`10.0.0.15`) et renvoie le flux au navigateur. Il sert aux machines où l'on ne
peut pas installer de client Moonlight natif, y compris celles dont l'UDP
sortant est bloqué. Les autres gardent le client Moonlight natif sur le tailnet.

Étude complète et mesures : `TODO_MOONLIGHT_WEB.md` du repo `infra_proxmox`.

## Choix d'exposition

- **Tailnet uniquement** (`ingress.yaml`, ingress de classe `tailscale`) :
  `https://moonlight-web.tail6060fb.ts.net`. Rien n'est publié sur Internet,
  il n'y a donc ni ingress Traefik ni TinyAuth.
- **HTTPS fourni par Tailscale** : le certificat `*.ts.net` est valide, ce qui
  fait de la page un *secure context*. WebCodecs, Gamepad API et Keyboard Lock
  y fonctionnent.
- **Transport WebSocket** : certaines machines clientes ont l'UDP
  sortant bloqué, donc le WebRTC est exclu et aucun port UDP n'est exposé.

## Mise en route (une fois)

1. Démarrer une session graphique sur la 815 depuis SSH : `gpu-mode game`.
2. Ouvrir l'UI. Le **premier compte créé devient admin**.
3. Ajouter le PC `10.0.0.15`, puis saisir le PIN affiché dans l'UI Sunshine
   de la 815.
4. Dans les réglages du stream : **Data Transport → Web Sockets**.

## Accès

- **Machines du tailnet** (portable, téléphone) : ouvrir directement
  `https://moonlight-web.tail6060fb.ts.net`.
- **Machine sans client Tailscale natif** : faire tourner un nœud Tailscale
  en mode userspace (par exemple dans un conteneur) avec son proxy HTTP
  (`--outbound-http-proxy-listen`), puis router `*.ts.net` vers ce proxy dans
  le navigateur, avec un fichier PAC ou une extension de proxy.

## Accès direct (hors tailnet)

Sans UDP sortant, le tailnet passe par un relais DERP : 70-100 ms de RTT
mesurés. Pour ces machines, `ingress-public.yaml` publie
`https://vm.valab.top` (port 443, nom volontairement neutre ;
`moonlight.valab.top` reste servi pendant la transition DNS) :

- **Box** : redirection TCP `443` externe → `10.0.0.105:47443` (Service
  `traefik-public`). Rien d'autre n'est redirigé.
- **Traefik** : l'entrypoint `public` ne sert que les routers qui le
  demandent explicitement. `web` et `websecure` sont les entrypoints par
  défaut, donc les autres Ingress du cluster n'y sont pas joignables.
- **Filtrage par IP** : middleware `moonlight-allowlist@file`, lu depuis le
  SealedSecret `traefik-dynamic` (`secrets/sealed/`). Pour changer l'IP
  autorisée, éditer `secrets/clear/traefik-dynamic.yaml` puis le resceller
  (`kubeseal … --cert secrets/clear/sealed-secrets.pem`).
- **TinyAuth** : middleware `security-tinyauth-protect` après l'allowlist.
  L'IP autorisée est l'IP NAT du bureau, partagée par tous les collègues :
  sans login, ils verraient l'UI Moonlight.
- **DNS** : `vm.valab.top` en enregistrement A **DNS only** vers l'IP
  publique de la maison. Pas proxifié, sinon on repasse par Cloudflare.
- **Navigateur** : si le navigateur passe par un proxy vers le tailnet,
  exclure `vm.valab.top` de ce proxy, sinon l'IP source n'est plus celle
  qui est autorisée.
