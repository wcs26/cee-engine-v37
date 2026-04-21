#!/usr/bin/env python3
"""
Extraction robuste des FICHES_CATALOGUE depuis Oracle V34 HTML.
Utilise Node.js pour parser le JS natif.
"""
import subprocess
import json
import os

HTML_PATH = os.path.expanduser("~/Downloads/WCS_ORACLE_V34_ULTIMATE.html")
ENGINE_DIR = os.path.dirname(__file__)

# Lire le HTML et trouver le bloc FICHES_CATALOGUE
with open(HTML_PATH, "r", encoding="utf-8") as f:
    html = f.read()

# Trouver début et fin
start_marker = "const FICHES_CATALOGUE = ["
start = html.index(start_marker) + len(start_marker) - 1  # inclure le [

# Trouver la fin du tableau (]; après le dernier })
depth = 0
i = start
while i < len(html):
    c = html[i]
    if c == '[':
        depth += 1
    elif c == ']':
        depth -= 1
        if depth == 0:
            end = i + 1
            break
    elif c in ('"', "'"):
        quote = c
        i += 1
        while i < len(html) and html[i] != quote:
            if html[i] == '\\':
                i += 1
            i += 1
    elif c == '/' and i + 1 < len(html) and html[i + 1] == '/':
        while i < len(html) and html[i] != '\n':
            i += 1
    i += 1

js_array = html[start:end]

# Utiliser Node.js pour parser le JS natif
node_script = f"""
const data = {js_array};
process.stdout.write(JSON.stringify(data));
"""

result = subprocess.run(
    ["node", "-e", node_script],
    capture_output=True, text=True, timeout=10
)

if result.returncode != 0:
    print(f"ERREUR Node: {result.stderr[:500]}")
    exit(1)

fiches_oracle = json.loads(result.stdout)
print(f"OK: {len(fiches_oracle)} fiches Oracle extraites")

# Sauvegarder brut
raw_path = os.path.join(ENGINE_DIR, "fiches_oracle_raw.json")
with open(raw_path, "w", encoding="utf-8") as f:
    json.dump(fiches_oracle, f, ensure_ascii=False, indent=2)
print(f"Sauvegardé: {raw_path}")

# Convertir au format Engine et merger
from merge_oracle import oracle_to_engine_fiche, merge_fiches

oracle_converted = [oracle_to_engine_fiche(f) for f in fiches_oracle]

# Charger fiches Engine (backup)
backup_path = os.path.join(ENGINE_DIR, "fiches.json.backup")
fiches_path = os.path.join(ENGINE_DIR, "fiches.json")

if os.path.exists(backup_path):
    with open(backup_path, "r", encoding="utf-8") as f:
        engine_fiches = json.load(f)
else:
    with open(fiches_path, "r", encoding="utf-8") as f:
        engine_fiches = json.load(f)

print(f"Engine: {len(engine_fiches)} fiches")

# Merger
merged = merge_fiches(oracle_converted, engine_fiches)

oracle_refs = set(f.get("ref") for f in fiches_oracle)
engine_refs = set(f["ref"] for f in engine_fiches)
print(f"\nOracle: {len(oracle_refs)} refs")
print(f"Engine: {len(engine_refs)} refs")
print(f"Communs: {len(oracle_refs & engine_refs)}")
print(f"Oracle uniquement: {len(oracle_refs - engine_refs)}")
print(f"Engine uniquement: {len(engine_refs - oracle_refs)}")
print(f"TOTAL FUSIONNÉ: {len(merged)}")

# Sauvegarder
with open(fiches_path, "w", encoding="utf-8") as f:
    json.dump(merged, f, ensure_ascii=False, indent=2)
print(f"\nfiches.json mis à jour: {len(merged)} fiches")
