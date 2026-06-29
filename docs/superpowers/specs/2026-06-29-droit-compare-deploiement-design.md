# Déploiement `droit_compare` (façon `vfnc`) — Design

> État : validé. Cible : déployer l'application `droit_compare` sur le cluster
> via GitOps (ArgoCD + Kustomize), en reprenant le pattern de `vfnc`
> (`apps/dinum/vfnc`), avec les adaptations propres à `droit_compare`.

## Contexte

`droit_compare` (repo voisin `/home/ubuntu/pro/droit_compare`, remote
`pro:antoinebugeia/droit_compare`) est un outil de droit comparé (POC) :
backend FastAPI qui **sert lui-même le frontend statique** et expose ses routes
API sous `/api/*`. Pas de service web séparé (contrairement à `vfnc`).

Différences structurantes vs `vfnc` :

- **Image unique** : le backend sert frontend (`/`) + API (`/api/*`). Pas de
  service `web`, pas de middleware `stripPrefix`, pas de `--root-path`.
- Le `docker-compose` repose sur des bind-mounts absents de l'image :
  `frontend/`, `prompt.md`, doc few-shot, JSON de compte de service GCP.
- Le repo `droit_compare` n'a **pas encore** de workflow CI (Harbor).
- DB : `postgres:18-alpine` (pas `postgis`).
- LLM en prod : **Gemini via Vertex AI** (compte de service GCP).
- Tables créées au démarrage (`init_db()` → `Base.metadata.create_all`), pas de
  job de migration.

## Décisions (validées)

| Sujet | Décision |
|---|---|
| Fournisseur LLM prod | Gemini via Vertex AI (`GEMINI_USE_VERTEX=true`) |
| Fichiers de contexte | `frontend/` + `prompt.md` bakés dans l'image (déjà versionnés) |
| Doc few-shot (gitignoré) | **ConfigMap en clair** dans `home_kluster` |
| Compte de service GCP | **SealedSecret**, monté en fichier `/secrets/gcp-sa.json` |
| Exposition | `droit-compare.valab.top` + basic auth (comme vfnc), ns `dinum` |
| Scellement secrets | Cert `secrets/clear/sealed-secrets.pem` présent → Claude prépare `secrets/clear/*` ET lance `seal_all.sh` |

## Architecture cible

```
Internet ──TLS(letsencrypt)──> Traefik Ingress (droit-compare.valab.top)
                                   │  middleware: droit-compare-basicauth
                                   ▼
                       Service droit-compare-api:8000
                                   │
                       Deployment droit-compare-api  (image unique)
                         ├─ sert frontend statique sur /
                         ├─ API sur /api/*  (/api/health, /api/compare, …)
                         ├─ env: config LLM/Gemini/Vertex (non-secret)
                         ├─ envFrom: droit-compare-db, droit-compare-secrets
                         ├─ volume secret  droit-compare-gcp-sa → /secrets/gcp-sa.json
                         └─ volume cm      droit-compare-fewshot → /app/fewshot_reference.md
                                   │
                       Service headless droit-compare-db:5432
                                   ▼
                       StatefulSet droit-compare-db (postgres:18-alpine, PVC 5Gi)
```

## Composants

### A. Repo `droit_compare` (build de l'image)

1. **`Dockerfile.prod`** (racine du repo, contexte de build `.`) :
   - `FROM python:3.12-slim`, `WORKDIR /app`
   - `COPY backend/requirements.txt backend/requirements.txt` ; `pip install`
   - `COPY backend/ backend/` ; `COPY frontend/ frontend/` ; `COPY prompt.md prompt.md`
   - `ENV PYTHONPATH=/app/backend` ; `WORKDIR /app/backend` ; `EXPOSE 8000`
   - `CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]`
   - Chemins runtime cohérents avec le code :
     - frontend → `/app/frontend` (`main.py` : `parents[2]/frontend`)
     - prompt.md → `/app/prompt.md` (`llm/sections/base.py` : `parents[4]/prompt.md`)
   - Le `backend/Dockerfile` de dev reste inchangé (utilisé par `docker-compose`).

2. **`.github/workflows/deploy_harbor_valab.yaml`** : clone du workflow `vfnc`,
   mais **une seule image** dans la matrice :
   - `image: droit-compare`, `context: .`, `file: ./Dockerfile.prod`
   - registry `harbor.valab.top`, projet `prod`, tags `type=ref,event=branch`
     (`main`), `type=sha,prefix=sha-`, `latest` sur `main`.
   - multi-arch `linux/amd64,linux/arm64`, secrets `ROBOT_VALAB_USERNAME` /
     `ROBOT_VALAB_TOKEN`, cache gha.

### B. Repo `home_kluster` — `apps/dinum/droit_compare/`

3. **`db.yaml`** — Service headless `droit-compare-db` + StatefulSet
   `postgres:18-alpine` :
   - `envFrom: droit-compare-db` (POSTGRES_USER/PASSWORD/DB)
   - `PGDATA=/var/lib/postgresql/data/pgdata`, volume monté sur
     `/var/lib/postgresql/data` (pattern vfnc éprouvé)
   - `volumeClaimTemplates` : `local-path`, `5Gi`, RWO
   - probes `pg_isready`

4. **`api.yaml`** — Deployment `droit-compare-api` + Service :
   - `image: harbor.valab.top/prod/droit-compare:main`, `imagePullPolicy: Always`
   - `imagePullSecrets: harbor-cicd-secret`
   - `envFrom`: `droit-compare-db` (fournit `DATABASE_URL`), `droit-compare-secrets`
   - `env` inline (non-secret) :
     `LLM_PROVIDER=gemini`, `LLM_MODEL=gemini-3.5-flash`,
     `LLM_MODEL_CHEAP=gemini-3.1-flash-lite`, `GEMINI_USE_VERTEX=true`,
     `GOOGLE_CLOUD_PROJECT=prj-dinum-exp-p-bq-608d`, `GOOGLE_CLOUD_LOCATION=global`,
     `GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-sa.json`,
     `COMPARISON_MODE=distinct`, `FEWSHOT_REFERENCE_DOC=/app/fewshot_reference.md`,
     `DRAFTING_LIMIT=12`, `DRAFTING_CONCURRENCY=5`
   - volumes :
     - secret `droit-compare-gcp-sa` → fichier `/secrets/gcp-sa.json` (`readOnly`)
     - configMap `droit-compare-fewshot` → fichier `/app/fewshot_reference.md` (`readOnly`)
   - probes `httpGet /api/health` (readiness + liveness)
   - ressources : requests 128Mi/50m, limits 512Mi/1000m (alignées API vfnc)
   - Service `port: 8000 → targetPort: http`

5. **`middleware.yaml`** — un seul `Middleware` Traefik `droit-compare-basicauth`
   (basicAuth, secret `droit-compare-basicauth`, realm). **Pas** de stripprefix.

6. **`ingress.yaml`** — **un seul** Ingress `droit-compare` :
   - host `droit-compare.valab.top`, `ingressClassName: traefik`
   - entrypoints `web,websecure`, middleware
     `dinum-droit-compare-basicauth@kubernetescrd`
   - `cert-manager.io/cluster-issuer: letsencrypt`, TLS `secretName: droit-compare-tls`
   - règle unique : `path: /` → `droit-compare-api:8000`

7. **`kustomization.yaml`** :
   - `namespace: dinum`
   - `resources`: db.yaml, api.yaml, middleware.yaml, ingress.yaml
   - `configMapGenerator`: `droit-compare-fewshot` à partir du fichier local
     `fewshot_reference.md` (clé `fewshot_reference.md`)
   - `images`: `harbor.valab.top/prod/droit-compare` `newTag: main`
     (surveillé par argocd-image-updater, write-back kustomize)
   - Note : si `configMapGenerator` ajoute un suffixe de hash au nom, le mount
     dans `api.yaml` doit référencer le nom suffixé via kustomize, ou désactiver
     le suffixe (`generatorOptions: disableNameSuffixHash: true`) pour garder un
     nom stable. **Décision : `disableNameSuffixHash: true`** (nom stable, simple).

8. **`fewshot_reference.md`** — copie en clair du doc de travail few-shot (fourni
   par l'utilisateur ; gitignoré côté `droit_compare`).

9. **`.argocd-source-droit-compare.yaml`** — override de digest kustomize
   (cible de write-back de l'image-updater), initialisé au digest courant après
   le premier build.

### C. Glue GitOps

10. **`argocd/apps/droit-compare.yaml`** — Application ArgoCD (clone de
    `vfnc.yaml`) : project `default`, repo `home_kluster`, `targetRevision: main`,
    `path: apps/dinum/droit_compare`, destination ns `dinum`, syncPolicy
    automated (prune + selfHeal, PrunePropagationPolicy=foreground, PruneLast).

11. **`apps/tools/argocd-image-updater/values.yaml`** — ajout d'une CR
    ImageUpdater pour `droit-compare` (1 image
    `harbor.valab.top/prod/droit-compare:main`, write-back GitOss via la deploy
    key SSH, `applicationRefs.namePattern: droit-compare`), sur le modèle de
    l'entrée `vfnc`.

### D. Secrets (préparés en `secrets/clear/`, scellés par l'utilisateur)

12. `droit-compare-db` (ns dinum, Opaque) :
    `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB=droit_compare`,
    `DATABASE_URL=postgresql+psycopg://<user>:<pass>@droit-compare-db:5432/droit_compare`
    (le backend lit `DATABASE_URL` ; le conteneur postgres lit les `POSTGRES_*`).
13. `droit-compare-secrets` (ns dinum, Opaque) :
    `LEGIFRANCE_CLIENT_ID`, `LEGIFRANCE_CLIENT_SECRET`, et clés LLM vides
    (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `ALBERT_API_KEY`) — provider Vertex
    n'utilise pas de clé.
14. `droit-compare-gcp-sa` (ns dinum, Opaque) : clé `gcp-sa.json` = contenu du
    JSON de compte de service (`prj-dinum-exp-p-bq-608d-39748e305d89.json`).
15. `droit-compare-basicauth` (ns dinum, Opaque) : clé `users` (format htpasswd).

Workflow : créer les manifests Secret en clair dans `secrets/clear/`, puis
`secrets/seal_all.sh` (cert `secrets/clear/sealed-secrets.pem` présent) produit
`secrets/sealed/*.yaml`. Les SealedSecrets scellés sont committés ; le mécanisme
de déploiement des secrets (Application ArgoCD `secret-app`) les inclut.

## Flux de données

1. Push sur `main` (droit_compare) → GitHub Actions build `Dockerfile.prod` →
   push `harbor.valab.top/prod/droit-compare:main` (+ sha, latest).
2. argocd-image-updater détecte le nouveau digest → write-back dans
   `.argocd-source-droit-compare.yaml` (commit GitOps).
3. ArgoCD sync l'Application `droit-compare` → applique db/api/ingress/middleware
   + ConfigMap few-shot dans le ns `dinum`.
4. Au démarrage du pod API : `init_db()` crée les tables ; Vertex AI authentifié
   via `/secrets/gcp-sa.json`.
5. Requête utilisateur → Traefik (TLS + basic auth) → backend (frontend `/`,
   API `/api/*`).

## Gestion d'erreurs / points de vigilance

- **Auth Vertex** : le rôle `roles/aiplatform.user` doit être porté par le SA et
  l'API Vertex activée sur `prj-dinum-exp-p-bq-608d` (hors scope GitOps).
- **`/api/health`** : confirmé présent (`main.py:35`).
- **ConfigMap few-shot** : 176 Ko < limite 1 Mio ConfigMap → OK.
- **Nom ConfigMap stable** : `disableNameSuffixHash: true` pour que le mount
  reste valide (sinon mises à jour du doc non rechargées et nom cassé).
- **Pas de volume d'écriture backend** : uploads traités en mémoire, export docx
  renvoyé en réponse — aucun PVC backend requis.
- **DB sans postgis** : `droit_compare` n'utilise pas d'extension spatiale.

## Hors scope

- Activation de l'API Vertex / IAM GCP (côté GCP, manuel).
- Build de bundle frontend (le frontend est statique : `index.html` + `app.js`).
- Migrations versionnées (auto-create suffit au POC).
- Modification du `docker-compose` / Dockerfile de dev de `droit_compare`.

## Critères de succès

- L'image `harbor.valab.top/prod/droit-compare:main` est buildée et poussée par CI.
- L'Application ArgoCD `droit-compare` est `Synced` + `Healthy`.
- `https://droit-compare.valab.top` répond (basic auth), sert le frontend, et
  `/api/health` est OK.
- Une comparaison aboutit via Gemini/Vertex (preuve : un job `compare` complété).
