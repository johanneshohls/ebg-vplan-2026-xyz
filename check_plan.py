"""
Vertretungsplan Change Detector v2
===================================
Prüft die Stundenplan24-Website auf Änderungen und sendet
personalisierte Push-Notifications pro Lehrkraft via ntfy.sh.

Jede Lehrkraft abonniert ihren eigenen ntfy-Kanal:
  {NTFY_TOPIC_PREFIX}-{kürzel}   z.B. ebg-vplan-hoh

Datenquelle: Indiware Stundenplan24 XML-API
  - Basis:     wdatenl/SPlanLe_Basis.xml     (Lehrerliste)
  - Tagesplan: wdatenl/WPlanLe_YYYYMMDD.xml  (pro Tag, mit Vertretungen)
"""

import requests
import requests.exceptions
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("vplan")

# --- Konfiguration (über GitHub Secrets / Umgebungsvariablen) ---
BASE_URL = os.environ.get("PLAN_URL", "https://www.stundenplan24.de/40062811/wplan")
PLAN_USER = os.environ.get("PLAN_USER", "lehrer")
PLAN_PASS = os.environ.get("PLAN_PASS", "")
NTFY_TOPIC_PREFIX = os.environ.get("NTFY_TOPIC", "ebg-vplan")
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
AUTH = (PLAN_USER, PLAN_PASS)
HEADERS = {"User-Agent": "Vertretungsplan-Notify/2.0"}
STUNDEN_ZEITEN = {
    "1": "07:40", "2": "08:25", "3": "09:40", "4": "10:25",
    "5": "11:40", "6": "12:25", "7": "13:40", "8": "14:25",
}
# Nach wie vielen aufeinanderfolgenden Fehlschlägen eine Monitoring-Warnung gesendet wird
FETCH_FAIL_ALERT_THRESHOLD = 6  # ~30 min bei 5-min-Intervall


def fetch_xml(path: str, retries: int = 3) -> ET.Element | None:
    """Ruft eine XML-Datei vom Stundenplan-Server ab (mit Retry + Backoff)."""
    url = f"{BASE_URL}/{path}"
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, auth=AUTH, headers=HEADERS, timeout=10)
            if r.status_code == 404:
                return None
            if r.status_code == 401:
                log.error("Authentifizierung fehlgeschlagen für %s (401)", path)
                return None
            r.raise_for_status()
            return ET.fromstring(r.text)
        except requests.exceptions.Timeout:
            log.warning("Timeout bei %s (Versuch %d/%d)", path, attempt, retries)
        except requests.exceptions.ConnectionError:
            log.warning("Verbindungsfehler bei %s (Versuch %d/%d)", path, attempt, retries)
        except requests.exceptions.HTTPError as e:
            log.warning("HTTP-Fehler %d bei %s (Versuch %d/%d)", e.response.status_code, path, attempt, retries)
        except ET.ParseError:
            log.error("Ungültiges XML von %s", path)
            return None
        except Exception as e:
            log.error("Unerwarteter Fehler bei %s: %s", path, e)
            return None

        if attempt < retries:
            wait = 2 ** attempt  # 2s, 4s
            log.info("Warte %ds vor erneutem Versuch...", wait)
            time.sleep(wait)

    log.error("%s nach %d Versuchen nicht erreichbar", path, retries)
    return None


def _safe_text(el, default: str = "") -> str:
    """Extrahiert Text aus einem XML-Element, gibt default zurück wenn None/leer."""
    if el is None:
        return default
    return el.text.strip() if el.text else default


def parse_daily_plan(date_str: str) -> tuple[dict, str, str]:
    """
    Parst den Tagesplan für ein Datum (Format: YYYYMMDD).
    Gibt zurück: (lehrer_dict, datum_text, zeitstempel)
    lehrer_dict: {kürzel: {hash, entries, changes}}
    """
    root = fetch_xml(f"wdatenl/WPlanLe_{date_str}.xml")
    if root is None:
        return {}, "", ""

    ts_el = root.find(".//zeitstempel")
    zeitstempel = _safe_text(ts_el)
    datum_el = root.find(".//DatumPlan")
    datum = _safe_text(datum_el, date_str)

    kl_elements = root.findall(".//Kl")
    if not kl_elements:
        log.warning("Unerwartetes XML-Format für %s: keine <Kl>-Elemente gefunden", date_str)
        return {}, datum, zeitstempel

    result = {}

    for kl in kl_elements:
        try:
            kurz_el = kl.find("Kurz")
            kurz = _safe_text(kurz_el)
            if not kurz:
                continue

            entries = []
            changes = []
            pl = kl.find("Pl")
            if pl is None:
                continue

            for std in pl.findall("Std"):
                try:
                    st = _safe_text(std.find("St"))

                    fa_el = std.find("Fa")
                    fa = _safe_text(fa_el)
                    fa_ae = fa_el.get("FaAe") if fa_el is not None else None

                    le_el = std.find("Le")
                    le = _safe_text(le_el)
                    le_ae = le_el.get("LeAe") if le_el is not None else None

                    ra_el = std.find("Ra")
                    ra = _safe_text(ra_el)
                    ra_ae = ra_el.get("RaAe") if ra_el is not None else None

                    info = _safe_text(std.find("If"))

                    entry = {
                        "stunde": st,
                        "fach": fa.replace("&nbsp;", "---") if fa else "---",
                        "klasse": le.replace("&nbsp;", ""),
                        "raum": ra.replace("&nbsp;", ""),
                        "info": info,
                        "geaendert": bool(fa_ae or le_ae or ra_ae),
                    }
                    entries.append(entry)

                    if entry["geaendert"] or info:
                        changes.append(entry)
                except Exception as e:
                    log.warning("Fehler beim Parsen einer Stunde für %s am %s: %s", kurz, date_str, e)
                    continue

            # Hash für Change-Detection
            content_str = json.dumps(entries, sort_keys=True, ensure_ascii=False)
            content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]

            result[kurz] = {
                "hash": content_hash,
                "entries": entries,
                "changes": changes,
            }
        except Exception as e:
            log.warning("Fehler beim Parsen von Lehrer-Eintrag am %s: %s", date_str, e)
            continue

    return result, datum, zeitstempel


def format_notification(kurz: str, datum: str, data: dict) -> tuple[str, str]:
    """Formatiert Titel und Nachricht für die Push-Notification."""
    changes = data["changes"]
    entries = data["entries"]

    title = f"📋 Plan geändert: {datum}"

    lines = []

    # Änderungen hervorheben
    if changes:
        for c in changes:
            zeit = STUNDEN_ZEITEN.get(c["stunde"], "")
            if c["info"]:
                lines.append(f"⚠️ Std {c['stunde']} ({zeit}): {c['info']}")
            elif c["geaendert"]:
                parts = [c["fach"], c["klasse"]]
                detail = " ".join(p for p in parts if p and p != "---")
                lines.append(f"⚠️ Std {c['stunde']} ({zeit}): {detail} geändert")

    # Vollständiger Tagesplan
    lines.append("")
    lines.append(f"Dein Plan ({datum}):")
    for e in entries:
        zeit = STUNDEN_ZEITEN.get(e["stunde"], "")
        marker = "▸" if e["geaendert"] else " "
        fach = e["fach"] if e["fach"] else "---"
        klasse = e["klasse"]
        raum = f"R.{e['raum']}" if e["raum"] else ""
        parts = [f for f in [fach, klasse, raum] if f]
        info_str = f" ({e['info']})" if e["info"] else ""
        lines.append(f" {marker} Std {e['stunde']} {zeit}: {' '.join(parts)}{info_str}")

    return title, "\n".join(lines)


def send_notification(topic: str, title: str, message: str, priority: str = "high", retries: int = 3) -> bool:
    """Sendet eine Push-Notification über ntfy.sh (mit Retry + Backoff).
    Gibt True zurück wenn erfolgreich, False wenn alle Versuche fehlschlagen."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(
                f"https://ntfy.sh/{topic}",
                data=message.encode("utf-8"),
                headers={
                    "Title": title,
                    "Priority": priority,
                    "Tags": "bell,school",
                    "Click": f"{BASE_URL}/plan.html",
                },
                timeout=10,
            )
            resp.raise_for_status()
            log.info("Notification gesendet → %s", topic)
            return True
        except Exception as e:
            log.warning("ntfy-Fehler bei %s (Versuch %d/%d): %s", topic, attempt, retries, e)
            if attempt < retries:
                wait = 2 ** attempt
                log.info("Warte %ds vor erneutem Versuch...", wait)
                time.sleep(wait)

    log.error("Notification an %s nach %d Versuchen fehlgeschlagen", topic, retries)
    return False


def load_state() -> dict:
    path = Path(STATE_FILE)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict):
    Path(STATE_FILE).write_text(json.dumps(state, ensure_ascii=False, indent=2))


def main():
    if not PLAN_PASS:
        log.critical("PLAN_PASS nicht gesetzt.")
        sys.exit(1)

    now = datetime.now()
    log.info("=== Vertretungsplan-Check %s ===", now.strftime("%d.%m.%Y %H:%M"))

    state = load_state()
    changed_total = 0
    consecutive_failures = state.get("_consecutive_fetch_failures", 0)

    # Erreichbarkeitstest: Basis-XML abrufen
    test = fetch_xml("wdatenl/SPlanLe_Basis.xml")
    if test is None:
        consecutive_failures += 1
        state["_consecutive_fetch_failures"] = consecutive_failures
        log.error("Stundenplan-Server nicht erreichbar (Fehler #%d in Folge)", consecutive_failures)

        if consecutive_failures == FETCH_FAIL_ALERT_THRESHOLD:
            log.warning("Schwellwert erreicht (%d Fehlschläge) – sende Monitoring-Alert", FETCH_FAIL_ALERT_THRESHOLD)
            send_notification(
                NTFY_TOPIC_PREFIX,
                "⚠️ Vplan-Server nicht erreichbar",
                f"Der Stundenplan-Server ist seit {consecutive_failures} aufeinanderfolgenden Prüfungen "
                f"(ca. {consecutive_failures * 5} min) nicht erreichbar.",
                priority="urgent",
            )

        save_state(state)
        sys.exit(1)

    # Server erreichbar → Fehlerzähler zurücksetzen
    if consecutive_failures > 0:
        log.info("Server wieder erreichbar nach %d Fehlschlägen", consecutive_failures)
    state["_consecutive_fetch_failures"] = 0
    log.info("Server erreichbar")

    # Prüfe heute + nächste 4 Werktage
    dates = []
    d = now
    for _ in range(10):
        if d.weekday() < 5:
            dates.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
        if len(dates) >= 5:
            break

    for date_str in dates:
        log.info("--- Prüfe %s ---", date_str)
        daily, datum, zeitstempel = parse_daily_plan(date_str)
        if not daily:
            log.info("Kein Plan verfügbar für %s", date_str)
            continue

        log.info("%d Lehrer geladen, Stand: %s", len(daily), zeitstempel)

        for kurz, data in daily.items():
            key = f"{kurz}_{date_str}"
            old_hash = state.get(key)

            if old_hash is None:
                # Erster Durchlauf → speichern, nicht benachrichtigen
                state[key] = data["hash"]
                continue

            if data["hash"] != old_hash:
                state[key] = data["hash"]

                if not data["changes"]:
                    # Plan hat sich geändert, aber keine echten Vertretungen → kein Push
                    log.info("Plan aktualisiert (keine Vertretungen): %s am %s", kurz, date_str)
                    continue

                # Echte Vertretung erkannt → benachrichtigen
                log.info("VERTRETUNG erkannt: %s am %s (%d Änderungen)", kurz, date_str, len(data["changes"]))
                title, message = format_notification(kurz, datum, data)

                # Persönliche Notification
                personal_topic = f"{NTFY_TOPIC_PREFIX}-{kurz.lower()}"
                send_notification(personal_topic, title, message)

                # Globale Notification (optional)
                send_notification(
                    NTFY_TOPIC_PREFIX, title,
                    f"Vertretung für {kurz} am {datum}",
                    priority="default"
                )

                changed_total += 1
            else:
                state[key] = data["hash"]

    # Alte Einträge aufräumen (> 14 Tage), Metadaten-Keys (mit _ Prefix) behalten
    cutoff = (now - timedelta(days=14)).strftime("%Y%m%d")
    state = {k: v for k, v in state.items() if k.startswith("_") or k.split("_")[-1] >= cutoff}

    save_state(state)
    log.info("=== Fertig: %d Änderungen ===", changed_total)


if __name__ == "__main__":
    main()
