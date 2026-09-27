# Moonlight Web : jouer sur `ai-gaming` (815) depuis un navigateur

[`moonlight-web-stream`](https://github.com/MrCreativ3001/moonlight-web-stream)
est un client Moonlight qui tourne côté serveur. Il appaire Sunshine (VM 815,
`10.0.0.15`) et renvoie le flux au navigateur. Il sert au **poste du boulot**,
qui n'a ni Moonlight-Qt ni Tailscale sous Windows mais a Tailscale dans WSL.
Les machines perso gardent le client Moonlight natif sur le tailnet.

Étude complète et mesures : `TODO_MOONLIGHT_WEB.md` du repo `infra_proxmox`.

## Choix d'exposition

- **Tailnet uniquement** (`service.yaml`, opérateur Tailscale) : rien n'est
  publié sur Internet, et il n'y a donc ni ingress, ni TinyAuth, ni certificat.
- **Pas d'HTTPS nécessaire** : le navigateur joint le service en
  `http://localhost`, et localhost compte comme un *secure context*. WebCodecs,
  Gamepad API et Keyboard Lock y fonctionnent donc.
- **Transport WebSocket** : l'UDP ne sort pas du réseau du boulot, donc le
  WebRTC est exclu et aucun port UDP n'est exposé.

## Mise en route (une fois)

1. Démarrer une session graphique sur la 815 depuis SSH : `gpu-mode game`.
2. Ouvrir l'UI (cf. ci-dessous). Le **premier compte créé devient admin**.
3. Ajouter le PC `10.0.0.15`, puis saisir le PIN affiché dans l'UI Sunshine
   de la 815.
4. Dans les réglages du stream : **Data Transport → Web Sockets**.

## Accès depuis le poste du boulot

MagicDNS ne résout pas dans WSL, il faut donc l'IP tailnet du service :

```sh
tailscale status | grep moonlight-web            # → 100.x.y.z
socat TCP-LISTEN:8080,bind=127.0.0.1,fork,reuseaddr TCP:100.x.y.z:8080
```

Puis ouvrir `http://localhost:8080` dans le navigateur Windows (localhost
forwarding de WSL2).
