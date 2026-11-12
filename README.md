# Veille Peugeot Partner → ntfy

Surveille AutoScout24 toutes les 15 minutes et envoie une notification ntfy (avec photo) pour chaque **nouveau Peugeot Partner** :
- nouvelle forme uniquement (2019+, moteur 1.5 BlueHDi ; les 1.6 HDi de l'ancienne génération sont écartés) ;
- diesel, 10 000 € max, 140 000 km max, 150 km autour de Salon-de-Provence.

Toutes les annonces dans ces critères sont signalées. Priorité **urgente** pour :
- une boîte **6 vitesses** (lue dans le titre « BVM6 », ou probable sur les 2022+) ;
- une **version longue / XL** ;
- un « Super prix » ou « Prix très bas » selon AutoScout24.

## Installation (10 minutes)

1. **ntfy** : installe l'appli ntfy sur ton téléphone et abonne-toi à un sujet au nom difficile à deviner, par exemple `mistraloc-camion-8f3k2`.
2. **GitHub** : crée un dépôt **public** (les minutes GitHub Actions sont illimitées sur un dépôt public ; en privé, 96 lancements par jour dépasseraient le quota gratuit).
3. Mets les fichiers dans le dépôt :
   - `monitor.py` à la racine
   - `seen.json` à la racine (contient `[]`)
   - `veille.yml` dans le dossier `.github/workflows/`
4. **Secret** : dans le dépôt, *Settings → Secrets and variables → Actions → New repository secret*, nom `NTFY_TOPIC`, valeur = ton sujet ntfy.
5. **Test** : onglet *Actions → Veille utilitaires → Run workflow*. Au premier passage, tu recevras les bonnes affaires déjà en ligne ; ensuite, seulement les nouvelles.

## Régler les critères

Tout est en haut de `monitor.py` : `PRIX_MAX`, `ANNEE_MIN`, `KM_MAX`, `RAYON_KM`, `MODELES`.

## À savoir

- GitHub peut décaler les lancements programmés de quelques minutes aux heures chargées.
- Si AutoScout24 bloque les serveurs de GitHub, le job échoue et GitHub t'envoie un e-mail.
- La version longue est repérée dans le titre de l'annonce (XL, Long, L2, 950 kg) : si le vendeur ne l'indique pas, elle passe inaperçue.
