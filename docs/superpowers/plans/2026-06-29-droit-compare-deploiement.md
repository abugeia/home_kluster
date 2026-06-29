# Déploiement `droit_compare` (façon vfnc) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Déployer l'application `droit_compare` sur le cluster via GitOps (ArgoCD + Kustomize), sur le modèle de `vfnc`, avec image unique (backend servant frontend + API), Gemini/Vertex, basic auth, et secrets scellés.

**Architecture:** Une image Docker unique (backend FastAPI servant le frontend statique sous `/` et l'API sous `/api/*`) buildée par GitHub Actions et poussée sur Harbor. Côté `home_kluster`, un dossier Kustomize `apps/dinum/droit_compare/` (db StatefulSet, api Deployment, ingress, middleware, ConfigMap few-shot), une Application ArgoCD, une entrée argocd-image-updater, et 4 SealedSecrets.

**Tech Stack:** Docker (python:3.12-slim), GitHub Actions, Kustomize, ArgoCD, Traefik (Ingress + Middleware), cert-manager (letsencrypt), Bitnami SealedSecrets (kubeseal), PostgreSQL 18, FastAPI, Gemini via Vertex AI.

## Global Constraints

- Deux repos distincts :
  - `droit_compare` : `/home/ubuntu/pro/droit_compare` (remote `pro:antoinebugeia/droit_compare`)
  - `home_kluster` : `/home/ubuntu/perso/home_kluster` (repo courant)
- Registry : `harbor.valab.top`, projet `prod`. Image unique : `harbor.valab.top/prod/droit-compare`.
- Namespace cible : `dinum`. Host : `droit-compare.valab.top`.
- Messages de commit : **jamais** de trailer `Co-Authored-By` ni footer `Generated with`.
- Ne pas committer sur `main` directement : créer une branche par repo avant toute modification.
- Valeurs de config (issues du `.env` de prod, à conserver verbatim) :
  - `LLM_PROVIDER=gemini`, `LLM_MODEL=gemini-3.5-flash`, `LLM_MODEL_CHEAP=gemini-3.1-flash-lite`
  - `GEMINI_USE_VERTEX=true`, `GOOGLE_CLOUD_PROJECT=prj-dinum-exp-p-bq-608d`, `GOOGLE_CLOUD_LOCATION=global`
  - `GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-sa.json`
  - `COMPARISON_MODE=distinct`, `FEWSHOT_REFERENCE_DOC=/app/fewshot_reference.md`
  - `DRAFTING_LIMIT=12`, `DRAFTING_CONCURRENCY=5`
- Chemins runtime exigés par le code (à respecter dans l'image) :
  - frontend → `/app/frontend` (`main.py` : `Path(__file__).resolve().parents[2] / "frontend"`)
  - prompt.md → `/app/prompt.md` (`llm/sections/base.py` : `parents[4] / "prompt.md"`)
- Health endpoint : `GET /api/health` (`backend/app/main.py:35`).
- Cert de scellement présent : `secrets/clear/sealed-secrets.pem`. Sceller via `secrets/seal_all.sh` (controller `sealed-secrets` / ns `security`).

---

## File Structure

**Repo `droit_compare`** (branche `feat/deploy-harbor`) :
- Create `Dockerfile.prod` — image prod auto-suffisante (backend + frontend + prompt.md).
- Create `.github/workflows/deploy_harbor_valab.yaml` — CI build & push Harbor.

**Repo `home_kluster`** (branche `feat/droit-compare`) :
- Create `apps/dinum/droit_compare/db.yaml` — Service headless + StatefulSet Postgres.
- Create `apps/dinum/droit_compare/api.yaml` — Deployment + Service backend.
- Create `apps/dinum/droit_compare/middleware.yaml` — Middleware basicauth.
- Create `apps/dinum/droit_compare/ingress.yaml` — Ingress unique.
- Create `apps/dinum/droit_compare/kustomization.yaml` — kustomization + configMapGenerator + images.
- Create `apps/dinum/droit_compare/fewshot_reference.md` — copie du doc few-shot (clair).
- Create `apps/dinum/droit_compare/.argocd-source-droit-compare.yaml` — override digest (placeholder initial).
- Create `argocd/apps/droit-compare.yaml` — Application ArgoCD.
- Modify `apps/tools/argocd-image-updater/values.yaml` — ajout CR ImageUpdater droit-compare.
- Create `secrets/clear/droit-compare-db.yaml`, `droit-compare-secrets.yaml`, `droit-compare-gcp-sa.yaml`, `droit-compare-basicauth.yaml` (gitignorés).
- Create `secrets/sealed/droit-compare-db.yaml`, `droit-compare-secrets.yaml`, `droit-compare-gcp-sa.yaml`, `droit-compare-basicauth.yaml` (committés).

---

## Task 1: Image prod `droit_compare` (Dockerfile.prod)

**Files:**
- Create: `/home/ubuntu/pro/droit_compare/Dockerfile.prod`

**Interfaces:**
- Produces: image dont l'entrypoint sert le backend sur `:8000`, frontend baké en `/app/frontend`, `prompt.md` en `/app/prompt.md`, `PYTHONPATH=/app/backend`.

- [ ] **Step 1: Créer la branche dans le repo droit_compare**

```bash
cd /home/ubuntu/pro/droit_compare
git fetch && git switch -c feat/deploy-harbor
```

- [ ] **Step 2: Écrire `Dockerfile.prod`**

Create `/home/ubuntu/pro/droit_compare/Dockerfile.prod` :

```dockerfile
# Image de production auto-suffisante : le backend FastAPI sert à la fois
# l'API (/api/*) et le frontend statique (/). Contexte de build = racine du repo.
# Le Dockerfile de dev (backend/Dockerfile, contexte ./backend) reste inchangé.
FROM python:3.12-slim

WORKDIR /app

# Dépendances Python (PyMuPDF fournit des wheels ; rien d'autre requis).
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Code + assets bakés. Chemins alignés sur le code :
#   frontend -> /app/frontend (main.py: parents[2]/frontend)
#   prompt.md -> /app/prompt.md (llm/sections/base.py: parents[4]/prompt.md)
COPY backend/ backend/
COPY frontend/ frontend/
COPY prompt.md prompt.md

ENV PYTHONPATH=/app/backend
WORKDIR /app/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Builder l'image localement pour vérifier**

Run:
```bash
cd /home/ubuntu/pro/droit_compare
docker build -f Dockerfile.prod -t droit-compare:test .
```
Expected: build réussi (PASS). En cas d'échec de COPY, vérifier que `frontend/` et `prompt.md` sont bien à la racine.

- [ ] **Step 4: Vérifier les chemins bakés dans l'image**

Run:
```bash
docker run --rm droit-compare:test sh -c "ls /app/frontend/index.html /app/prompt.md && python -c 'import app.main'"
```
Expected: les deux fichiers listés sans erreur, import du module OK (PASS). Une erreur DB éventuelle à l'import est acceptable tant que le module se charge ; sinon ignorer (l'app ne se connecte qu'au démarrage uvicorn).

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/pro/droit_compare
git add Dockerfile.prod
git commit -m "build: Dockerfile.prod (image unique backend+frontend pour Harbor)"
```

---

## Task 2: Workflow CI Harbor (droit_compare)

**Files:**
- Create: `/home/ubuntu/pro/droit_compare/.github/workflows/deploy_harbor_valab.yaml`

**Interfaces:**
- Consumes: `Dockerfile.prod` (Task 1), secrets repo `ROBOT_VALAB_USERNAME` / `ROBOT_VALAB_TOKEN`.
- Produces: image `harbor.valab.top/prod/droit-compare` tags `main`, `sha-<sha>`, `latest`.

- [ ] **Step 1: Écrire le workflow**

Create `/home/ubuntu/pro/droit_compare/.github/workflows/deploy_harbor_valab.yaml` :

```yaml
name: Deploy to Harbor Valab (Automatic)

on:
  push:
    branches: [ "main" ]
  workflow_dispatch:

env:
  HARBOR_REGISTRY: harbor.valab.top
  HARBOR_PROJECT: prod

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        include:
          - image: droit-compare
            context: .
            file: ./Dockerfile.prod

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Harbor Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.HARBOR_REGISTRY }}
          username: ${{ secrets.ROBOT_VALAB_USERNAME }}
          password: ${{ secrets.ROBOT_VALAB_TOKEN }}

      - name: Extract Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.HARBOR_REGISTRY }}/${{ env.HARBOR_PROJECT }}/${{ matrix.image }}
          tags: |
            type=ref,event=branch
            type=sha,prefix=sha-
            type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}

      - name: Build and push ${{ matrix.image }}
        uses: docker/build-push-action@v5
        with:
          context: ${{ matrix.context }}
          file: ${{ matrix.file }}
          push: true
          platforms: linux/amd64,linux/arm64
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha,scope=${{ matrix.image }}
          cache-to: type=gha,mode=max,scope=${{ matrix.image }}
```

- [ ] **Step 2: Valider la syntaxe YAML**

Run:
```bash
cd /home/ubuntu/pro/droit_compare
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/deploy_harbor_valab.yaml')); print('YAML OK')"
```
Expected: `YAML OK` (PASS).

- [ ] **Step 3: Commit**

```bash
cd /home/ubuntu/pro/droit_compare
git add .github/workflows/deploy_harbor_valab.yaml
git commit -m "ci: build & push image droit-compare vers Harbor Valab"
```

- [ ] **Step 4: (Optionnel, validé avec l'utilisateur) Pousser la branche et ouvrir la PR**

Le push sur `main` déclenche le build. Coordination avec l'utilisateur avant merge (le premier build alimentera le digest de la Task 8).

```bash
cd /home/ubuntu/pro/droit_compare
git push -u origin feat/deploy-harbor
```

---

## Task 3: Manifests Kustomize — DB + API (home_kluster)

**Files:**
- Create: `/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/db.yaml`
- Create: `/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/api.yaml`

**Interfaces:**
- Consumes: SealedSecrets `droit-compare-db` (clés `POSTGRES_USER/PASSWORD/DB`, `DATABASE_URL`), `droit-compare-secrets`, `droit-compare-gcp-sa` (clé `gcp-sa.json`) ; ConfigMap `droit-compare-fewshot` (clé `fewshot_reference.md`) — créés Tasks 5/6.
- Produces: Service `droit-compare-db:5432` (headless), Service `droit-compare-api:8000`.

- [ ] **Step 1: Créer la branche dans home_kluster**

```bash
cd /home/ubuntu/perso/home_kluster
git fetch && git switch -c feat/droit-compare
mkdir -p apps/dinum/droit_compare
```

- [ ] **Step 2: Écrire `db.yaml`**

Create `/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/db.yaml` :

```yaml
apiVersion: v1
kind: Service
metadata:
  name: droit-compare-db
  namespace: dinum
  labels:
    app.kubernetes.io/name: droit-compare-db
spec:
  clusterIP: None
  selector:
    app.kubernetes.io/name: droit-compare-db
  ports:
    - name: postgres
      port: 5432
      targetPort: 5432
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: droit-compare-db
  namespace: dinum
  labels:
    app.kubernetes.io/name: droit-compare-db
spec:
  serviceName: droit-compare-db
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: droit-compare-db
  template:
    metadata:
      labels:
        app.kubernetes.io/name: droit-compare-db
    spec:
      containers:
        - name: postgres
          image: postgres:18-alpine
          envFrom:
            - secretRef:
                name: droit-compare-db
          env:
            # Sous-répertoire pour éviter les soucis de propriété sur la racine du volume.
            - name: PGDATA
              value: /var/lib/postgresql/data/pgdata
          ports:
            - name: postgres
              containerPort: 5432
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
          readinessProbe:
            exec:
              command: ["sh", "-c", "pg_isready -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\""]
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            exec:
              command: ["sh", "-c", "pg_isready -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\""]
            initialDelaySeconds: 30
            periodSeconds: 30
          resources:
            requests:
              memory: "256Mi"
              cpu: "100m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: local-path
        resources:
          requests:
            storage: 5Gi
```

- [ ] **Step 3: Écrire `api.yaml`**

Create `/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/api.yaml` :

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: droit-compare-api
  namespace: dinum
  labels:
    app.kubernetes.io/name: droit-compare-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: droit-compare-api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: droit-compare-api
    spec:
      imagePullSecrets:
        - name: harbor-cicd-secret # répliqué par Reflector (label ns replicate-harbor-cicd)
      containers:
        - name: api
          image: harbor.valab.top/prod/droit-compare:main
          imagePullPolicy: Always
          envFrom:
            - secretRef:
                name: droit-compare-db       # DATABASE_URL (+ POSTGRES_* ignorés par le backend)
            - secretRef:
                name: droit-compare-secrets   # LEGIFRANCE_* + clés LLM (vides en Vertex)
          env:
            - name: LLM_PROVIDER
              value: "gemini"
            - name: LLM_MODEL
              value: "gemini-3.5-flash"
            - name: LLM_MODEL_CHEAP
              value: "gemini-3.1-flash-lite"
            - name: GEMINI_USE_VERTEX
              value: "true"
            - name: GOOGLE_CLOUD_PROJECT
              value: "prj-dinum-exp-p-bq-608d"
            - name: GOOGLE_CLOUD_LOCATION
              value: "global"
            - name: GOOGLE_APPLICATION_CREDENTIALS
              value: "/secrets/gcp-sa.json"
            - name: COMPARISON_MODE
              value: "distinct"
            - name: FEWSHOT_REFERENCE_DOC
              value: "/app/fewshot_reference.md"
            - name: DRAFTING_LIMIT
              value: "12"
            - name: DRAFTING_CONCURRENCY
              value: "5"
          ports:
            - name: http
              containerPort: 8000
          readinessProbe:
            httpGet:
              path: /api/health
              port: http
            initialDelaySeconds: 5
            periodSeconds: 15
          livenessProbe:
            httpGet:
              path: /api/health
              port: http
            initialDelaySeconds: 15
            periodSeconds: 30
          resources:
            requests:
              memory: "128Mi"
              cpu: "50m"
            limits:
              memory: "512Mi"
              cpu: "1000m"
          volumeMounts:
            - name: gcp-sa
              mountPath: /secrets
              readOnly: true
            - name: fewshot
              mountPath: /app/fewshot_reference.md
              subPath: fewshot_reference.md
              readOnly: true
      volumes:
        - name: gcp-sa
          secret:
            secretName: droit-compare-gcp-sa
            items:
              - key: gcp-sa.json
                path: gcp-sa.json
        - name: fewshot
          configMap:
            name: droit-compare-fewshot
---
apiVersion: v1
kind: Service
metadata:
  name: droit-compare-api
  namespace: dinum
  labels:
    app.kubernetes.io/name: droit-compare-api
spec:
  selector:
    app.kubernetes.io/name: droit-compare-api
  ports:
    - name: http
      port: 8000
      targetPort: http
```

- [ ] **Step 4: Commit (validation kustomize en Task 7)**

```bash
cd /home/ubuntu/perso/home_kluster
git add apps/dinum/droit_compare/db.yaml apps/dinum/droit_compare/api.yaml
git commit -m "feat(droit-compare): manifests db (postgres) et api (backend unique)"
```

---

## Task 4: Ingress + Middleware (home_kluster)

**Files:**
- Create: `/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/middleware.yaml`
- Create: `/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/ingress.yaml`

**Interfaces:**
- Consumes: Service `droit-compare-api:8000` (Task 3), SealedSecret `droit-compare-basicauth` (clé `users`, Task 6).
- Produces: Middleware `dinum-droit-compare-basicauth@kubernetescrd`, Ingress host `droit-compare.valab.top`.

- [ ] **Step 1: Écrire `middleware.yaml`**

Create `/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/middleware.yaml` :

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: droit-compare-basicauth
  namespace: dinum
spec:
  basicAuth:
    # Secret "droit-compare-basicauth" (clé "users", format htpasswd) fourni via
    # SealedSecret -> secrets/sealed/droit-compare-basicauth.yaml
    secret: droit-compare-basicauth
    realm: "droit-compare - acces restreint"
```

- [ ] **Step 2: Écrire `ingress.yaml`**

Le backend sert frontend (`/`) ET API (`/api/*`) : un seul Ingress, une seule règle, basic auth global. Pas de stripprefix.

Create `/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/ingress.yaml` :

```yaml
# Un seul backend sert le frontend (/) et l'API (/api/*) : un seul Ingress suffit.
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: droit-compare
  namespace: dinum
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web,websecure
    traefik.ingress.kubernetes.io/router.middlewares: dinum-droit-compare-basicauth@kubernetescrd
    cert-manager.io/cluster-issuer: letsencrypt
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - droit-compare.valab.top
      secretName: droit-compare-tls
  rules:
    - host: droit-compare.valab.top
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: droit-compare-api
                port:
                  number: 8000
```

- [ ] **Step 3: Commit**

```bash
cd /home/ubuntu/perso/home_kluster
git add apps/dinum/droit_compare/middleware.yaml apps/dinum/droit_compare/ingress.yaml
git commit -m "feat(droit-compare): ingress unique + middleware basicauth"
```

---

## Task 5: Kustomization + doc few-shot + source override (home_kluster)

**Files:**
- Create: `/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/fewshot_reference.md`
- Create: `/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/kustomization.yaml`
- Create: `/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/.argocd-source-droit-compare.yaml`

**Interfaces:**
- Produces: ConfigMap `droit-compare-fewshot` (nom stable, sans suffixe de hash) ; déclaration `images: harbor.valab.top/prod/droit-compare:main`.

- [ ] **Step 1: Copier le doc few-shot (clair) dans le dossier**

Run:
```bash
cp "/home/ubuntu/pro/droit_compare/2026.02.11_Tableau de travail APLP_Réforme CAC.md" \
   "/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/fewshot_reference.md"
ls -la "/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/fewshot_reference.md"
```
Expected: fichier présent (~176 Ko). Si absent côté droit_compare, demander le fichier à l'utilisateur.

- [ ] **Step 2: Écrire `kustomization.yaml`**

Create `/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/kustomization.yaml` :

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: dinum
resources:
  - db.yaml
  - api.yaml
  - middleware.yaml
  - ingress.yaml
# ConfigMap du document de travail few-shot (monté en /app/fewshot_reference.md).
# Nom stable (pas de suffixe de hash) pour que le mount de api.yaml reste valide.
configMapGenerator:
  - name: droit-compare-fewshot
    files:
      - fewshot_reference.md
generatorOptions:
  disableNameSuffixHash: true
# Image surveillée par argocd-image-updater (write-back kustomize).
# Le digest courant du tag :main est inscrit via .argocd-source-droit-compare.yaml.
images:
  - name: harbor.valab.top/prod/droit-compare
    newTag: main
```

- [ ] **Step 3: Écrire le fichier de source override (placeholder initial)**

Tant que le premier build n'a pas eu lieu, on n'a pas de digest. ArgoCD utilise alors `newTag: main` du kustomization. L'image-updater écrira le digest ici après le premier build. Initialiser avec un fichier vide valide.

Create `/home/ubuntu/perso/home_kluster/apps/dinum/droit_compare/.argocd-source-droit-compare.yaml` :

```yaml
kustomize:
  images: []
```

- [ ] **Step 4: Valider le build kustomize**

Run:
```bash
cd /home/ubuntu/perso/home_kluster
kubectl kustomize apps/dinum/droit_compare > /tmp/dc-render.yaml && \
  grep -c "kind:" /tmp/dc-render.yaml && \
  grep -E "name: droit-compare-fewshot|image: harbor.valab.top/prod/droit-compare" /tmp/dc-render.yaml
```
Expected: build réussi, ConfigMap `droit-compare-fewshot` présent **sans suffixe**, image taggée `:main` (PASS).

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/perso/home_kluster
git add apps/dinum/droit_compare/kustomization.yaml \
        apps/dinum/droit_compare/fewshot_reference.md \
        apps/dinum/droit_compare/.argocd-source-droit-compare.yaml
git commit -m "feat(droit-compare): kustomization + configmap few-shot + source override"
```

---

## Task 6: Secrets — manifests clairs + scellement (home_kluster)

**Files:**
- Create: `secrets/clear/droit-compare-db.yaml` (gitignoré)
- Create: `secrets/clear/droit-compare-secrets.yaml` (gitignoré)
- Create: `secrets/clear/droit-compare-gcp-sa.yaml` (gitignoré)
- Create: `secrets/clear/droit-compare-basicauth.yaml` (gitignoré)
- Create (via seal): `secrets/sealed/droit-compare-db.yaml`, `droit-compare-secrets.yaml`, `droit-compare-gcp-sa.yaml`, `droit-compare-basicauth.yaml`

**Interfaces:**
- Produces: 4 Secrets Opaque dans le ns `dinum`, consommés par Tasks 3 et 4.

- [ ] **Step 1: Générer les identifiants DB et la chaîne de connexion**

Run:
```bash
cd /home/ubuntu/perso/home_kluster
DC_DB_USER=droit
DC_DB_PASS=$(openssl rand -hex 16)
echo "user=$DC_DB_USER pass=$DC_DB_PASS"
```
Conserver ces valeurs pour le step suivant. `DATABASE_URL=postgresql+psycopg://$DC_DB_USER:$DC_DB_PASS@droit-compare-db:5432/droit_compare`.

- [ ] **Step 2: Écrire `secrets/clear/droit-compare-db.yaml`**

Remplacer `<PASS>` par la valeur générée. Le backend lit `DATABASE_URL` ; le conteneur Postgres lit `POSTGRES_*`.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: droit-compare-db
  namespace: dinum
type: Opaque
stringData:
  POSTGRES_USER: droit
  POSTGRES_PASSWORD: "<PASS>"
  POSTGRES_DB: droit_compare
  DATABASE_URL: "postgresql+psycopg://droit:<PASS>@droit-compare-db:5432/droit_compare"
```

- [ ] **Step 3: Écrire `secrets/clear/droit-compare-secrets.yaml`**

Récupérer `LEGIFRANCE_CLIENT_ID` et `LEGIFRANCE_CLIENT_SECRET` depuis le `.env` de droit_compare :
```bash
grep -E "^LEGIFRANCE_" /home/ubuntu/pro/droit_compare/.env
```
Puis créer le fichier (clés LLM laissées vides : Vertex n'en a pas besoin) :

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: droit-compare-secrets
  namespace: dinum
type: Opaque
stringData:
  LEGIFRANCE_CLIENT_ID: "<depuis .env>"
  LEGIFRANCE_CLIENT_SECRET: "<depuis .env>"
  ANTHROPIC_API_KEY: ""
  GEMINI_API_KEY: ""
  ALBERT_API_KEY: ""
```

- [ ] **Step 4: Écrire `secrets/clear/droit-compare-gcp-sa.yaml` depuis le JSON du compte de service**

Le contenu du fichier doit être injecté tel quel sous la clé `gcp-sa.json`. Utiliser un here-doc qui indente le JSON, ou générer via kubectl (méthode fiable) :
```bash
cd /home/ubuntu/perso/home_kluster
kubectl create secret generic droit-compare-gcp-sa \
  --namespace dinum \
  --from-file=gcp-sa.json=/home/ubuntu/pro/droit_compare/prj-dinum-exp-p-bq-608d-39748e305d89.json \
  --dry-run=client -o yaml > secrets/clear/droit-compare-gcp-sa.yaml
head -5 secrets/clear/droit-compare-gcp-sa.yaml
```
Expected: fichier Secret avec `data.gcp-sa.json` (base64) (PASS).

- [ ] **Step 5: Écrire `secrets/clear/droit-compare-basicauth.yaml`**

Générer une paire utilisateur/mot de passe htpasswd (bcrypt), clé `users` :
```bash
cd /home/ubuntu/perso/home_kluster
DC_WEB_USER=droit
DC_WEB_PASS=$(openssl rand -hex 12)
HTPASSWD=$(htpasswd -nbB "$DC_WEB_USER" "$DC_WEB_PASS")
echo "ACCES WEB -> user=$DC_WEB_USER pass=$DC_WEB_PASS (à transmettre à l'utilisateur)"
kubectl create secret generic droit-compare-basicauth \
  --namespace dinum \
  --from-literal=users="$HTPASSWD" \
  --dry-run=client -o yaml > secrets/clear/droit-compare-basicauth.yaml
```
Expected: fichier créé ; **noter les identifiants** pour les transmettre à l'utilisateur. (Si `htpasswd` absent : `apt-get install -y apache2-utils` ou `docker run --rm httpd:alpine htpasswd -nbB user pass`.)

- [ ] **Step 6: Sceller les 4 secrets**

`seal_all.sh` saute les fichiers déjà présents dans `sealed/`. Comme ce sont de nouveaux secrets, il les chiffrera.
```bash
cd /home/ubuntu/perso/home_kluster
bash secrets/seal_all.sh
ls -la secrets/sealed/droit-compare-*.yaml
```
Expected: 4 fichiers `secrets/sealed/droit-compare-*.yaml` créés (PASS).

- [ ] **Step 7: Vérifier que les fichiers clairs ne sont pas suivis par git**

Run:
```bash
cd /home/ubuntu/perso/home_kluster
git status --porcelain secrets/clear/ ; echo "---" ; git check-ignore secrets/clear/droit-compare-db.yaml
```
Expected: aucune sortie pour `git status` sur `secrets/clear/` (ignoré), et `git check-ignore` renvoie le chemin (PASS). Si un fichier clair apparaît comme suivi, **NE PAS committer** et corriger `.gitignore`.

- [ ] **Step 8: Commit (uniquement les sealed)**

```bash
cd /home/ubuntu/perso/home_kluster
git add secrets/sealed/droit-compare-db.yaml \
        secrets/sealed/droit-compare-secrets.yaml \
        secrets/sealed/droit-compare-gcp-sa.yaml \
        secrets/sealed/droit-compare-basicauth.yaml
git commit -m "feat(droit-compare): sealed secrets (db, api keys, gcp-sa, basicauth)"
```

---

## Task 7: Application ArgoCD + image-updater (home_kluster)

**Files:**
- Create: `/home/ubuntu/perso/home_kluster/argocd/apps/droit-compare.yaml`
- Modify: `/home/ubuntu/perso/home_kluster/apps/tools/argocd-image-updater/values.yaml`

**Interfaces:**
- Consumes: dossier `apps/dinum/droit_compare` (Tasks 3-5).
- Produces: Application ArgoCD `droit-compare` ; CR ImageUpdater surveillant `harbor.valab.top/prod/droit-compare:main`.

- [ ] **Step 1: Écrire l'Application ArgoCD**

Create `/home/ubuntu/perso/home_kluster/argocd/apps/droit-compare.yaml` :

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: droit-compare
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/abugeia/home_kluster.git
    targetRevision: main
    path: apps/dinum/droit_compare
  destination:
    server: https://kubernetes.default.svc
    namespace: dinum
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - PrunePropagationPolicy=foreground
      - PruneLast=true
```

- [ ] **Step 2: Lire l'entrée vfnc de l'image-updater pour la répliquer fidèlement**

Run:
```bash
cd /home/ubuntu/perso/home_kluster
grep -n -A12 "namePattern: vfnc" apps/tools/argocd-image-updater/values.yaml
```
Expected: bloc `applicationRefs` de vfnc avec `imageName` et options de write-back. S'en servir comme gabarit exact (mêmes annotations/clés).

- [ ] **Step 3: Ajouter la CR ImageUpdater pour droit-compare**

Modifier `apps/tools/argocd-image-updater/values.yaml` : ajouter, à côté de l'entrée `vfnc` (dans la même section `extraObjects`/`applicationRefs` selon la structure observée au Step 2), un bloc pour `droit-compare` avec **une seule image** :
- `namePattern: droit-compare`
- image surveillée : `harbor.valab.top/prod/droit-compare:main`
- même configuration de write-back GitOps (deploy key SSH) que vfnc.

Reproduire exactement la forme du bloc vfnc en remplaçant `vfnc`→`droit-compare` et en ne gardant qu'une image (supprimer la seconde ligne `vfnc-web`). Conserver l'indentation YAML.

- [ ] **Step 4: Valider la syntaxe YAML des deux fichiers**

Run:
```bash
cd /home/ubuntu/perso/home_kluster
python -c "import yaml; [yaml.safe_load(open(f)) for f in ['argocd/apps/droit-compare.yaml']]; print('app OK')"
python -c "import yaml; list(yaml.safe_load_all(open('apps/tools/argocd-image-updater/values.yaml'))); print('values OK')"
```
Expected: `app OK` et `values OK` (PASS).

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/perso/home_kluster
git add argocd/apps/droit-compare.yaml apps/tools/argocd-image-updater/values.yaml
git commit -m "feat(droit-compare): application argocd + entree image-updater"
```

---

## Task 8: Vérification de bout en bout

**Files:** aucun (validation).

**Interfaces:**
- Consumes: tout ce qui précède + premier build CI (Task 2) mergé sur `main`.

- [ ] **Step 1: Pré-requis hors GitOps (à confirmer avec l'utilisateur)**

- DNS `droit-compare.valab.top` pointant vers l'ingress (comme `vfnc.valab.top`).
- Sur GCP `prj-dinum-exp-p-bq-608d` : API Vertex AI activée + rôle `roles/aiplatform.user` sur le compte de service.
- Secrets repo GitHub `droit_compare` : `ROBOT_VALAB_USERNAME` / `ROBOT_VALAB_TOKEN` présents (réutiliser ceux de vfnc).

- [ ] **Step 2: Merger les branches**

Après revue : merger `feat/deploy-harbor` (droit_compare) sur `main` (déclenche le build), puis `feat/droit-compare` (home_kluster) sur `main` (déclenche ArgoCD).

- [ ] **Step 3: Vérifier le build de l'image**

Run (ou via l'UI GitHub Actions) :
```bash
cd /home/ubuntu/pro/droit_compare
gh run list --workflow "Deploy to Harbor Valab (Automatic)" --limit 1
```
Expected: dernier run `completed/success` (PASS).

- [ ] **Step 4: Vérifier l'Application ArgoCD**

Run:
```bash
kubectl get application droit-compare -n argocd -o jsonpath='{.status.sync.status}/{.status.health.status}{"\n"}'
kubectl get pods -n dinum -l app.kubernetes.io/name=droit-compare-api
kubectl get pods -n dinum -l app.kubernetes.io/name=droit-compare-db
```
Expected: `Synced/Healthy`, pods `Running` (PASS). Si `ImagePullBackOff`, vérifier la réplication de `harbor-cicd-secret` dans le ns `dinum`.

- [ ] **Step 5: Vérifier les SealedSecrets déchiffrés**

Run:
```bash
kubectl get secret -n dinum droit-compare-db droit-compare-secrets droit-compare-gcp-sa droit-compare-basicauth
```
Expected: les 4 secrets présents (le controller SealedSecrets les a déchiffrés) (PASS).

- [ ] **Step 6: Vérifier l'app en HTTP**

Run (identifiants basic auth générés en Task 6) :
```bash
curl -su "droit:<PASS_WEB>" https://droit-compare.valab.top/api/health
curl -su "droit:<PASS_WEB>" -o /dev/null -w "%{http_code}\n" https://droit-compare.valab.top/
```
Expected: `/api/health` renvoie un JSON OK ; `/` renvoie `200` (frontend servi) (PASS).

- [ ] **Step 7: Test fonctionnel Gemini/Vertex (preuve finale)**

Lancer une comparaison via l'UI (ou un POST `/api/compare`) et vérifier qu'un job se termine sans erreur d'authentification Vertex. Inspecter les logs en cas d'échec :
```bash
kubectl logs -n dinum -l app.kubernetes.io/name=droit-compare-api --tail=50
```
Expected: pas d'erreur `DefaultCredentialsError` / `PermissionDenied` ; job `compare` complété (PASS).

---

## Notes d'exécution

- **Ordre inter-repos :** Tasks 1-2 (droit_compare) et Tasks 3-7 (home_kluster) sont indépendantes jusqu'au merge. Le premier build (Task 2) doit idéalement précéder le sync ArgoCD pour que l'image `:main` existe ; sinon le pod restera en `ImagePullBackOff` jusqu'au premier push.
- **Digest image-updater :** `.argocd-source-droit-compare.yaml` démarre vide (`images: []`) ; l'image-updater l'alimentera automatiquement au premier digest détecté.
- **Secrets :** ne jamais committer `secrets/clear/`. Transmettre les identifiants basic auth à l'utilisateur hors du repo.
