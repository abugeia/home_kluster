# Configuration SSO Jellyfin avec Pocket ID

Ce guide décrit les étapes pour configurer l'authentification SSO sur Jellyfin avec Pocket ID.

## Plugin et version de Jellyfin

- **Jellyfin 12.x** (chart 3.4.0+). Le plugin d'origine,
  [9p4/jellyfin-plugin-sso](https://github.com/9p4/jellyfin-plugin-sso), est
  archivé et s'arrête à la 10.11. On utilise son fork maintenu,
  [K0lin/jellyfin-plugin-sso](https://github.com/K0lin/jellyfin-plugin-sso),
  version **5.1.x** : même GUID, même API (`/sso/OID/...`), même URL de
  redirection côté Pocket ID.
- **Limite de la 5.1** : le SSO ne marche que dans l'interface web et les
  clients qui gèrent [Quick Connect](https://jellyfin.org/docs/general/server/quick-connect)
  (sur une TV : code à valider depuis le navigateur).

## Étape 1: Plugin SSO — automatique

Rien à faire à la main : le job `jellyfin-sso-setup` (étape 5) déclare le dépôt
de plugins K0lin, installe « SSO Authentication » à la version fixée dans le
job (`PLUGIN_VERSION`), redémarre Jellyfin pour le charger, puis configure le
fournisseur `pocketid`. Il est idempotent : le relancer ne réinstalle rien si
le plugin est déjà à la bonne version.

Pour monter de version le plugin : changer `PLUGIN_VERSION` dans
`jellyfin-sso-setup-job.yaml` (versions publiées :
`https://raw.githubusercontent.com/k0lin/jellyfin-plugin-sso/manifest-release/manifest.json`),
puis relancer le job.

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

## Étape 5: Lancer le job de configuration

Le CronJob est suspendu : on le lance à la main, avec un accès admin au
cluster. Jellyfin doit être réveillé (Sablier) : ouvrir
`https://jellyfin.valab.top` juste avant, sinon le job abandonne après 10 min.

```bash
kubectl create job --from=cronjob/jellyfin-sso-setup jellyfin-sso-run -n media
kubectl logs -n media job/jellyfin-sso-run -f
```

Le journal doit se terminer par `SSO configuré. Fournisseurs OpenID : ['pocketid']`.

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
# api_key en query n'est plus accepté (autorisation « legacy » désactivée)
curl -H "Authorization: MediaBrowser Token=\"${API_KEY}\"" https://jellyfin.valab.top/sso/OID/Get
```

Vous devriez voir la configuration JSON du provider `pocketid`.

## Reconfigurer le SSO

Modifier le corps envoyé à `/sso/OID/Add/pocketid` dans
`jellyfin-sso-setup-job.yaml`, merger, puis relancer le job (étape 5) : `Add`
écrase la configuration existante. Supprimer d'abord l'ancien job s'il porte
le même nom (`kubectl delete job jellyfin-sso-run -n media`).

### Bouton de connexion sur la page de login


### 1. Accéder aux Paramètres de Branding

1. Se connecter à Jellyfin avec un compte administrateur
2. Aller dans **Dashboard** → **General** → **Branding**

### 2. Ajouter le Bouton HTML

Dans le champ **"Login disclaimer"**, ajoutez ce code :

```html
<form action="https://jellyfin.valab.top/sso/OID/start/pocketid"> 
  <button class="raised block emby-button button-submit">Se connecter avec Pocket ID</button> 
</form>
```

> **Note** : Remplacez `pocketid` par le nom de votre provider si différent.

### 3. Ajouter le CSS Personnalisé

Dans le champ **"Custom CSS code"**, ajoutez ce code :

```css
a.raised.emby-button { 
  padding: 0.9em 1em; 
  color: inherit !important; 
} 
.disclaimerContainer { 
  display: block; 
}
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
