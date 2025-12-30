# TODO Kluster

## Réseau / DNS
- [ ] **Problème ndots: 5** : Investiguer pourquoi la résolution DNS échoue (ServFail ou timeout) pour les domaines externes sans un `ndots: 1` explicite. Le comportement par défaut de K8s (`ndots: 5`) semble entrer en conflit avec le resolver ou le DNS amont dans certains Pods (MeTube, Syncthing).
