# Veille utilitaires → ntfy

Surveille AutoScout24 toutes les 15 minutes (Partner, Berlingo, Combo diesel, 2019+ (nouvelle forme), ≤ 11 500 €, ≤ 140 000 km, 150 km autour de Salon-de-Provence) et envoie une notification ntfy pour chaque **nouvelle** annonce qui est :
- une **version longue / XL** (alerte prioritaire, même à prix simplement correct) ;
- **au moins aussi bien que la référence** : 2022 ou plus récent, 120 000 km max, 11 500 € max ;
- ou notée « Super prix », « Bon prix » ou « Prix très bas » par AutoScout24.

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

Tout est en haut de `monitor.py` : `PRIX_MAX`, `ANNEE_MIN`, `KM_MAX`, `RAYON_KM`, `MODELES`, et `EVALUATIONS_ALERTE` (retire `2` pour ne garder que les « Super prix »).

## À savoir

- GitHub peut décaler les lancements programmés de quelques minutes aux heures chargées.
- Si AutoScout24 bloque les serveurs de GitHub, le job échoue et GitHub t'envoie un e-mail.
- La version longue est repérée dans le titre de l'annonce (XL, Long, L2, 950 kg) : si le vendeur ne l'indique pas, elle passe inaperçue.
