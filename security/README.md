
### Sealed secrets
install du client kubeseal :
```
https://github.com/bitnami-labs/sealed-secrets?tab=readme-ov-file#kubeseal
```
sur windows le binaire est sur [gh](https://github.com/bitnami-labs/sealed-secrets/releases)

Récupération de la public key :
```
kubeseal --fetch-cert --controller-name=sealed-secrets --controller-namespace=security > sealed-secrets.pem

```
Création d'un secret.yaml (clear) :
```
kubectl create secret generic testsecret \
  --from-literal=username=admin \
  --from-literal=password=SuperSecret123 \
  -n default \
  -o yaml --dry-run=client > secrets/clear/secret.yaml
```
Création d'un sealedsecret à partir de secret.yaml :
```
kubeseal \
--controller-name=sealed-secrets \
--controller-namespace=security \
--format=yaml \
--cert=secrets/clear/sealed-secrets.pem \ 
< secrets/clear/secret.yaml >> secrets/sealedsecret.yaml

```
flag pour le cert
`--cert=secrets/clear/sealed-secret.pem`


## Harbor

Harbor est le registre de conteneurs privé du cluster. Deux secrets sont nécessaires pour son bon fonctionnement :

### Secret pg-harbor (Base de données PostgreSQL)

Le secret `pg-harbor` contient les credentials pour la base de données PostgreSQL utilisée par Harbor :
- **Utilité** : Stockage des métadonnées Harbor (utilisateurs, projets, images, etc.)
- **Contenu** : nom d'utilisateur et mot de passe PostgreSQL
- **Génération** : Utiliser le script existant dans `secrets/` ou créer manuellement puis sceller avec kubeseal

### Secret registry-secret (Accès au registre)

Le secret `registry-secret` permet aux pods Kubernetes de télécharger des images depuis Harbor :

#### 1. Créer un compte robot dans Harbor
1. Se connecter à Harbor (`https://harbor.cagou.ovh`)
2. Aller dans **Administration** → **Robot Accounts**
3. Créer un nouveau robot avec :
   - **Name** : `cluster-sa`
   - **Permissions** : `Pull` sur les projets nécessaires
   - **Expiration** : selon vos besoins

#### 2. Configurer le fichier robot JSON
Créer/mettre à jour `secrets/clear/robot$cluster-sa.json` :
```json
{
    "name": "robot$cluster-sa",
    "secret": "VOTRE_TOKEN_ROBOT_HARBOR"
}
```

#### 3. Générer et sceller le secret
```bash
# Générer le secret Base64
cd secrets/
python registry_b64_create.py

# Sceller le secret
kubeseal \
--controller-name=sealed-secrets \
--controller-namespace=security \
--format=yaml \
--cert=sealed-secrets.pem \
< clear/registry-secret.yaml > sealed/registry-secret.yaml

# Appliquer le secret scellé
kubectl apply -f sealed/registry-secret.yaml
```

#### 4. Déploiement multi-namespace
⚠️ **Important** : Les secrets sont liés à un namespace spécifique. Si vous déployez des apps dans plusieurs namespaces, vous devez créer le secret dans chaque namespace :

```bash
# Exemple pour le namespace 'datalab'
kubectl create secret docker-registry harbor-creds \
  --docker-server=harbor.cagou.ovh \
  --docker-username=robot$cluster-sa \
  --docker-password=VOTRE_TOKEN_ROBOT \
  --namespace=datalab \
  -o yaml --dry-run=client > clear/registry-secret-datalab.yaml

# Sceller le secret
kubeseal --cert=sealed-secrets.pem \
< clear/registry-secret-datalab.yaml \
> sealed/registry-secret-datalab.yaml

# Appliquer
kubectl apply -f sealed/registry-secret-datalab.yaml
```

#### 5. Utilisation dans les pods
Le secret `harbor-creds` est utilisé automatiquement par Kubernetes pour l'authentification auprès de Harbor lors du pull d'images privées.