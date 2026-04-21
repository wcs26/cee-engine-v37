"""
PARSER FICHES ATEE → JSON
Extrait les fiches CEE officielles et les structure au format moteur V3.

Format cible par fiche:
{
  "ref": "BAT-EQ-127",
  "nom": "Éclairage LED",
  "secteur": "BAT",          # BAT, IND, AGR, TRA, RES
  "sous_secteur": "EQ",      # TH, EN, EQ, UT, EC, SE...
  "type": "surface",         # surface, unitaire, puissance, logement
  "params": ["surface", "puissance_ref", "duree_vie"],
  "formule": "surface * puissance_ref * duree_vie",
  "conditions": {
    "zone": ["H1", "H2", "H3"],
    "energie": ["electricite"],
    "seuils_min": {}
  }
}
"""

import json
import os
import re
import sys

FICHES_OUTPUT = os.path.join(os.path.dirname(__file__), "fiches.json")

# =========================
# NOMENCLATURE CEE
# =========================

SECTEURS = {
    "BAT": "Bâtiment tertiaire",
    "IND": "Industrie",
    "AGR": "Agriculture",
    "TRA": "Transport",
    "RES": "Résidentiel",
}

SOUS_SECTEURS = {
    "TH": "Thermique",
    "EN": "Enveloppe",
    "EQ": "Équipement",
    "UT": "Utilités",
    "EC": "Économies globales",
    "SE": "Services",
    "BA": "Bâtiment",
    "CH": "Chaleur",
    "FR": "Froid",
}


def parse_ref(ref):
    """Décompose une référence ATEE. Ex: BAT-EQ-127 → (BAT, EQ, 127)"""
    parts = ref.strip().upper().split("-")
    if len(parts) != 3:
        return None, None, None
    return parts[0], parts[1], parts[2]


# =========================
# SAISIE MANUELLE
# =========================

def saisie_fiche():
    """Saisie manuelle d'une fiche CEE."""
    print("\n--- NOUVELLE FICHE ---")

    ref = input("Référence (ex: BAT-EQ-127): ").strip().upper()
    secteur, sous_secteur, num = parse_ref(ref)
    if not secteur:
        print("Référence invalide. Format: XXX-XX-NNN")
        return None

    nom = input("Nom de l'opération: ").strip()

    print("\nType de calcul:")
    print("  1. surface   (kWhc = f(surface))")
    print("  2. unitaire  (kWhc = f(quantité))")
    print("  3. puissance (kWhc = f(puissance kW))")
    print("  4. logement  (kWhc = f(nb logements))")
    choix_type = input("Choix (1-4): ").strip()
    types = {"1": "surface", "2": "unitaire", "3": "puissance", "4": "logement"}
    ftype = types.get(choix_type, "surface")

    print(f"\nParamètres disponibles: surface, quantite, puissance, puissance_ref,")
    print(f"  duree_vie, cop, eer, rendement, r_isolation, nb_logements")
    params_str = input("Paramètres requis (séparés par ,): ").strip()
    params = [p.strip() for p in params_str.split(",") if p.strip()]

    print(f"\nFormule de calcul (utiliser les paramètres ci-dessus)")
    print(f"  Ex: surface * puissance_ref * duree_vie")
    print(f"  Ex: quantite * 3900")
    print(f"  Ex: puissance * 1720 * duree_vie")
    formule = input("Formule: ").strip()

    # Conditions
    print(f"\nZones éligibles (H1,H2,H3 ou vide pour toutes):")
    zones_str = input("Zones: ").strip()
    zones = [z.strip() for z in zones_str.split(",") if z.strip()] or ["H1", "H2", "H3"]

    energies_str = input("Énergies éligibles (electricite,gaz,fioul ou vide pour toutes): ").strip()
    energies = [e.strip() for e in energies_str.split(",") if e.strip()] or []

    seuils = {}
    seuil_str = input("Seuils min (ex: puissance=10,surface=1 ou vide): ").strip()
    if seuil_str:
        for s in seuil_str.split(","):
            if "=" in s:
                k, v = s.split("=", 1)
                seuils[k.strip()] = float(v.strip())

    duree_vie = input("Durée de vie conventionnelle (années): ").strip()
    duree_vie = int(duree_vie) if duree_vie else None

    conditions_texte = input("Conditions texte (séparées par ;): ").strip()
    conditions_list = [c.strip() for c in conditions_texte.split(";") if c.strip()]

    fiche = {
        "ref": ref,
        "nom": nom,
        "secteur": secteur,
        "sous_secteur": sous_secteur,
        "type": ftype,
        "params": params,
        "formule": formule,
        "duree_vie": duree_vie,
        "conditions": {
            "zone": zones,
        },
        "conditions_texte": conditions_list,
    }

    if energies:
        fiche["conditions"]["energie"] = energies
    if seuils:
        fiche["conditions"]["seuils_min"] = seuils

    return fiche


# =========================
# IMPORT CSV BASIQUE
# =========================

def parse_csv(path):
    """
    Parse un CSV de fiches CEE.
    Colonnes attendues: ref,nom,type,params,formule,zones,energies,seuils,duree_vie
    """
    import csv

    fiches = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            secteur, sous_secteur, num = parse_ref(row.get("ref", ""))
            if not secteur:
                continue

            params = [p.strip() for p in row.get("params", "").split(",") if p.strip()]
            zones = [z.strip() for z in row.get("zones", "H1,H2,H3").split(",") if z.strip()]
            energies = [e.strip() for e in row.get("energies", "").split(",") if e.strip()]

            seuils = {}
            for s in row.get("seuils", "").split(","):
                if "=" in s:
                    k, v = s.split("=", 1)
                    seuils[k.strip()] = float(v.strip())

            fiche = {
                "ref": row["ref"].strip().upper(),
                "nom": row.get("nom", "").strip(),
                "secteur": secteur,
                "sous_secteur": sous_secteur,
                "type": row.get("type", "surface").strip(),
                "params": params,
                "formule": row.get("formule", "").strip(),
                "duree_vie": int(row["duree_vie"]) if row.get("duree_vie") else None,
                "conditions": {"zone": zones},
            }

            if energies:
                fiche["conditions"]["energie"] = energies
            if seuils:
                fiche["conditions"]["seuils_min"] = seuils

            fiches.append(fiche)

    return fiches


# =========================
# GESTION FICHIER FICHES
# =========================

def load_existing():
    if os.path.exists(FICHES_OUTPUT):
        with open(FICHES_OUTPUT, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_fiches(fiches):
    with open(FICHES_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(fiches, f, ensure_ascii=False, indent=2)
    print(f"\n{len(fiches)} fiches sauvegardées dans {FICHES_OUTPUT}")


def ajouter_fiche(fiche, fiches):
    """Ajoute ou met à jour une fiche (par ref)."""
    for i, f in enumerate(fiches):
        if f["ref"] == fiche["ref"]:
            fiches[i] = fiche
            print(f"  Fiche {fiche['ref']} mise à jour.")
            return fiches
    fiches.append(fiche)
    print(f"  Fiche {fiche['ref']} ajoutée.")
    return fiches


# =========================
# MAIN
# =========================

def main():
    print("=" * 50)
    print("  PARSER FICHES ATEE → JSON")
    print("=" * 50)

    fiches = load_existing()
    print(f"\n{len(fiches)} fiches existantes.")

    print("\nMode:")
    print("  1. Saisie manuelle (une par une)")
    print("  2. Import CSV")
    print("  3. Lister fiches existantes")
    print("  4. Supprimer une fiche")
    print("  5. Quitter")

    while True:
        choix = input("\nChoix (1-5): ").strip()

        if choix == "1":
            fiche = saisie_fiche()
            if fiche:
                print(f"\n{json.dumps(fiche, ensure_ascii=False, indent=2)}")
                ok = input("Sauvegarder ? (o/n): ").strip().lower()
                if ok == "o":
                    fiches = ajouter_fiche(fiche, fiches)
                    save_fiches(fiches)

        elif choix == "2":
            path = input("Chemin CSV: ").strip()
            if not os.path.exists(path):
                print(f"Fichier {path} introuvable.")
                continue
            nouvelles = parse_csv(path)
            print(f"{len(nouvelles)} fiches lues depuis CSV.")
            for nf in nouvelles:
                fiches = ajouter_fiche(nf, fiches)
            save_fiches(fiches)

        elif choix == "3":
            if not fiches:
                print("Aucune fiche.")
            for f in fiches:
                print(f"  {f['ref']} | {f.get('nom','')} | {f['type']} | {f.get('formule','')}")

        elif choix == "4":
            ref = input("Ref à supprimer: ").strip().upper()
            before = len(fiches)
            fiches = [f for f in fiches if f["ref"] != ref]
            if len(fiches) < before:
                print(f"  {ref} supprimée.")
                save_fiches(fiches)
            else:
                print(f"  {ref} non trouvée.")

        elif choix == "5":
            break

    print("Terminé.")


if __name__ == "__main__":
    main()
