#!/usr/bin/env python3
"""
Veille de bonnes affaires utilitaires (Partner / Berlingo / Combo) sur AutoScout24.
Envoie une notification ntfy pour chaque nouvelle annonce jugée "bonne affaire".
Aucune dépendance externe : uniquement la bibliothèque standard Python.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# ---------- Réglages ----------
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")

ZIP = "13300 Salon-de-Provence"
RAYON_KM = 150
PRIX_MAX = 11500
ANNEE_MIN = 2019  # nouvelle forme (Partner III / Berlingo III / Combo E) uniquement
KM_MAX = 140000

# Référence : le Partner du frère (2022, 120 000 km, 11 500 €).
# Toute annonce au moins aussi bien (année >= 2022 et km <= 120 000, prix <= PRIX_MAX) déclenche une alerte.
REF_ANNEE = 2022
REF_KM = 120000

# Mots qui signalent une version longue (XL / Long / L2 / 950 kg)
MOTS_LONG = ("XL", "LONG", "L2", "950")
PAGES = 2  # pages de 20 annonces par modèle, triées des plus récentes aux plus anciennes

MODELES = [
    ("peugeot", "partner"),
    ("citroen", "berlingo"),
    ("opel", "combo"),
]

# Évaluation de prix AutoScout24 : 0 = anormalement bas, 1 = super prix, 2 = bon prix, 3 = prix correct
EVALUATIONS_ALERTE = {0, 1, 2}
LIBELLES = {0: "⚠️ Prix très bas (à vérifier)", 1: "🔥 Super prix", 2: "👍 Bon prix"}

SEEN_FILE = Path(__file__).with_name("seen.json")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


def url_recherche(marque, modele, page):
    params = {
        "fregfrom": ANNEE_MIN,
        "priceto": PRIX_MAX,
        "kmto": KM_MAX,
        "fuel": "D",
        "body": 13,          # utilitaire
        "cy": "F",
        "zip": ZIP,
        "zipr": RAYON_KM,
        "sort": "age",       # plus récentes d'abord
        "desc": 1,
        "page": page,
        "size": 20,
    }
    return f"https://www.autoscout24.fr/lst/{marque}/{modele}?" + urllib.parse.urlencode(params)


def telecharger(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def extraire_annonces(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("Données __NEXT_DATA__ introuvables (page bloquée ou structure modifiée)")
    data = json.loads(m.group(1))
    return data["props"]["pageProps"].get("listings", []) or []


def charger_vus():
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text()))
        except Exception:
            pass
    return set()


def sauver_vus(vus):
    # On garde les 2000 derniers identifiants pour que le fichier reste petit
    SEEN_FILE.write_text(json.dumps(sorted(vus)[-2000:], indent=0))


def photo_annonce(annonce):
    """Première photo de l'annonce, en JPEG 720x540 (format bien affiché par ntfy)."""
    images = annonce.get("images") or []
    if not images:
        return None
    base = images[0].rsplit("/", 1)[0]  # retire le suffixe de taille (ex. /250x188.webp)
    return f"{base}/720x540.jpg"


def notifier(titre, message, lien, priorite="high", photo=None):
    if not NTFY_TOPIC:
        print(f"[pas de NTFY_TOPIC] {titre} | {message} | {lien} | photo={photo}")
        return
    # Paramètres passés dans l'URL (UTF-8 OK, contrairement aux en-têtes HTTP)
    params = {
        "title": titre,
        "click": lien,
        "priority": priorite,
        "tags": "truck",
    }
    if photo:
        params["attach"] = photo
        params["filename"] = "photo.jpg"
    q = urllib.parse.urlencode(params)
    url = f"{NTFY_SERVER.rstrip('/')}/{NTFY_TOPIC}?{q}"
    req = urllib.request.Request(url, data=message.encode("utf-8"), method="POST")
    urllib.request.urlopen(req, timeout=20).read()


def main():
    vus = charger_vus()
    nouvelles = 0
    erreurs = 0

    for marque, modele in MODELES:
        for page in range(1, PAGES + 1):
            url = url_recherche(marque, modele, page)
            try:
                annonces = extraire_annonces(telecharger(url))
            except Exception as e:
                erreurs += 1
                print(f"Erreur {marque} {modele} p{page} : {e}", file=sys.stderr)
                break
            if not annonces:
                break

            for a in annonces:
                aid = a.get("id")
                if not aid or aid in vus:
                    continue
                vus.add(aid)

                prix = a.get("price", {})
                evaluation = prix.get("priceEvaluation")
                v = a.get("vehicle", {})
                t = a.get("tracking", {})
                loc = a.get("location", {})
                version = v.get("modelVersionInput") or ""
                mots = re.findall(r"[A-Z0-9]+", version.upper())

                # Ancienne génération (moteur 1.6 HDi) : la nouvelle forme n'a que le 1.5 BlueHDi
                if re.search(r"\b1[.,]6\b", version):
                    continue

                # Version longue ?
                est_long = any(m in MOTS_LONG or m.startswith("950") for m in mots)

                # Au moins aussi bien que le Partner du frère ?
                try:
                    annee = int(str(t.get("firstRegistration", "")).split("-")[-1])
                    km = int(t.get("mileage") or 0)
                    bat_reference = annee >= REF_ANNEE and 0 < km <= REF_KM
                except ValueError:
                    bat_reference = False

                bon_prix = evaluation in EVALUATIONS_ALERTE
                # Une version longue ou une annonce qui bat la référence est signalée même à "prix correct"
                if not (bon_prix or est_long or bat_reference):
                    continue

                raisons = []
                if est_long:
                    raisons.append("📏 VERSION LONGUE / XL")
                if bat_reference:
                    raisons.append("⭐ Mieux que le Partner de ton frère (2022, 120 000 km)")
                if bon_prix:
                    raisons.append(LIBELLES.get(evaluation, ""))

                lignes = [
                    " · ".join(raisons),
                    f"{prix.get('priceFormatted', '?')}",
                    f"{t.get('firstRegistration', '?')} · {v.get('mileageInKm', '?')}",
                    f"{loc.get('city', '?')} ({loc.get('zip', '')}) · {loc.get('distanceToSearchLocationInKm', '?')} km",
                    version,
                ]

                prefixe = "📏 XL — " if est_long else ""
                titre = f"{prefixe}{v.get('make', '')} {v.get('model', '')} — {prix.get('priceFormatted', '')}"
                lien = "https://www.autoscout24.fr" + a.get("url", "")
                urgent = est_long or bat_reference or evaluation == 1
                notifier(titre, "\n".join(lignes), lien,
                         priorite="urgent" if urgent else "high",
                         photo=photo_annonce(a))
                nouvelles += 1
                time.sleep(1)

            time.sleep(2)  # on reste poli avec le site

    sauver_vus(vus)
    print(f"Terminé : {nouvelles} alerte(s), {len(vus)} annonces connues, {erreurs} erreur(s).")

    # Si toutes les requêtes ont échoué, on fait échouer le job (GitHub t'enverra un e-mail)
    if erreurs == len(MODELES):
        sys.exit(1)


if __name__ == "__main__":
    main()
