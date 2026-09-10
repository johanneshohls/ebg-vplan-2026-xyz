#!/usr/bin/env python3
"""
Prüft, ob der VPS-Trigger noch feuert.

Der Vertretungsplan-Workflow wird vom IONOS-VPS alle 5 Minuten per
workflow_dispatch angestoßen; der GitHub-eigene Zeitplan (schedule) feuert
daneben nur alle paar Stunden. Fällt der VPS-Trigger aus - kaputter Token,
abgelaufener PAT, Cron gestoppt -, läuft der Plan-Check weiter, nur eben
zwei- bis viermal am Tag statt alle fünf Minuten. Das fällt niemandem auf.

Am 03.09.2026 blieb genau dieser Ausfall eine Woche lang unbemerkt, weil das
Trigger-Log nur auf dem VPS lag. Dieses Skript schaut von außen nach und
meldet sich über denselben ntfy-Kanal wie der Server-nicht-erreichbar-Alarm.
"""
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("watchdog")

REPO = os.environ.get("GITHUB_REPOSITORY", "johanneshohls/ebg-vplan-2026-xyz")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "") or "ebg-vplan"
WORKFLOW = "check.yml"

# So lange darf der letzte VPS-Dispatch her sein, bevor Alarm ausgelöst wird.
# Der Cron feuert alle 5 min; drei Stunden Stille sind eindeutig ein Ausfall
# und nicht bloß ein verschluckter Lauf.
MAX_STILLE = timedelta(hours=3)

# Aktives Fenster des VPS-Crons: */5 5-20 * * 0-6 (Sonntag bis Freitag).
# Außerhalb ist Stille normal und kein Alarmgrund.
AKTIVE_STUNDEN = range(6, 21)
TZ = ZoneInfo("Europe/Berlin")


def im_aktiven_fenster(jetzt: datetime) -> bool:
    lokal = jetzt.astimezone(TZ)
    # weekday(): Montag 0 ... Samstag 5, Sonntag 6. Samstag läuft der Cron nicht.
    if lokal.weekday() == 5:
        return False
    return lokal.hour in AKTIVE_STUNDEN


def letzter_dispatch() -> datetime | None:
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/runs"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    resp = requests.get(
        url, headers=headers, params={"event": "workflow_dispatch", "per_page": 1}, timeout=30
    )
    resp.raise_for_status()
    runs = resp.json().get("workflow_runs", [])
    if not runs:
        return None
    return datetime.fromisoformat(runs[0]["created_at"].replace("Z", "+00:00"))


def melde(titel: str, text: str) -> bool:
    try:
        resp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=text.encode("utf-8"),
            headers={"Title": titel.encode("utf-8"), "Priority": "high", "Tags": "warning"},
            timeout=30,
        )
        resp.raise_for_status()
        log.info("Warnung an ntfy-Topic %s gesendet", NTFY_TOPIC)
        return True
    except Exception as e:
        log.error("ntfy-Meldung fehlgeschlagen: %s", e)
        return False


def main() -> int:
    jetzt = datetime.now(timezone.utc)

    if not im_aktiven_fenster(jetzt):
        log.info("Außerhalb des Cron-Fensters (So-Fr 6-20 Uhr) - keine Prüfung")
        return 0

    try:
        zuletzt = letzter_dispatch()
    except Exception as e:
        log.error("Runs konnten nicht abgefragt werden: %s", e)
        return 0  # Kein Workflow-Fehler, beim nächsten Lauf erneut versuchen

    if zuletzt is None:
        melde(
            "VPS-Trigger feuert nicht",
            "Es gibt überhaupt keinen workflow_dispatch-Lauf. Der Vertretungsplan wird nur "
            "noch alle paar Stunden geprüft. Auf dem VPS nachsehen: "
            "/var/log/vplan-trigger.log und /root/.vplan-github-token.",
        )
        return 0

    stille = jetzt - zuletzt
    stunden = stille.total_seconds() / 3600

    if stille > MAX_STILLE:
        log.warning("Letzter VPS-Dispatch vor %.1f Stunden - Alarm", stunden)
        melde(
            "VPS-Trigger feuert nicht",
            f"Der letzte Anstoß vom VPS ist {stunden:.1f} Stunden her "
            f"({zuletzt.astimezone(TZ):%d.%m. %H:%M} Uhr). Der Vertretungsplan wird derzeit nur "
            "über den GitHub-Zeitplan geprüft, also alle zwei bis vier Stunden. "
            "Auf dem VPS nachsehen: /var/log/vplan-trigger.log und /root/.vplan-github-token.",
        )
    else:
        log.info("Letzter VPS-Dispatch vor %.0f Minuten - alles in Ordnung", stille.total_seconds() / 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
