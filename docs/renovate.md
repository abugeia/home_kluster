# Renovate Bot (Mises à jour automatiques)

Ce dépôt utilise [Renovate](https://github.com/renovatebot/renovate) pour maintenir les dépendances à jour (images Docker, Charts Helm, manifeste Kubernetes, etc.).

## 🚀 Activation

Pour activer Renovate sur ce dépôt :

1.  Aller sur l'application GitHub **[Renovate](https://github.com/apps/renovate)**.
2.  Cliquer sur **Install** (ou **Configure** si déjà installé).
3.  Sélectionner ce dépôt (`home_kluster`).
4.  Renovate va détecter le fichier `renovate.json` à la racine et créer une première "Onboarding PR" (ou directement les PRs si la config est déjà valide).

## 📅 Planning et Fonctionnement

La configuration est définie dans `renovate.json` :

*   **Planning** : Les recherches de mises à jour se font le **mardi** (heure de Nouméa), sur la journée entière.
*   **Regroupement** : 
    *   Toutes les mises à jour "non-majeures" (patchs, mineures) sont **regroupées** dans une seule Pull Request pour éviter le spam.
    *   Les mises à jour majeures (v1.0.0 -> v2.0.0) restent séparées pour attirer l'attention.
*   **Dashboard** : Une "Issue" spéciale appelée "Dependency Dashboard" sera créée pour lister les mises à jour en attente et permettre de forcer une vérification manuelle.

## 🛠️ Utilisation au quotidien

1.  Le mardi matin, tu recevras potentiellement une ou plusieurs PRs de Renovate.
2.  ArgoCD ne se mettra pas à jour tant que tu n'as pas **mergé** ces PRs.
3.  Vérifie le contenu (changelog inclus dans la PR).
4.  **Merge** la PR.
5.  ArgoCD détectera le changement et mettra à jour le cluster.

## ⚠️ Le manager `argocd` doit être déclaré explicitement

C'est le piège qui a rendu Renovate à moitié aveugle pendant sept mois. Le manager
`argocd` — celui qui lit le `targetRevision` des charts Helm dans les `Application` —
a `managerFilePatterns: []` par défaut : sans configuration, **il ne matche aucun
fichier**. L'amont l'assume, faute de convention de nommage pour les YAML Argo CD.

Conséquence observée : Renovate n'a jamais proposé la moindre montée de chart. Les
seules PR qu'il ait ouvertes (janvier 2026) portaient sur des images Docker, vues par
le manager `kubernetes`. Pendant ce temps l'écart s'est creusé jusqu'à 21 charts en
retard, dont 5 majeures — dont ArgoCD lui-même, à deux majeures.

Le manager est désormais déclaré sur `argocd/apps/*.yaml`, où vivent les 55
Applications du dépôt.

## Le schedule doit rester large

La configuration d'origine n'ouvrait qu'**une heure par semaine** (« after 8am and
before 9am on tuesday »). C'est fragile : le `schedule` ne dit pas à Renovate *quand
se réveiller*, il lui interdit d'agir **hors** de la fenêtre. Avec l'App hébergée,
c'est Mend qui décide de l'heure des jobs — si aucun ne tombe dans cette heure-là,
Renovate ne crée jamais rien. La fenêtre couvre désormais la journée du mardi, ce qui
garde l'intention (un lot hebdomadaire, pas de bruit quotidien) sans le pari horaire.

## Autres corrections de la même passe (2026-09-04)

- `fileMatch` → `managerFilePatterns` : l'option a été renommée et l'ancien nom
  **n'existe plus** dans le schéma amont (0 occurrence, contre 355 pour le nouveau).
  Trois déclarations du dépôt l'utilisaient encore.
- `config:base` → `config:recommended` : `config:base` a disparu de la documentation.
- Le manager `flux` a été retiré : le dépôt ne contient aucune ressource Flux, il
  faisait scanner tous les YAML pour rien.
- Les `Chart.yaml` locaux (`actions-runner`, `actions-runner-orga`,
  `sablier/middlewares-chart`) n'ont besoin d'aucune config : le manager `helmv3` les
  détecte par défaut.

## Si Renovate ne produit toujours rien

Une config valide ne suffit pas, l'**App GitHub doit être installée** sur le dépôt.
Toutes les PR Renovate de ce dépôt datent du même jour (27/01/2026) et aucune issue
« Dependency Dashboard » n'existe malgré `dependencyDashboard: true` : signe que l'App
ne tourne plus du tout, indépendamment de la config. Cela se vérifie sur
<https://github.com/settings/installations> — l'API REST le refuse à un PAT.

## Automerge : oui, sauf sur six composants

Les mises à jour non-majeures sont en `automerge: true`, et ArgoCD est en auto-sync :
une PR mergée par le bot part en production sans relecture. C'est le bon compromis pour
le catalogue applicatif — le pire cas est un service qui tombe et qu'on redresse — et
c'est ce qui évite de laisser le retard s'accumuler.

Six composants en sont exclus (groupe `infra-critique`, à merger à la main), parce
qu'une **mineure** y suffit à couper l'accès à tout :

| composant | ce qu'une régression casse |
|---|---|
| `csi-driver-nfs` | **tous** les PVC — Immich, les bases, les configs |
| `metallb` | l'attribution des IP, dont le `10.0.0.101` du Gateway |
| `traefik` | l'ingress entier |
| `cert-manager` | le renouvellement TLS, en silence jusqu'à l'expiration |
| `argo-cd` | l'outil qui déploie tout, rollback compris |
| `tailscale-operator` | l'accès distant |

Deux raisons concrètes plutôt que théoriques. Le serveur s'éteint de minuit à 10h : un
lot mergé la nuit s'applique d'un bloc au réveil, et si ça casse on découvre un cluster
en vrac sans savoir quel changement l'a causé. Et l'incident du 2026-09-04 l'a montré —
ce qui a rendu le diagnostic possible, c'est de *savoir* qu'un upgrade venait de passer.

L'ordre des `packageRules` compte : Renovate applique les règles dans l'ordre et les
dernières gagnent. La règle `infra-critique` doit donc rester **après** celle qui active
l'automerge des non-majeures, sans quoi elle serait sans effet.
