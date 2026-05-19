"""
PARSER PDF FICHES ATEE → JSON
Extrait ref, nom, type, cumac depuis les PDF officiels.
"""

import pdfplumber
import json
import re
import os
import sys

FICHES_PATH = os.path.join(os.path.dirname(__file__), "fiches.json")
PDF_DIR = os.path.join(os.path.dirname(__file__), "pdfs")


def extract_text(path):
    """Extrait le texte d'un PDF. Fallback OCR si le PDF est scanné."""
    text = ""

    # 1. Extraction texte natif (rapide)
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"

    # Nettoyage
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)

    # Debug: sauvegarder le texte extrait
    debug_path = path.replace(".pdf", "_debug.txt")
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write(text)

    # 2. Si peu de texte extrait → fallback OCR
    if len(text.strip()) < 50:
        print("  Texte natif insuffisant, tentative OCR...")
        text = extract_text_ocr(path)

    return text


def extract_text_ocr(path):
    """Extrait le texte par OCR (tesseract) pour les PDF scannés."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        print("  OCR non disponible (pip install pytesseract pdf2image)")
        return ""

    try:
        images = convert_from_path(path, dpi=300)
        text = ""
        for i, img in enumerate(images):
            page_text = pytesseract.image_to_string(img, lang="fra")
            text += page_text + "\n"
            print(f"  OCR page {i+1}/{len(images)}")
        return text
    except Exception as e:
        print(f"  Erreur OCR: {e}")
        return ""


def parse_ref(text):
    """Extrait la référence ATEE (ex: BAT-EQ-127, BAR-TH-104, AGRI-TH-108)."""
    # V39.1.0 fix : ajout BAR (résidentiel) et AGRI (4 lettres au lieu de AGR)
    match = re.search(r"(BAR|BAT|IND|RES|AGRI|TRA)-[A-Z]{2,3}-\d{2,3}", text)
    return match.group(0) if match else None


def parse_nom(text, ref):
    """Extrait le nom de l'opération (ligne après la ref)."""
    if not ref:
        return ""
    pattern = re.escape(ref) + r"[:\s]*(.+?)[\n\r]"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()

    # Fallback: chercher "Opération" ou "Fiche"
    match = re.search(r"(?:Opération|Fiche)[:\s]*(.+?)[\n\r]", text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def parse_type(text):
    """Déduit le type: surface ou unitaire."""
    if re.search(r"par\s+m[²2]", text, re.IGNORECASE):
        return "surface"
    if re.search(r"par\s+(appareil|équipement|logement|unité|luminaire|pompe|moteur)", text, re.IGNORECASE):
        return "unitaire"
    if "surface" in text.lower():
        return "surface"
    return "unitaire"


def parse_cumac_table(text):
    """Extrait les valeurs cumac par zone climatique (tolérant OCR)."""
    cumac = {}

    # Regex large : tolère espaces et erreurs OCR entre H et 1/2/3
    matches = re.findall(r"H\s*([123])\D{0,5}(\d{3,6})", text)
    for zone, value in matches:
        cumac[f"H{zone}"] = int(value)

    # Fallback: capture directe stricte
    if not cumac:
        matches = re.findall(r"(H[123])\s*[:\-]?\s*(\d+)", text)
        for zone, value in matches:
            cumac[zone] = int(value)

    # Fallback: tableau cassé
    if not cumac:
        lines = text.split("\n")
        for i, line in enumerate(lines):
            for zone in ["H1", "H2", "H3"]:
                if zone in line and i + 1 < len(lines):
                    nums = re.findall(r"\d{3,6}", lines[i + 1])
                    if nums:
                        cumac[zone] = int(nums[0])

    return cumac if cumac else None


def parse_duree_vie(text):
    """Extrait la durée de vie conventionnelle."""
    match = re.search(r"[Dd]urée\s+de\s+vie\s*[:\s]*(\d+)\s*ans?", text)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s*ans?\s*(?:de\s+)?durée\s+de\s+vie", text)
    return int(match.group(1)) if match else None


def extract_variables(text):
    """Extrait les variables de calcul depuis le texte d'une fiche complexe."""
    variables = []
    lower = text.lower()

    patterns = {
        "puissance": r"puissance\s*(électrique|nominale|installée)?",
        "surface": r"surface\s*(chauffée|climatisée|habitable)?",
        "nb_compresseurs": r"nombre\s+de\s+compresseurs",
        "nb_logements": r"nombre\s+de\s+logements",
        "quantite": r"nombre\s+d[e']\s*(appareils|équipements|luminaires|unités)",
        "cop": r"\bCOP\b",
        "eer": r"\bEER\b",
        "debit": r"débit\s*(d'air|nominal)?",
        "rendement": r"rendement\s*(thermique|nominal)?",
        "duree_fonctionnement": r"durée\s*(annuelle)?\s*de\s*fonctionnement",
    }

    for var, pattern in patterns.items():
        if re.search(pattern, lower):
            variables.append(var)

    return variables


def detect_complex(text):
    """Détecte si la fiche a un calcul complexe (table multi-paramètres)."""
    keywords = ["puissance", "tableau", "selon", "en fonction de", "nombre de"]
    count = sum(1 for k in keywords if k in text.lower())
    return count >= 2


def detect_expired(text):
    """Détecte si la fiche est abrogée ou expirée."""
    lower = text.lower()
    if "abrogée" in lower or "abrogee" in lower:
        return True
    if "date de fin" in lower:
        return True
    if "n'est plus en vigueur" in lower:
        return True
    return False


def parse_conditions(text):
    """Extrait les conditions d'éligibilité."""
    conditions = []

    # Chercher section conditions
    match = re.search(r"[Cc]onditions?.+?(?:éligibilité|application)[:\s]*(.+?)(?:\n\n|\Z)", text, re.DOTALL)
    if match:
        block = match.group(1)
        for line in block.split("\n"):
            line = line.strip().lstrip("-•◦● ")
            if len(line) > 10 and len(line) < 200:
                conditions.append(line)

    return conditions[:5]


def parse_secteur(ref):
    """Extrait secteur et sous-secteur depuis la ref."""
    if not ref:
        return "", ""
    parts = ref.split("-")
    return parts[0], parts[1] if len(parts) > 1 else ""


def parse_pdf_to_fiche(path):
    """Parse un PDF ATEE et retourne une fiche structurée."""
    text = extract_text(path)
    if not text.strip():
        return None

    ref = parse_ref(text)
    if not ref:
        print(f"  Pas de ref ATEE trouvée dans {path}")
        return None

    secteur, sous_secteur = parse_secteur(ref)
    nom = parse_nom(text, ref)
    ftype = parse_type(text)
    cumac = parse_cumac_table(text)
    duree_vie = parse_duree_vie(text)
    conditions = parse_conditions(text)

    expired = detect_expired(text)
    is_complex = detect_complex(text)
    variables = []

    if is_complex and not cumac:
        ftype = "complexe"
        variables = extract_variables(text)

    fiche = {
        "ref": ref,
        "nom": nom,
        "secteur": secteur,
        "sous_secteur": sous_secteur,
        "type": ftype,
        "duree_vie": duree_vie,
        "actif": not expired,
        "conditions_texte": conditions,
    }

    if variables:
        fiche["variables"] = variables
        fiche["mode_calcul"] = "table"

    if cumac:
        fiche["cumac_unitaire"] = cumac
        if ftype == "surface":
            fiche["params"] = ["surface"]
            fiche["unite"] = "kWhc par m2"
        else:
            fiche["params"] = ["quantite"]
            fiche["unite"] = "kWhc par unité"
    else:
        fiche["cumac_unitaire"] = "A REMPLIR"
        fiche["params"] = []
        print(f"  Cumac non extrait pour {ref} — à remplir manuellement")

    return fiche


def save_fiche(fiche):
    """Ajoute ou met à jour une fiche dans fiches.json."""
    try:
        with open(FICHES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []

    # Remplacer si existe
    data = [f for f in data if f.get("ref") != fiche["ref"]]
    data.append(fiche)

    with open(FICHES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  {fiche['ref']} sauvegardé dans fiches.json")


def parse_folder(folder=None):
    """Parse tous les PDF d'un dossier."""
    folder = folder or PDF_DIR

    if not os.path.isdir(folder):
        print(f"Dossier {folder} inexistant. Création...")
        os.makedirs(folder)
        print(f"Placez vos PDF ATEE dans {folder}/")
        return

    pdfs = [f for f in os.listdir(folder) if f.lower().endswith(".pdf")]
    if not pdfs:
        print(f"Aucun PDF dans {folder}/")
        return

    print(f"{len(pdfs)} PDF trouvés\n")

    for filename in sorted(pdfs):
        path = os.path.join(folder, filename)
        print(f"Parsing: {filename}")
        fiche = parse_pdf_to_fiche(path)
        if fiche:
            print(f"  Ref: {fiche['ref']} | {fiche['nom']} | {fiche['type']}")
            if fiche.get("cumac_unitaire") and fiche["cumac_unitaire"] != "A REMPLIR":
                print(f"  Cumac: {fiche['cumac_unitaire']}")
            save_fiche(fiche)
        print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Parse un seul fichier
        fiche = parse_pdf_to_fiche(sys.argv[1])
        if fiche:
            print(json.dumps(fiche, ensure_ascii=False, indent=2))
            ok = input("\nSauvegarder ? (o/n): ").strip().lower()
            if ok == "o":
                save_fiche(fiche)
    else:
        parse_folder()
