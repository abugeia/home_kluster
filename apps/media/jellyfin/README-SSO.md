# Configuration SSO Jellyfin avec Pocket ID

Ce guide décrit les étapes pour configurer l'authentification SSO sur Jellyfin avec Pocket ID.

## Prérequis

Le plugin SSO doit être installé dans Jellyfin avant de pouvoir être configuré.

## Étape 1: Installer le Plugin SSO dans Jellyfin

1. Se connecter à Jellyfin : `https://jellyfin.valab.top`
2. Aller dans **Dashboard** → **Plugins** → **Repositories**
3. Cliquer sur **+** pour ajouter un nouveau repository
4. Entrer :
   - **Repository Name** : `SSO Auth`
   - **Repository URL** : `https://raw.githubusercontent.com/9p4/jellyfin-plugin-sso/manifest-release/manifest.json`
5. Cliquer sur **Save**
6. Aller dans **Catalog** et chercher "SSO-Auth"
7. Cliquer sur **Install**
8. **Redémarrer Jellyfin** (Dashboard → Redémarrer)

## Étape 2: Créer un Client OAuth dans Pocket ID

1. Se connecter à Pocket ID : `https://auth-id.valab.top`
2. Aller dans **Applications** ou **Clients**
3. Créer un nouveau client OAuth/OpenID avec :
   - **Nom** : `Jellyfin`
   - **Client Type** : `Confidential`
   - **Redirect URIs** : 
     ```
     https://jellyfin.valab.top/sso/OID/redirect/pocketid
     ```
   - **Scopes** : `openid`, `profile`, `email`
4. **Sauvegarder** et noter :
   - Le **Client ID**
   - Le **Client Secret**

## Étape 3: Obtenir une Clé API Jellyfin

1. Se connecter à Jellyfin avec le compte admin
2. Aller dans **Dashboard** → **API Keys**
3. Cliquer sur **+** pour créer une nouvelle clé
4. Donner un nom : `SSO Setup`
5. **Copier la clé API générée**

## Étape 4: Configurer le Secret Kubernetes

Éditer le fichier `jellyfin-sso-secret.yaml` et remplacer les placeholders :

```bash
# Ouvrir le fichier
nano apps/media/jellyfin/jellyfin-sso-secret.yaml

# Remplacer :
# - PLACEHOLDER_REPLACE_ME (client-id) par le Client ID de Pocket ID
# - PLACEHOLDER_REPLACE_ME (client-secret) par le Client Secret de Pocket ID  
# - PLACEHOLDER_REPLACE_ME (api-key) par la clé API Jellyfin
```

Ou utiliser kubectl pour créer le secret directement :

```bash
kubectl create secret generic jellyfin-sso-credentials \
  --from-literal=client-id='VOTRE_CLIENT_ID' \
  --from-literal=client-secret='VOTRE_CLIENT_SECRET' \
  --from-literal=api-key='VOTRE_API_KEY' \
  --namespace=media \
  --dry-run=client -o yaml | kubectl apply -f -
```

## Étape 5: Appliquer la Configuration

```bash
# Commit et push les changements (si vous avez édité le fichier yaml)
git add apps/media/jellyfin/
git commit -m "feat: Configure SSO for Jellyfin with Pocket ID"
git push

# ArgoCD va automatiquement déployer et exécuter le Job de configuration
# Vérifier le statut :
kubectl get jobs -n media
kubectl logs -n media job/jellyfin-sso-setup
```

## Étape 6: Tester la Connexion SSO

1. Ouvrir `https://jellyfin.valab.top` dans un **navigateur privé**
2. Sur la page de login, vous devriez voir un bouton **"Sign in with pocketid"**
3. Cliquer dessus → redirection vers Pocket ID
4. Se connecter avec vos identifiants Pocket ID
5. Accepter les permissions
6. Vous devriez être redirigé vers Jellyfin avec une session active

## Vérification de la Configuration

Pour vérifier que la configuration SSO est active :

```bash
# Récupérer la clé API depuis le secret
API_KEY=$(kubectl get secret jellyfin-sso-credentials -n media -o jsonpath='{.data.api-key}' | base64 -d)

# Vérifier la configuration SSO
curl "https://jellyfin.valab.top/sso/OID/Get?api_key=${API_KEY}"
```

Vous devriez voir la configuration JSON du provider `pocketid`.

## Reconfigurer le SSO

Si vous devez modifier la configuration SSO :

```bash
# Supprimer le Job existant
kubectl delete job jellyfin-sso-setup -n media

# Créer un nouveau Job manuellement
kubectl create job --from=cronjob/jellyfin-sso-setup jellyfin-sso-setup-manual -n media

# Ou faire un sync ArgoCD pour recréer le Job
```

## Troubleshooting

### Le bouton SSO n'apparaît pas

- Vérifier que le plugin est bien installé et activé dans Dashboard → Plugins
- Vérifier les logs du Job : `kubectl logs -n media job/jellyfin-sso-setup`
- Vérifier les logs de Jellyfin : `kubectl logs -n media deployment/jellyfin`

### Erreur lors de la redirection

- Vérifier que l'URI de redirection dans Pocket ID est exactement : `https://jellyfin.valab.top/sso/OID/redirect/pocketid`
- Vérifier que les credentials dans le Secret sont corrects

### L'utilisateur SSO n'a pas accès aux médias

- Par défaut, `enableAuthorization` est à `false`, donc les permissions ne sont pas modifiées
- Aller dans Dashboard → Users et configurer les permissions manuellement pour l'utilisateur SSO

## Rollback vers TinyAuth

Si vous souhaitez revenir à TinyAuth :

1. Éditer `apps/media/jellyfin/values.yaml`
2. Décommenter la ligne TinyAuth :
   ```yaml
   traefik.ingress.kubernetes.io/router.middlewares: security-tinyauth-protect@kubernetescrd
   ```
3. Désactiver le plugin SSO dans Jellyfin Dashboard
4. Commit et push les changements
