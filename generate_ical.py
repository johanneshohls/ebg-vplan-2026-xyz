"""
Vertretungsplan → iCal-Generator
=================================
Liest docs/data.json (wird von generate_data.py erzeugt) und schreibt
für jede Lehrkraft eine persönliche .ics-Datei nach docs/ical/.

Wird von GitHub Actions direkt NACH generate_data.py aufgerufen.
Kein eigener HTTP-Zugriff nötig – nutzt die bereits geholten Daten.

Jede Lehrkraft kann ihren Kalender über eine stabile URL abonnieren:
  https://<user>.github.io/<repo>/ical/HOH.ics
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


# --- Konfiguration ---
DATA_FILE  = os.environ.get("DATA_FILE",  "docs/data.json")
OUTPUT_DIR = os.environ.get("ICAL_DIR",   "docs/ical")
SCHOOL     = "Ernst-Barlach-Gymnasium"
DOMAIN     = "ebg-vplan"

# Stundenzeiten: Stunde → (Start, Ende)
STUNDEN = {
    "1": ("07:40", "08:25"),
    "2": ("08:25", "09:10"),
    "3": ("09:40", "10:25"),
    "4": ("10:25", "11:10"),
    "5": ("11:40", "12:25"),
    "6": ("12:25", "13:10"),
    "7": ("13:40", "14:25"),
    "8": ("14:25", "15:10"),
}


# ---------------------------------------------------------------------------
# iCal-Hilfsfunktionen
# ---------------------------------------------------------------------------

def fold_line(line: str) -> str:
    """Faltet lange Zeilen gemäß RFC 5545 (max. 75 Oktette pro Zeile)."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line

    result = []
    buf = b""
    for ch in line:
        ch_bytes = ch.encode("utf-8")
        limit = 75 if not result else 74  # Fortsetzungszeilen haben 1 Byte Einrückung
        if len(buf) + len(ch_bytes) > limit:
            result.append(buf.decode("utf-8"))
            buf = ch_bytes
        else:
            buf += ch_bytes
    if buf:
        result.append(buf.decode("utf-8"))

    return "\r\n ".join(result)


def ical_escape(text: str) -> str:
    """Escapet Sonderzeichen in iCal-Textwerten (RFC 5545)."""
    return (text
            .replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n"))


def make_dt(date_str: str, time_str: str) -> str:
    """Erzeugt einen iCal-Datetime-String (floating local time)."""
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H:%M")
    return dt.strftime("%Y%m%dT%H%M%S")


# ---------------------------------------------------------------------------
# Event-Erzeuger
# ---------------------------------------------------------------------------

def make_lesson_event(kurz: str, date_str: str, entry: dict, dtstamp: str) -> list[str]:
    """Erzeugt einen VEVENT-Block für eine Unterrichtsstunde."""
    stunde = entry.get("stunde", "")
    times  = STUNDEN.get(stunde)
    if not times:
        return []

    start_time, end_time = times
    fach      = entry.get("fach", "---")
    if fach == "---":
        fach = "Freistunde"
    klasse    = entry.get("klasse", "")
    raum      = entry.get("raum", "")
    info      = entry.get("info", "")
    geaendert = entry.get("geaendert", False)

    # Summary
    summary = fach
    if klasse:
        summary += f" ({klasse})"
    if geaendert or info:
        summary = f"⚠️ {summary}"

    # Description
    desc_parts = [f"Std. {stunde}: {fach}"]
    if klasse:
        desc_parts.append(f"Klasse: {klasse}")
    if raum:
        desc_parts.append(f"Raum: {raum}")
    if info:
        desc_parts.append(f"Info: {info}")
    if geaendert:
        desc_parts.append("→ Geändert!")
    description = "\\n".join(desc_parts)

    uid = f"{kurz.lower()}-{date_str}-std{stunde}@{DOMAIN}"

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{make_dt(date_str, start_time)}",
        f"DTEND:{make_dt(date_str, end_time)}",
        f"SUMMARY:{ical_escape(summary)}",
        f"DESCRIPTION:{ical_escape(description)}",
    ]
    if raum:
        lines.append(f"LOCATION:{ical_escape(raum)}")
    if geaendert or info:
        lines.append("STATUS:TENTATIVE")
    lines.append("CATEGORIES:Schule,Vertretungsplan")
    lines.append("END:VEVENT")
    return lines


def make_aufsicht_event(kurz: str, date_str: str, auf: dict, dtstamp: str) -> list[str]:
    """Erzeugt einen VEVENT-Block für eine Aufsicht."""
    uhrzeit    = auf.get("uhrzeit", "")
    ort        = auf.get("ort", "")
    info       = auf.get("info", "")
    vor_stunde = auf.get("vor_stunde", "")

    if not uhrzeit:
        return []

    try:
        start_dt = datetime.strptime(f"{date_str} {uhrzeit}", "%Y%m%d %H:%M")
        end_dt   = start_dt + timedelta(minutes=10)
    except ValueError:
        return []

    summary = f"Aufsicht {ort}" if ort else "Aufsicht"
    if info:
        summary += f": {info}"

    desc_parts = [f"Aufsicht vor Stunde {vor_stunde}"] if vor_stunde else ["Aufsicht"]
    if ort:
        desc_parts.append(f"Ort: {ort}")
    if info:
        desc_parts.append(f"Info: {info}")
    description = "\\n".join(desc_parts)

    uid = f"{kurz.lower()}-{date_str}-auf{vor_stunde or uhrzeit.replace(':', '')}@{DOMAIN}"

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{ical_escape(summary)}",
        f"DESCRIPTION:{ical_escape(description)}",
    ]
    if ort:
        lines.append(f"LOCATION:{ical_escape(ort)}")
    lines.append("CATEGORIES:Schule,Aufsicht")
    lines.append("END:VEVENT")
    return lines


# ---------------------------------------------------------------------------
# iCal-Builder
# ---------------------------------------------------------------------------

def build_ical(kurz: str, data: dict, dtstamp: str) -> str:
    """
    Baut den vollständigen iCal-Inhalt für eine Lehrkraft.
    data = { date_str: { "lehrer": { kurz: { entries, aufsichten } } } }
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{SCHOOL}//Vertretungsplan//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{SCHOOL} \u2013 {kurz}",
        "X-WR-CALDESC:Persönlicher Vertretungsplan",
        f"X-WR-LASTUPDATED:{dtstamp}",
    ]

    for date_str in sorted(data):
        lehrer_data = data[date_str].get("lehrer", {}).get(kurz)
        if not lehrer_data:
            continue

        for entry in lehrer_data.get("entries", []):
            lines.extend(make_lesson_event(kurz, date_str, entry, dtstamp))

        for auf in lehrer_data.get("aufsichten", []):
            lines.extend(make_aufsicht_event(kurz, date_str, auf, dtstamp))

    lines.append("END:VCALENDAR")

    # RFC 5545: CRLF-Zeilenenden, lange Zeilen falten
    return "\r\n".join(fold_line(line) for line in lines) + "\r\n"


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def main():
    now = datetime.now()
    print(f"=== Generiere iCal-Dateien ({now.strftime('%d.%m.%Y %H:%M')}) ===")

    # data.json einlesen
    data_path = Path(DATA_FILE)
    if not data_path.exists():
        print(f"✗ {DATA_FILE} nicht gefunden – läuft generate_data.py davor?")
        sys.exit(1)

    with open(data_path, encoding="utf-8") as f:
        plan_data = json.load(f)

    teachers = plan_data.get("lehrer", [])
    wochen   = plan_data.get("wochen", {})

    if not teachers or not wochen:
        print("✗ Keine Daten in data.json – Abbruch.")
        sys.exit(1)

    print(f"  {len(teachers)} Lehrkräfte, {len(wochen)} Wochen geladen")

    # Alle Tage aus allen Wochen sammeln
    all_days: dict[str, dict] = {}
    for woche in wochen.values():
        for date_str, day_data in woche.get("tage", {}).items():
            all_days[date_str] = day_data

    print(f"  {len(all_days)} Tage mit Plandaten")

    # Ausgabeverzeichnis anlegen
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    # iCal-Dateien schreiben
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    written = 0

    for kurz in teachers:
        # Nur schreiben wenn die Lehrkraft tatsächlich Einträge hat
        has_entries = any(
            kurz in day.get("lehrer", {})
            for day in all_days.values()
        )
        if not has_entries:
            continue

        ical_content = build_ical(kurz, all_days, dtstamp)
        out_path = out_dir / f"{kurz}.ics"
        out_path.write_text(ical_content, encoding="utf-8")
        written += 1

    print(f"\n✓ {written} iCal-Dateien in {OUTPUT_DIR}/ geschrieben")
    print(f"  Abonnierbar unter: https://<user>.github.io/<repo>/ical/<KÜRZEL>.ics")


if __name__ == "__main__":
    main()
