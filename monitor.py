#!/usr/bin/env python3
"""
Veille Peugeot Partner (nouvelle forme) sur AutoScout24.
Envoie une notification ntfy pour chaque nouvelle annonce qui correspond aux critères.
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
PRIX_MAX = 10000
ANNEE_MIN = 2019  # nouvelle forme (Partner III) uniquement
KM_MAX = 140000

# Mots qui signalent une version longue (XL / Long / L2 / 950 kg)
MOTS_LONG = ("XL", "LONG", "L2", "950")
PAGES = 2  # pages de 20 annonces par modèle, triées des plus récentes aux plus anciennes

# (marque, modèle, prix max, année min)
MODELES = [
    ("peugeot", "partner", PRIX_MAX, ANNEE_MIN),
]

# Évaluation de prix AutoScout24 : 0 = anormalement bas, 1 = super prix, 2 = bon prix, 3 = prix correct
EVALUATIONS_ALERTE = {0, 1, 2}
LIBELLES = {0: "⚠️ Prix très bas (à vérifier)", 1: "🔥 Super prix", 2: "👍 Bon prix"}

SEEN_FILE = Path(__file__).with_name("seen.json")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


def url_recherche(marque, modele, page, prix_max=PRIX_MAX, annee_min=ANNEE_MIN):
    params = {
        "fregfrom": annee_min,
        "priceto": prix_max,
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

    for marque, modele, prix_max, annee_min in MODELES:
        for page in range(1, PAGES + 1):
            url = url_recherche(marque, modele, page, prix_max, annee_min)
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

                # Boîte de vitesses (lue dans le titre de l'annonce)
                vu = version.upper()
                try:
                    annee = int(str(t.get("firstRegistration", "")).split("-")[-1])
                except ValueError:
                    annee = 0
                if "EAT8" in vu or "AUTO" in (v.get("transmission") or "").upper():
                    boite, six = "Boîte automatique", False
                elif re.search(r"BVM\s?6|6\s?VITESSES|\b6V\b", vu):
                    boite, six = "⚙️ 6 vitesses", True
                elif re.search(r"BVM\s?5|5\s?VITESSES|\b5V\b", vu):
                    boite, six = "5 vitesses", False
                elif annee >= 2022:
                    boite, six = "⚙️ 6 vitesses probable (2022+)", True
                else:
                    boite, six = "Boîte non précisée (5 ou 6 vitesses)", False

                # Toutes les annonces dans les critères sont signalées : la priorité indique les meilleures
                bon_prix = evaluation in EVALUATIONS_ALERTE
                raisons = []
                if six:
                    raisons.append(boite)
                if est_long:
                    raisons.append("📏 VERSION LONGUE / XL")
                if bon_prix:
                    raisons.append(LIBELLES.get(evaluation, ""))

                lignes = [
                    " · ".join(raisons) or "Nouvelle annonce",
                    f"{prix.get('priceFormatted', '?')}",
                    f"{t.get('firstRegistration', '?')} · {v.get('mileageInKm', '?')}",
                    f"{loc.get('city', '?')} ({loc.get('zip', '')}) · {loc.get('distanceToSearchLocationInKm', '?')} km",
                    boite if not six else "",
                    version,
                ]
                lignes = [l for l in lignes if l]

                prefixe = ("📏 XL " if est_long else "") + ("⚙️6 " if six else "")
                prefixe = prefixe.strip() + " — " if prefixe else ""
                titre = f"{prefixe}{v.get('make', '')} {v.get('model', '')} — {prix.get('priceFormatted', '')}"
                lien = "https://www.autoscout24.fr" + a.get("url", "")
                urgent = est_long or six or evaluation in (0, 1)
                notifier(titre, "\n".join(lignes), lien,
                         priorite="urgent" if urgent else ("high" if bon_prix else "default"),
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
