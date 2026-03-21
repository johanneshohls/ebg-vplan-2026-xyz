"""
Vertretungsplan → iCal-Generator
=================================
Generiert für jede Lehrkraft eine persönliche .ics-Datei unter docs/ical/.

Jede Lehrkraft kann ihren Kalender über eine stabile URL abonnieren:
  https://<user>.github.io/<repo>/ical/HOH.ics

Das Skript läuft in GitHub Actions direkt nach generate_data.py.
Die Dateien werden mit dem Rest von docs/ committed und via GitHub Pages bereitgestellt.
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
import requests.exceptions


# --- Konfiguration ---
BASE_URL   = os.environ.get("PLAN_URL",  "https://www.stundenplan24.de/40062811/wplan")
PLAN_USER  = os.environ.get("PLAN_USER", "lehrer")
PLAN_PASS  = os.environ.get("PLAN_PASS", "")
OUTPUT_DIR = os.environ.get("ICAL_DIR",  "docs/ical")
AUTH       = (PLAN_USER, PLAN_PASS)
HEADERS    = {"User-Agent": "Vertretungsplan-Notify/2.0"}
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
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def fetch_xml(path: str, retries: int = 3) -> ET.Element | None:
    """Ruft eine XML-Datei vom Stundenplan-Server ab (mit Retry + Backoff)."""
    url = f"{BASE_URL}/{path}"
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, auth=AUTH, headers=HEADERS, timeout=30)
            if r.status_code == 404:
                return None
            if r.status_code == 401:
                print(f"  ✗ Authentifizierung fehlgeschlagen (401)")
                return None
            r.raise_for_status()
            return ET.fromstring(r.text)
        except requests.exceptions.Timeout:
            print(f"  ✗ Timeout bei {path} (Versuch {attempt}/{retries})")
        except requests.exceptions.ConnectionError:
            print(f"  ✗ Verbindungsfehler bei {path} (Versuch {attempt}/{retries})")
        except requests.exceptions.HTTPError as e:
            print(f"  ✗ HTTP-Fehler {e.response.status_code} (Versuch {attempt}/{retries})")
        except ET.ParseError:
            print(f"  ✗ Ungültiges XML von {path}")
            return None
        except Exception as e:
            print(f"  ✗ Unerwarteter Fehler bei {path}: {e}")
            return None

        if attempt < retries:
            wait = 2 ** attempt
            print(f"    Warte {wait}s vor erneutem Versuch...")
            time.sleep(wait)

    print(f"  ✗ {path} nach {retries} Versuchen nicht erreichbar")
    return None


def parse_daily_plan(date_str: str) -> dict:
    """
    Parst den Tagesplan für ein Datum (Format: YYYYMMDD).
    Gibt dict zurück: { kürzel: { entries: [...], aufsichten: [...] } }
    """
    root = fetch_xml(f"wdatenl/WPlanLe_{date_str}.xml")
    if root is None:
        return {}

    result = {}

    for kl in root.findall(".//Kl"):
        kurz_el = kl.find("Kurz")
        if kurz_el is None or not kurz_el.text:
            continue
        kurz = kurz_el.text.strip()

        # Unterrichtsstunden
        entries = []
        pl = kl.find("Pl")
        if pl is not None:
            for std in pl.findall("Std"):
                st = std.find("St").text if std.find("St") is not None else ""

                fa_el = std.find("Fa")
                fa     = (fa_el.text or "").replace("&nbsp;", "---") if fa_el is not None else ""
                fa_ae  = fa_el.get("FaAe") if fa_el is not None else None

                le_el = std.find("Le")
                le    = (le_el.text or "").replace("&nbsp;", "") if le_el is not None else ""
                le_ae = le_el.get("LeAe") if le_el is not None else None

                ra_el = std.find("Ra")
                ra    = (ra_el.text or "").replace("&nbsp;", "") if ra_el is not None else ""
                ra_ae = ra_el.get("RaAe") if ra_el is not None else None

                info_el = std.find("If")
                info    = info_el.text if info_el is not None and info_el.text else ""

                entries.append({
                    "stunde":   st,
                    "fach":     fa if fa else "---",
                    "klasse":   le,
                    "raum":     ra,
                    "info":     info,
                    "geaendert": bool(fa_ae or le_ae or ra_ae),
                })

        # Aufsichten
        aufsichten = []
        auf_el = kl.find("Aufsichten")
        if auf_el is not None:
            for a in auf_el.findall("Aufsicht"):
                au_vor  = a.find("AuVorStunde").text if a.find("AuVorStunde") is not None else ""
                au_zeit = a.find("AuUhrzeit").text   if a.find("AuUhrzeit")   is not None else ""
                au_ort  = a.find("AuOrt").text       if a.find("AuOrt")       is not None else ""
                au_info = a.find("AuInfo").text       if a.find("AuInfo")      is not None else ""
                aufsichten.append({
                    "vor_stunde": au_vor,
                    "uhrzeit":    au_zeit,
                    "ort":        au_ort,
                    "info":       au_info,
                })

        result[kurz] = {"entries": entries, "aufsichten": aufsichten}

    return result


def fold_line(line: str) -> str:
    """Faltet lange Zeilen gemäß RFC 5545 (max. 75 Oktette, Fortsetzung mit CRLF + Leerzeichen)."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line

    result = []
    buf = b""
    char_iter = iter(line)
    for ch in char_iter:
        ch_bytes = ch.encode("utf-8")
        limit = 75 if not result else 74  # erste Zeile 75, Fortsetzungszeilen 74 (+1 für Leerzeichen)
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
    fach     = entry["fach"] if entry["fach"] != "---" else "Freistunde"
    klasse   = entry.get("klasse", "")
    raum     = entry.get("raum", "")
    info     = entry.get("info", "")
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
    uhrzeit   = auf.get("uhrzeit", "")
    ort       = auf.get("ort", "")
    info      = auf.get("info", "")
    vor_stunde = auf.get("vor_stunde", "")

    if not uhrzeit:
        return []

    # Aufsichten dauern typisch 10 Minuten (Pausenaufsicht)
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
        "X-WR-CALDESC:Persönlicher Vertretungsplan",
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

    # RFC 5545: CRLF-Zeilenenden, lange Zeilen falten
    folded = [fold_line(line) for line in lines]
    return "\r\n".join(folded) + "\r\n"


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def main():
    if not PLAN_PASS:
        print("ERROR: PLAN_PASS nicht gesetzt.")
        sys.exit(1)

    now = datetime.now()
    print(f"=== Generiere iCal-Dateien ({now.strftime('%d.%m.%Y %H:%M')}) ===")

    # Erreichbarkeitstest
    test = fetch_xml("wdatenl/SPlanLe_Basis.xml")
    if test is None:
        print("\n✗ Stundenplan-Server nicht erreichbar – Abbruch.")
        sys.exit(1)
    print("  Server erreichbar ✓")

    # Lehrerliste aus Basis-XML
    teachers = sorted({
        le.find("Kurz").text
        for le in test.findall(".//Le")
        if le.find("Kurz") is not None and le.find("Kurz").text
    })
    print(f"  {len(teachers)} Lehrkräfte gefunden")

    # Datumsbereiche: aktuelle Woche + nächste Woche (Mo-Fr je)
    this_monday = now - timedelta(days=now.weekday())
    dates_to_fetch: list[str] = []
    for week_offset in range(2):
        monday = this_monday + timedelta(weeks=week_offset)
        for day_offset in range(5):
            dates_to_fetch.append((monday + timedelta(days=day_offset)).strftime("%Y%m%d"))

    # Tagespläne laden
    days: dict[str, dict] = {}
    for date_str in dates_to_fetch:
        print(f"\n  Lade {date_str}...")
        plan = parse_daily_plan(date_str)
        if plan:
            days[date_str] = plan
            print(f"    → {len(plan)} Lehrkräfte mit Einträgen")
        else:
            print(f"    → Kein Plan verfügbar")

    if not days:
        print("\n✗ Keine Plandaten verfügbar – keine .ics-Dateien erzeugt.")
        sys.exit(0)

    # Ausgabeverzeichnis anlegen
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    # iCal-Dateien schreiben
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    written = 0

    for kurz in teachers:
        ical_content = build_ical(kurz, days, dtstamp)

        # Nur schreiben wenn der Lehrer tatsächlich Einträge hat
        has_entries = any(kurz in day_data for day_data in days.values())
        if not has_entries:
            continue

        out_path = out_dir / f"{kurz}.ics"
        out_path.write_text(ical_content, encoding="utf-8")
        written += 1

    print(f"\n✓ {written} iCal-Dateien in {OUTPUT_DIR}/ geschrieben")
    print(f"  Abonnierbar unter: https://<user>.github.io/<repo>/ical/<KÜRZEL>.ics")


if __name__ == "__main__":
    main()
