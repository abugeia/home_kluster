# Troubleshooting Home Kluster

## ArgoCD : Application "Progressing" (Ingress Issue)

### Le Problème
Les applications utilisant un **Ingress** (comme Harbor ou ArgoCD lui-même) restent indéfiniment dans l'état `Progressing` ou `Suspended` dans ArgoCD, bien qu'elles fonctionnent ("Healthy" techniquement).

### La Cause
ArgoCD vérifie l'état de santé (Health Check) des ressources. Pour un **Ingress**, ArgoCD attend que le champ `status.loadBalancer.ingress` contienne une IP ou un Hostname.

*   **Sur le Cloud (ex: Oracle Cloud / `orarm`)** : Le Cloud Provider (CCM) attribue une IP publique au LoadBalancer de Traefik. Traefik remonte cette info sur les Ingress. Le champ est rempli -> **Healthy**.
*   **Sur Home Lab (ex: `home_kluster`)** : Sans Cloud Controller Manager externe (ou MetalLB configuré spécifiquement), le Service LoadBalancer n'a pas forcément d'IP "externe" officielle au sens Kubernetes. Traefik ne met donc pas jour les Ingress. Le champ reste vide -> **Progressing**.

### Les Solutions

#### Option A : Patch ArgoCD (APPLIED)
On configure ArgoCD pour qu'il considère un Ingress sans IP comme "Healthy".

**APPLIED:** This configuration has been added to `argocd/helm/values.yaml` in the `configs.cm` section.

```yaml
configs:
  cm:
    resource.customizations: |
      networking.k8s.io/Ingress:
        health.lua: |
          hs = {}
          hs.status = "Healthy"
          hs.message = "Ingress is healthy (ignored loadBalancer status)"
          return hs
```

#### Option B : Configurer Traefik (Plus propre si VIP existante)
Si Traefik a une IP (via MetalLB ou Kube-VIP), on peut le forcer à "publier" cette info sur tous les Ingress.

Modifier les `values.yaml` du chart Traefik :

```yaml
providers:
  kubernetesIngress:
    publishedService:
      enabled: true
      pathOverride: "infra/traefik" # namespace/service-name de Traefik
```

## vmagent : plus aucune métrique de nœud ni de conteneur (403 `nodes/proxy`)

### Le Problème
Les dashboards Grafana « K8S » se vident : plus de CPU/RAM par pod, plus de
métriques kubelet. Les jobs `kubernetes-nodes` et `kubernetes-cadvisor` sont à
`up=0`, alors que le cluster, Grafana et VictoriaMetrics vont parfaitement bien.
Panne **silencieuse** : les autres jobs (`external-nodes`, `garage`, `postgres`,
`nut`, `kubernetes-pods`) continuent de remonter, donc rien ne saute aux yeux.

Dans les logs de vmagent :

```
403: nodes "ubuntu-srv" is forbidden: User
"system:serviceaccount:observability:vmagent-victoria-metrics-agent"
cannot get resource "nodes/proxy" in API group "" at the cluster scope
```

### La Cause
Le chart `victoria-metrics-agent` a **retiré `nodes/proxy` de son ClusterRole en
0.31.0** (03/02/2026), cette permission permettant une escalade de privilèges
(elle ouvre *tous* les endpoints du kubelet : `/exec`, `/run`…). Un bump Renovate
qui traverse ce palier casse donc toute config qui scrape le kubelet via le proxy
de l'API server (`/api/v1/nodes/$1/proxy/metrics[/cadvisor]`).

> Vécu ici le 04/09/2026 : PR #9 (Renovate) monte le chart 0.29.0 → 0.46.0.
> Dernier point de métrique à 16:00, soit une minute après le merge.

### La Solution (APPLIED)
Scraper le kubelet **en direct** plutôt que par le proxy, dans
`apps/tools/vmagent/values.yaml` :

*   `role: node` pose déjà `__address__` à `<NodeInternalIP>:10250` — il suffit
    de **supprimer** les `relabel_configs` qui réécrivent `__address__` vers
    `kubernetes.default.svc:443`, et de poser `metrics_path` en dur
    (`/metrics` et `/metrics/cadvisor`).
*   Aucun RBAC à ajouter : `/metrics/*` relève du subresource `nodes/metrics`,
    que le chart accorde toujours (table d'autorisation kubelet ; le feature gate
    `KubeletFineGrainedAuthz` est stable depuis k8s v1.36).
*   `insecure_skip_verify: true` devient **indispensable** : en direct on parle au
    certificat auto-signé du kubelet, plus à celui de l'API server.
*   Le label `instance` reste le nom du nœud : pour `role: node`, il est posé
    d'office au node name, indépendamment de `__address__`. Pas de rupture de
    série dans l'historique.

L'alternative — réaccorder `nodes/proxy` via `rbac.extraRules` dans les values —
fonctionne aussi (le chart expose ce champ depuis 0.25.6) mais réintroduit
précisément la permission que l'upstream a retirée pour raison de sécurité.

Refs : [changelog du chart](https://docs.victoriametrics.com/helm/victoria-metrics-agent/changelog/) ·
[kubelet authn/authz](https://kubernetes.io/docs/reference/access-authn-authz/kubelet-authn-authz/)
