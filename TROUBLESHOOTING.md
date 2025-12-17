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
