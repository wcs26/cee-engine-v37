#!/usr/bin/env python3
"""Génère l'invitation Google Agenda (.ics) + le corps du mail d'une visite technique.

Usage:
    python3 scripts/rdv_visite_ics.py config.json [--out-dir .]

Le fichier de config JSON contient toutes les données variables (voir EXEMPLE
en bas de fichier). Aucun secret n'est stocké ici.
"""
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]


def date_fr(d: datetime) -> str:
    """'mardi 22 septembre 2026' — évite toute erreur de jour de semaine."""
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}"


def esc(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\;")
                .replace(",", "\\,").replace("\n", "\\n"))


def fold(line: str) -> str:
    """Pliage RFC 5545 à 75 octets."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def build_ics(cfg: dict) -> str:
    tz = cfg.get("tz_offset", "+02:00")  # Europe/Paris en septembre
    start = datetime.fromisoformat(f"{cfg['date']}T{cfg['heure_debut']}:00{tz}")
    end = datetime.fromisoformat(f"{cfg['date']}T{cfg['heure_fin']}:00{tz}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fmt = lambda d: d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SIRAT//Visite technique//FR",
        "CALSCALE:GREGORIAN", "METHOD:REQUEST", "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@sirat-travaux.com",
        f"DTSTAMP:{stamp}", f"DTSTART:{fmt(start)}", f"DTEND:{fmt(end)}",
        f"SUMMARY:{esc(cfg['titre'])}",
        f"LOCATION:{esc(cfg['lieu'])}",
        f"DESCRIPTION:{esc(cfg['description'])}",
        f"ORGANIZER;CN={esc(cfg['organisateur_nom'])}:mailto:{cfg['organisateur_email']}",
        "STATUS:CONFIRMED", "TRANSP:OPAQUE", "SEQUENCE:0",
    ]
    for a in cfg["invites"]:
        lines.append(
            f"ATTENDEE;CN={esc(a['nom'])};ROLE=REQ-PARTICIPANT;"
            f"PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{a['email']}")
    for rappel in cfg.get("rappels_minutes", [1440, 60]):
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY",
                  f"DESCRIPTION:{esc('Rappel : ' + cfg['titre'])}",
                  f"TRIGGER:-PT{rappel}M", "END:VALARM"]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(fold(l) for l in lines) + "\r\n"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cfg = json.loads(open(sys.argv[1], encoding="utf-8").read())
    start = datetime.fromisoformat(f"{cfg['date']}T{cfg['heure_debut']}:00")
    print(f"[check] {date_fr(start)} {cfg['heure_debut']}-{cfg['heure_fin']} "
          f"| {len(cfg['invites'])} invités | organisateur {cfg['organisateur_email']}")
    out = cfg.get("fichier_ics", "visite_technique.ics")
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write(build_ics(cfg))
    print(f"[ok] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
