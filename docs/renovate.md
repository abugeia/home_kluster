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

*   **Planning** : Les recherches de mises à jour se font uniquement le **Mardi matin entre 8h00 et 9h00** (Heure de Nouméa).
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
