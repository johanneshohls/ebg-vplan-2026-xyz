"""
Vertretungsplan → iCal-Generator
=================================
Generiert für jede Lehrkraft eine persönliche .ics-Datei unter docs/ical/.

Liest die Daten aus docs/data.json (erzeugt von generate_data.py im selben
Workflow-Run). Keine eigenen HTTP-Calls – funktioniert auch am Wochenende
und außerhalb der Schulzeiten zuverlässig.

Jede Lehrkraft kann ihren Kalender über eine stabile URL abonnieren:
  https://<user>.github.io/<repo>/ical/HOH.ics
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


# --- Konfiguration ---
DATA_JSON  = Path("docs/data.json")
OUTPUT_DIR = Path("docs/ical")
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
    "9": ("15:40", "16:25"),
    "10": ("16:25", "17:10"),
}


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def fold_line(line: str) -> str:
    """Faltet lange Zeilen gemäß RFC 5545 (max. 75 Oktette, Fortsetzung mit CRLF + Leerzeichen)."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line

    result = []
    buf = b""
    for ch in line:
        ch_bytes = ch.encode("utf-8")
        limit = 75 if not result else 74
        if len(buf) + len(ch_bytes) > limit:
            result.append(buf.decode("utf-8"))
            buf = ch_bytes
        else:
            buf += ch_bytes
    if buf:
        result.append(buf.decode("utf-8"))

    return "\r\n ".join(result)


def ical_escape(text: str) -> str:
    """Escapet Sonderzeichen in iCal-Textwerten."""
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def make_dt(date_str: str, time_str: str) -> str:
    """Erzeugt einen iCal-Datetime-String (lokal, ohne Zeitzone = floating time)."""
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H:%M")
    return dt.strftime("%Y%m%dT%H%M%S")


def make_lesson_event(kurz: str, date_str: str, entry: dict, dtstamp: str) -> list[str]:
    """Erzeugt einen VEVENT-Block für eine Unterrichtsstunde."""
    stunde = entry["stunde"]
    times  = STUNDEN.get(stunde)
    if not times:
        return []

    start_time, end_time = times
    fach      = entry["fach"] if entry["fach"] != "---" else "Freistunde"
    klasse    = entry.get("klasse", "")
    raum      = entry.get("raum", "")
    info      = entry.get("info", "")
    geaendert = entry.get("geaendert", False)

    summary = fach
    if klasse:
        summary += f" ({klasse})"
    if geaendert or info:
        summary = f"\u26a0\ufe0f {summary}"

    desc_parts = [f"Std. {stunde}: {fach}"]
    if klasse:
        desc_parts.append(f"Klasse: {klasse}")
    if raum:
        desc_parts.append(f"Raum: {raum}")
    if info:
        desc_parts.append(f"Info: {info}")
    if geaendert:
        desc_parts.append("\u2192 Ge\u00e4ndert!")
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

    uid = f"{kurz.lower()}-{date_str}-auf{vor_stunde or uhrzeit.replace(':', '')}@{DOMAIN}"
    desc_str = "\\n".join(desc_parts)

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{ical_escape(summary)}",
        f"DESCRIPTION:{ical_escape(desc_str)}",
    ]
    if ort:
        lines.append(f"LOCATION:{ical_escape(ort)}")
    lines.append("CATEGORIES:Schule,Aufsicht")
    lines.append("END:VEVENT")
    return lines


def build_ical(kurz: str, days: dict[str, dict], dtstamp: str) -> str:
    """Baut den vollständigen iCal-Inhalt für eine Lehrkraft zusammen."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{SCHOOL}//Vertretungsplan//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{SCHOOL} \u2013 {kurz}",
        "X-WR-CALDESC:Pers\u00f6nlicher Vertretungsplan",
        f"X-WR-LASTUPDATED:{dtstamp}",
    ]

    for date_str in sorted(days):
        teacher_data = days[date_str].get(kurz)
        if not teacher_data:
            continue

        for entry in teacher_data.get("entries", []):
            lines.extend(make_lesson_event(kurz, date_str, entry, dtstamp))

        for auf in teacher_data.get("aufsichten", []):
            lines.extend(make_aufsicht_event(kurz, date_str, auf, dtstamp))

    lines.append("END:VCALENDAR")

    folded = [fold_line(line) for line in lines]
    return "\r\n".join(folded) + "\r\n"


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def main():
    now = datetime.now()
    print(f"=== Generiere iCal-Dateien ({now.strftime('%d.%m.%Y %H:%M')}) ===")

    # data.json laden (erzeugt von generate_data.py im selben Workflow-Run)
    if not DATA_JSON.exists():
        print(f"\u2717 {DATA_JSON} nicht gefunden \u2013 generate_data.py zuerst ausf\u00fchren.")
        sys.exit(1)

    with open(DATA_JSON, encoding="utf-8") as f:
        data = json.load(f)

    print(f"  data.json geladen \u2713")

    # Lehrerliste aus data.json
    teachers = sorted(data.get("lehrer", []))
    print(f"  {len(teachers)} Lehrkr\u00e4fte gefunden")

    # Tagesdaten aus wochen → tage extrahieren
    days: dict[str, dict] = {}
    for woche in data.get("wochen", {}).values():
        for date_str, tag in woche.get("tage", {}).items():
            lehrer_data = tag.get("lehrer", {})
            if lehrer_data:
                days[date_str] = lehrer_data

    if not days:
        print("\n\u2717 Keine Plandaten in data.json \u2013 keine .ics-Dateien erzeugt.")
        sys.exit(0)

    print(f"  {len(days)} Tage mit Plandaten")

    # Ausgabeverzeichnis anlegen
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # iCal-Dateien schreiben
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    written = 0

    for kurz in teachers:
        has_entries = any(kurz in day_data for day_data in days.values())
        if not has_entries:
            continue

        ical_content = build_ical(kurz, days, dtstamp)
        out_path = OUTPUT_DIR / f"{kurz}.ics"
        out_path.write_text(ical_content, encoding="utf-8")
        written += 1

    print(f"\n\u2713 {written} iCal-Dateien in {OUTPUT_DIR}/ geschrieben")


if __name__ == "__main__":
    main()
