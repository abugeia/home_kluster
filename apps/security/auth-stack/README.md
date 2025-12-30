# Configuration des Applications dans PocketID

Pour ajouter une nouvelle application (comme Harbor ou ArgoCD) dans PocketID, suivez cette procédure.

## Informations de connexion
L'interface de gestion PocketID est accessible à l'adresse suivante :
👉 **[https://auth-id.valab.top](https://auth-id.valab.top)**

## Étapes de création d'une application
1. Connectez-vous avec votre compte administrateur.
2. Allez dans la section **Aplications** (ou Client OIDC).
3. Cliquez sur **Create Application**.
4. Remplissez les informations de base :
   - **Name :** Nom de l'application (ex: `Harbor`)
   - **Redirect URI :** L'URL de callback de l'application.
     - Pour Harbor : `https://harbor.valab.top/c/oidc/callback`
5. Notez bien le **Client ID** et le **Client Secret** générés pour les reporter dans la configuration de l'application cible.

## Scopes recommandés
Pour la plupart des intégrations, utilisez les scopes : `openid`, `profile`, `email`.
