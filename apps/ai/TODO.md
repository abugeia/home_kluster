# Stack IA — pistes d'évolution

État au 17/06/2026. Stack : OpenWebUI (k3s) → Ollama gpt-oss:20b (VM gaming GPU)
+ recherche web SearXNG/Playwright + task model llama3.2:3b (ollama-cpu) + STT
speaches (VM). Ce qui marche, ce qui plafonne, et les leviers restants.

## Ce qui est résolu (ne pas y revenir)
- Embedding RAG : 40s → ~1s (CPU limit 2→6 + OMP_NUM_THREADS=6 ; torch sur-souscrivait
  6 threads sur 2 cœurs → throttling CFS).
- SearXNG : timeout moteurs 3→8s, startpage/wikidata désactivés (timeouts).
- Playwright : lit le contenu réel des pages (le loader `requests` par défaut échoue).
- Query-gen : task model dédié CPU `llama3.2:3b` (qwen2.5:3b sortait des requêtes
  corrompues ; les modèles 2026 à raisonnement OOM/garbage sur CPU).
- gpt-oss : Ollama sépare bien thinking/content ; la fuite est côté OpenWebUI →
  workaround system prompt « réponds uniquement la réponse finale ».

## Plafond connu (NON réglable côté local)
La recherche web généraliste (SearXNG/Google) est **excellente pour les requêtes
techniques concrètes** (doc, GitHub, StackOverflow — prouvé) mais **mauvaise pour
les requêtes "dernières X" / méta / sensibles à la fraîcheur** (dernière release,
actu de région) : Google classe en tête les pages de section SEO ou de vieux blogs,
pas les articles datés / la page live (ex. GitHub Releases). Aucun réglage SearXNG
ne corrige ça.

## Pistes d'évolution (par impact)

### 1. Search API LLM-native (Tavily / Exa) — LE levier pour la fraîcheur/pertinence
- Renvoie contenu d'article classé + daté + extrait propre → résout les requêtes
  "actu / dernières versions" que SearXNG rate.
- Coût : clé API (quota gratuit), requêtes sortent du cluster (pas 100% local).
- Mise en œuvre : `WEB_SEARCH_ENGINE=tavily` + `TAVILY_API_KEY` dans OpenWebUI.
- À faire si le besoin "actu fiable" devient récurrent.

### 2. Mode agentic — à retenter avec un meilleur modèle local
- Testé KO avec gpt-oss:20b (ne déclenche pas la recherche → hallucine ; la doc
  prévient que les petits modèles locaux peinent sur le multi-étapes).
- Si un jour un modèle local plus fort en tool-calling tient dans 16 Go →
  `DEFAULT_MODEL_PARAMS={"function_calling":"native"}` : supprime query-gen +
  embedding, le modèle pilote search_web/fetch_url comme un vrai agent.

### 3. Fuite raisonnement gpt-oss — fix propre
- Workaround actuel = system prompt (par modèle, dans l'UI → pas GitOps).
- Fix réel : maj OpenWebUI (parsing thinking/streaming amélioré) ou bon passage
  de `reasoning_effort` low/medium/high. Suivre les versions (issues #20921, #9348).
- Chart actuel 14.6.0 (OWUI 0.9.5) ; dispo 14.8.0 (0.9.6, patch mineur).

### 4. Loader d'extraction — firecrawl en alternative à Playwright
- Playwright OK, mais firecrawl/tavily-extract donnent parfois une extraction plus
  propre (markdown structuré) sur sites complexes. `WEB_LOADER_ENGINE=firecrawl`.

### 5. Bypass embedding (option vitesse)
- `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=true` : injecte le contenu direct dans
  gpt-oss (64k contexte) au lieu de vectoriser. Plus rapide encore, + de tokens.
  À tester si l'embedding ~1-2s devient gênant (peu probable).

## Dette / à savoir
- Config runtime OpenWebUI (moteur recherche, loader, bypass, task model, system
  prompt) vit dans **Redis/DB** (PersistentConfig), PAS dans git : le `values.yaml`
  ne fait que seeder. Toute valeur effective se règle via UI ou `redis-cli SET
  open-webui:config:<KEY>`. Inhérent à OpenWebUI.
- ollama-cpu : limite 5Gi, `keep_alive=-1`. Ne pas charger 2 modèles 3B en même
  temps (OOM). postStart pull llama3.2:3b uniquement.
