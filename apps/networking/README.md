# Architecture Réseau et Sécurité SSL

Ce document explique les choix structurants pour l'accès aux applications et la gestion du HTTPS.

## 1. Le Double-TLS (Pourquoi deux certificats ?)

L'infrastructure utilise une stratégie hybride pour garantir un "Verrou Vert" (HTTPS valide) que l'on soit chez soi ou en voyage.

### Accès Extérieur (Cloudflare Tunnel)
- **Trajet** : Utilisateur → Internet → Cloudflare (Edge) → Tunnel → Traefik.
- **Certificat** : Fourni par **Cloudflare**. Il sécurise la connexion entre l'utilisateur et le réseau Cloudflare.
- **Avantage** : Rien à gérer, Cloudflare s'occupe du SSL.

### Accès Local (cert-manager + AdGuard)
- **Trajet** : Utilisateur → WiFi Local → IP Traefik (10.0.0.101).
- **Certificat** : Fourni par **cert-manager** (via Let's Encrypt).
- **Pourquoi ?** : En local, tu ne passes pas par Cloudflare. Pour éviter l'erreur "Danger, site non sécurisé", ton serveur (Traefik) doit posséder son propre certificat valide pour `valab.top`.
- **DNS Challenge** : cert-manager utilise ton Token Cloudflare pour prouver à Let's Encrypt que tu possèdes le domaine, sans avoir besoin d'ouvrir de port sur ta box.

---

## 2. MetalLB (Le Load Balancer)

Dans un cluster Kubernetes standard (Cloud), les IPs publiques sont fournies par le fournisseur (AWS, Google). Dans un Homelab, le cluster "flotte" dans ton réseau local.

### Son Rôle
**MetalLB** donne une identité physique à tes services Kubernetes sur ton réseau domestique.
- Sans MetalLB : Traefik n'aurait qu'une IP interne (`10.42.x.x`) invisible depuis ton PC.
- Avec MetalLB : Il réserve l'IP **`10.0.0.101`** de ton réseau local et la "donne" à Traefik.

### Pourquoi une IP fixe (`10.0.0.101`) ?
1. **AdGuard** : Pour que tes réécritures DNS (`*.valab.top → 10.0.0.101`) fonctionnent toujours.
2. **Tunnel Cloudflare** : Le tunnel sait exactement où envoyer le trafic.
3. **Stabilité** : Même si tu redémarres ton cluster, Traefik retrouvera toujours la même adresse.

---

## 3. Maintenance SSL

Les certificats sont stockés dans des **Secrets Kubernetes** (ex: `syncthing-tls`). 
- **Migration** : Nous avons migré de la gestion interne de Traefik vers `cert-manager` car les Secrets sont plus stables, plus faciles à sauvegarder, et ne dépendent pas des permissions de fichiers sur ton partage NFS.
