# 🛠️ Guide de Mise en Place du DNS Local (valab.top)

Ce guide est à suivre une fois que tu as reçu ton **Raspberry Pi Zero 2W**.

## Étape 1 : Préparation du Raspberry Pi
1.  Flashe **Raspberry Pi OS Lite (64-bit)** sur la carte SD.
2.  Active le SSH et configure le Wi-Fi (via `Raspberry Pi Imager`).
3.  Récupère l'IP du Pi sur ta box.

## Étape 2 : Déploiement avec Ansible
Utilise ton dépôt `infra_proxmox/ansible`.
1.  Ajoute l'IP du Pi dans ton fichier `inventory`.
2.  Lancer le playbook pour installer AdGuard Home :
    ```bash
    ansible-playbook site.yml -l raspberry_pi
    ```
    *(Le rôle s'occupera d'installer le binaire AdGuard et de le lancer).*

## Étape 3 : Configuration Globale avec Terraform
Utilise ton dépôt `infra/`.
1.  Ajoute le provider `gmichels/adguard` dans `provider.tf`.
2.  Crée un fichier `adguard.tf` :
    - Déclare tes listes de blocage (Ads, Trackers).
    - Ajoute les records statiques (ex: `pve.valab.top` -> IP Proxmox).
3.  Exécute : `terraform apply`.

## Étape 4 : Automatisation Kubernetes (ExternalDNS)
Utilise ton dépôt `home_kluster/`.
1.  Déploie le Helm Chart d'**ExternalDNS** via ArgoCD.
2.  Configure les arguments :
    - `source=ingress`
    - `provider=adguard`
    - `adguard-server=http://<IP_DU_PI>`
3.  Vérification : Déploie une app avec un Ingress, vérifie dans l'interface AdGuard que l'entrée DNS apparaît toute seule.

## Étape 5 : Activation Finale
Une fois que tout fonctionne :
- Change le paramètre **DNS** dans les réglages DHCP de ta Box internet.
- Mets l'IP de ton Raspberry Pi en DNS primaire.

---
> [!IMPORTANT]
> Grâce à ce setup, si tu éteins ton cluster Kubernetes, ton Internet continue de fonctionner et la pub reste bloquée ! Seules les URL de tes applis Kubernetes (`auth-id.valab.top`, etc.) ne répondront plus.
