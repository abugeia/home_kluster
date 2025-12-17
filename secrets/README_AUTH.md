# Gestion des Secrets pour Auth Stack

Ce document explique comment récupérer et configurer les secrets nécessaires pour le déploiement de l'Auth Stack (Pocket ID + TinyAuth).

Les secrets doivent être définis dans `secrets/clear/auth-stack.yaml` avant d'être chiffrés (sealed).

## Liste des Secrets Requis

Le secret Kubernetes `auth-secrets` attend les clés suivantes :

| Clé | Description | Source |
|---|---|---|
| `google-client-id` | Client ID OAuth2 Google | Google Cloud Console |
| `google-client-secret` | Client Secret OAuth2 Google | Google Cloud Console |
| `pocket-client-id` | Client ID OIDC pour TinyAuth | Interface Pocket ID |
| `pocket-client-secret` | Client Secret OIDC pour TinyAuth | Interface Pocket ID |
| `tinyauth-secret` | Clé de signature de session | Généré aléatoirement |

## 1. Google OAuth (pour TinyAuth)

Pour permettre la connexion via Google :

1. Aller sur la [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Créer un nouveau projet (ou utiliser un existant).
3. Aller dans **APIs & Services > Credentials**.
4. Créer un **OAuth Client ID**.
   - **Application Type**: Web application
   - **Name**: `Home Kluster Auth` (exemple)
   - **Authorized JavaScript origins**: `https://auth.valab.top`
   - **Authorized redirect URIs**: `https://auth.valab.top/api/auth/callback/google`
5. Copier le **Client ID** et le **Client Secret** et les placer dans `google-client-id` et `google-client-secret`.

## 2. Pocket ID (L'Annuaire)

Pocket ID agit comme fournisseur d'identité local. Puisqu'il est hébergé dans ce même cluster :

1. **Déployer l'Auth Stack une première fois**.
   - TinyAuth risque d'échouer au démarrage si les secrets Pocket ID sont manquants ou invalides, ce n'est pas grave pour l'instant. L'objectif est de démarrer Pocket ID.
2. Accéder à Pocket ID sur `https://auth-id.valab.top`.
3. Terminer la configuration initiale (création du premier utilisateur admin).
4. Naviguer dans les paramètres OIDC / Applications.
5. Créer une nouvelle application pour **TinyAuth** :
   - **Name**: TinyAuth
   - **Redirect URIs**: `https://auth.valab.top/api/auth/callback/oidc` (ou `pocket` selon la config, vérifier les logs si besoin)
   - **Scopes**: `openid`, `profile`, `email`
6. Copier le **Client ID** et le **Client Secret** générés par Pocket ID.
7. Mettre à jour `pocket-client-id` et `pocket-client-secret` dans vos secrets.
8. Re-sceller les secrets et redéployer (ou restart TinyAuth).

## 3. TinyAuth Secret

Générer une chaîne aléatoire forte pour sécuriser les sessions.

En ligne de commande :
```bash
openssl rand -hex 32
```
Copier le résultat dans `tinyauth-secret`.

## Rappel : Chiffrement

Une fois le fichier `secrets/clear/auth-stack.yaml` rempli :

```bash
cd secrets
./seal_all.sh
```

Cela mettra à jour le fichier dans `secrets/sealed/` qui peut être commité en toute sécurité.
