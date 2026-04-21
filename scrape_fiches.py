"""
SCRAPER FICHES CEE OFFICIELLES
Source: site du ministère de l'écologie
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import os
import time

FICHES_PATH = os.path.join(os.path.dirname(__file__), "fiches.json")

SOURCES = [
    "https://www.ecologie.gouv.fr/operations-standardisees-deconomies-denergie",
    "https://www.ecologie.gouv.fr/politiques-publiques/operations-standardisees-deconomies-denergie",
    "https://www.ecologie.gouv.fr/operations-standardisees-deconomies-denergie-secteur-tertiaire",
    "https://www.ecologie.gouv.fr/operations-standardisees-deconomies-denergie-industrie",
    "https://www.ecologie.gouv.fr/operations-standardisees-deconomies-denergie-residentiel",
    "https://www.ecologie.gouv.fr/operations-standardisees-deconomies-denergie-transport",
    "https://www.ecologie.gouv.fr/operations-standardisees-deconomies-denergie-agriculture",
]


def get_all_fiche_urls():
    """Récupère les URLs de toutes les fiches depuis le site officiel."""
    urls = set()

    for base_url in SOURCES:
        try:
            print(f"  Scan: {base_url}")
            res = requests.get(base_url, timeout=15)
            if res.status_code != 200:
                print(f"  HTTP {res.status_code}")
                continue

            soup = BeautifulSoup(res.text, "html.parser")

            for link in soup.find_all("a", href=True):
                href = link["href"].lower()
                if any(x in href for x in ["bat-", "ind-", "res-", "tra-", "agr-"]):
                    full = href if href.startswith("http") else base_url.split("/operations")[0] + href
                    urls.add(full)

        except Exception as e:
            print(f"  Erreur: {e}")

    return list(urls)


def parse_fiche_page(url):
    """Parse une page de fiche CEE."""
    try:
        res = requests.get(url, timeout=15)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        # Référence
        ref_match = re.search(r"(BAT|IND|RES|TRA|AGR)-[A-Z]{2}-\d{2,3}", text)
        if not ref_match:
            return None
        ref = ref_match.group(0)

        # Nom (texte après la ref)
        nom = ""
        nom_match = re.search(re.escape(ref) + r"[:\s]+(.+?)(?:\.|$)", text)
        if nom_match:
            nom = nom_match.group(1).strip()[:100]

        # Secteur
        secteur = ref.split("-")[0]

        # Type
        ftype = "surface" if re.search(r"par\s+m[²2]", text, re.IGNORECASE) else "unitaire"

        # Cumac par zone (tolérant)
        cumac = {}
        matches = re.findall(r"H\s*([123])\D{0,5}(\d{3,6})", text)
        for zone, value in matches:
            cumac[f"H{zone}"] = int(value)

        # Durée de vie
        duree = None
        dv_match = re.search(r"(\d+)\s*ans?", text)
        if dv_match:
            val = int(dv_match.group(1))
            if 5 <= val <= 50:
                duree = val

        return {
            "ref": ref,
            "nom": nom,
            "secteur": secteur,
            "type": ftype,
            "cumac_unitaire": cumac if cumac else "A VERIFIER",
            "duree_vie": duree,
            "source_url": url,
            "params": ["surface"] if ftype == "surface" else ["quantite"],
        }

    except Exception as e:
        print(f"  Erreur parse: {e}")
        return None


def find_pdf_links(soup, base_url):
    """Trouve les liens vers les PDF dans une page."""
    pdfs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href.lower():
            full = href if href.startswith("http") else base_url + href
            pdfs.append(full)
    return list(set(pdfs))


def download_pdf(url, folder=None):
    """Télécharge un PDF dans le dossier pdfs/."""
    folder = folder or os.path.join(os.path.dirname(__file__), "pdfs")
    os.makedirs(folder, exist_ok=True)

    filename = url.split("/")[-1].split("?")[0]
    if not filename.endswith(".pdf"):
        filename += ".pdf"
    path = os.path.join(folder, filename)

    if os.path.exists(path):
        return path

    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and len(r.content) > 1000:
            with open(path, "wb") as f:
                f.write(r.content)
            print(f"  PDF: {filename}")
            return path
    except Exception as e:
        print(f"  PDF erreur: {e}")

    return None


def merge_fiches(nouvelles):
    """Merge les nouvelles fiches dans fiches.json sans écraser les existantes."""
    try:
        with open(FICHES_PATH, "r", encoding="utf-8") as f:
            existantes = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existantes = []

    refs_existantes = {f["ref"] for f in existantes}
    ajoutees = 0

    for nf in nouvelles:
        if nf["ref"] not in refs_existantes:
            existantes.append(nf)
            ajoutees += 1
            print(f"  + {nf['ref']} ajoutée")
        else:
            print(f"  = {nf['ref']} existe déjà")

    with open(FICHES_PATH, "w", encoding="utf-8") as f:
        json.dump(existantes, f, ensure_ascii=False, indent=2)

    return ajoutees


def main():
    print("\n===== SCRAPER FICHES CEE =====\n")

    urls = get_all_fiche_urls()
    print(f"\n{len(urls)} URLs trouvées\n")

    fiches = []
    for i, url in enumerate(urls):
        print(f"[{i+1}/{len(urls)}] {url[:80]}")
        fiche = parse_fiche_page(url)
        if fiche:
            fiches.append(fiche)
            print(f"  {fiche['ref']} | {fiche['nom'][:50]}")
        time.sleep(0.5)  # politesse

    print(f"\n{len(fiches)} fiches extraites")

    if fiches:
        ajoutees = merge_fiches(fiches)
        print(f"{ajoutees} nouvelles fiches ajoutées à fiches.json")


if __name__ == "__main__":
    main()
