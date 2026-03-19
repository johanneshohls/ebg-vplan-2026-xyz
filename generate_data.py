"""
Generiert docs/data.json aus den Stundenplan24-XML-Daten.
Wird von GitHub Actions aufgerufen. Die HTML-Seite lädt data.json.
"""

import requests
import json
import os
import sys
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

BASE_URL = os.environ.get("PLAN_URL", "https://www.stundenplan24.de/40062811/wplan")
PLAN_USER = os.environ.get("PLAN_USER", "lehrer")
PLAN_PASS = os.environ.get("PLAN_PASS", "")
AUTH = (PLAN_USER, PLAN_PASS)
HEADERS = {"User-Agent": "Vertretungsplan-Notify/2.0"}
OUTPUT = os.environ.get("OUTPUT_FILE", "docs/data.json")


def fetch_xml(path: str) -> ET.Element | None:
    url = f"{BASE_URL}/{path}"
    try:
        r = requests.get(url, auth=AUTH, headers=HEADERS, timeout=30)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return ET.fromstring(r.text)
    except Exception as e:
        print(f"  Fehler: {path}: {e}")
        return None


def get_teacher_list() -> list[str]:
    root = fetch_xml("wdatenl/SPlanLe_Basis.xml")
    if root is None:
        return []
    return [le.find("Kurz").text for le in root.findall(".//Le")
            if le.find("Kurz") is not None and le.find("Kurz").text]


def parse_daily_plan(date_str: str) -> dict | None:
    root = fetch_xml(f"wdatenl/WPlanLe_{date_str}.xml")
    if root is None:
        return None

    ts_el = root.find(".//zeitstempel")
    datum_el = root.find(".//DatumPlan")

    day_data = {
        "datum": datum_el.text if datum_el is not None else date_str,
        "zeitstempel": ts_el.text if ts_el is not None else "",
        "lehrer": {},
    }

    for kl in root.findall(".//Kl"):
        kurz_el = kl.find("Kurz")
        if kurz_el is None or not kurz_el.text:
            continue
        kurz = kurz_el.text.strip()

        entries = []
        pl = kl.find("Pl")
        if pl is None:
            continue

        for std in pl.findall("Std"):
            st = std.find("St").text if std.find("St") is not None else ""

            fa_el = std.find("Fa")
            fa = (fa_el.text or "").replace("&nbsp;", "---") if fa_el is not None else ""
            fa_ae = fa_el.get("FaAe") if fa_el is not None else None

            le_el = std.find("Le")
            le = (le_el.text or "").replace("&nbsp;", "") if le_el is not None else ""

            ra_el = std.find("Ra")
            ra = (ra_el.text or "").replace("&nbsp;", "") if ra_el is not None else ""
            ra_ae = ra_el.get("RaAe") if ra_el is not None else None

            info_el = std.find("If")
            info = info_el.text if info_el is not None and info_el.text else ""

            entries.append({
                "stunde": st,
                "fach": fa if fa else "---",
                "klasse": le,
                "raum": ra,
                "info": info,
                "geaendert": bool(fa_ae or ra_ae),
            })

        day_data["lehrer"][kurz] = {"entries": entries}

    return day_data


def main():
    if not PLAN_PASS:
        print("ERROR: PLAN_PASS nicht gesetzt.")
        sys.exit(1)

    now = datetime.now()
    print(f"=== Generiere data.json ({now.strftime('%d.%m.%Y %H:%M')}) ===")

    # Lehrerliste holen
    lehrer_list = get_teacher_list()
    print(f"Lehrer: {len(lehrer_list)}")

    # Nächste 5 Werktage parsen
    tage = {}
    d = now
    for _ in range(10):
        if d.weekday() < 5:
            ds = d.strftime("%Y%m%d")
            print(f"  Lade {ds}...")
            day = parse_daily_plan(ds)
            if day:
                tage[ds] = day
        d += timedelta(days=1)
        if len(tage) >= 5:
            break

    data = {
        "schule": "Ernst-Barlach-Gymnasium",
        "generiert": now.strftime("%d.%m.%Y, %H:%M Uhr"),
        "lehrer": lehrer_list,
        "tage": tage,
    }

    # Schreiben
    os.makedirs(os.path.dirname(OUTPUT) or ".", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    size = os.path.getsize(OUTPUT)
    print(f"\n✓ {OUTPUT} geschrieben ({size:,} Bytes, {len(tage)} Tage)")


if __name__ == "__main__":
    main()
