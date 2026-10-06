# Vplan fix – Projektkontext für Claude

> Diese Datei bei jeder Session zuerst lesen. Nach Entscheidungen oder Änderungen aktualisieren.

---

## Was ist dieses Projekt?

Automatischer Vertretungsplan-Checker für die EBG-Schule. Läuft vollständig als GitHub Actions Workflow – kein eigener Server.

Prüft alle 5 Minuten ob sich der Vertretungsplan geändert hat, sendet bei Änderung eine Push-Benachrichtigung via **ntfy** und stellt die aktuelle Ansicht als **GitHub Pages Web-App** bereit.

- **Repository:** GitHub (ebg-vplan-2026-xyz)
- **Benachrichtigung:** ntfy (Push auf Mobilgerät)
- **Web-App:** GitHub Pages unter `docs/`
- **iCal-Abo:** `docs/ical/<KÜRZEL>.ics` pro Lehrkraft, via GitHub Pages
- **Status:** v1.1 läuft produktiv, iCal-Feature deployed

---

## Tech-Stack

| Was | Womit |
|-----|-------|
| Ausführung | GitHub Actions (Cron, alle 5 min) |
| Sprache | Python |
| Änderungserkennung | `state.json` + GitHub Actions Cache |
| Push | ntfy |
| Web-App | Statisches HTML/JS aus `docs/` |
| Deployment | GitHub Pages |

---

## Aktueller Fokus (Stand 2026-09-03, geprüft 2026-10-05)

Stand 2026-10-05 (Sprint-Analyse KW41): Kein Commit seit 10.09., läuft. Token-Tausch bleibt Zettel, Kandidat für den Zettel-Tag in den Herbstferien.

Stand 2026-09-28 (Sprint-Analyse KW40): Kein Commit seit 10.09., läuft. Kein Sprint-Invest. Token-Tausch nach KW39-Regel auf den Zettel (siehe Blocker).

Läuft produktiv. Seit 03.09.2026 kommen die Hinweise zum Tag mit (Indiware
`<ZusatzInfo><ZiZeile>`): in data.json je Tag als `tagesinfo`, als Karte über dem
Wochenplan, als ganztägiger iCal-Termin, als Meldung auf dem globalen ntfy-Topic
und im Verlauf (Eintrag mit `lehrer: "*"`). Das echte XML hat die Wurzel
`<WplanVp>` mit den Kindern Kopf, FreieTage, Klassen, ZusatzInfo.

**Auslösung des Workflows:** Der GitHub-Zeitplan (`cron` alle 5 min) feuert in
der Praxis nur alle 2 bis 3 Stunden. Deshalb stößt der IONOS-VPS
(`root@87.106.155.168`) den Workflow per `/opt/vplan-trigger.sh` an, Cron
`*/5 5-20 * * 0-5` (Sonntag bis Freitag, sonntags wegen des Montagsplans). Das Skript liest den Token aus `/root/.vplan-github-token`.
Fehlt die Datei oder ist der Token ungültig, steht es in `/var/log/vplan-trigger.log`
mit HTTP-Code.

**Token-Historie:** Der alte PAT in der Crontab war seit 23.03.2026 ungültig (2167
Fehlversuche). Am 03.09.2026 12:46 kam ein gültiger Token hinein, der Trigger lief
sauber - alle 5 Minuten ein `workflow_dispatch`, lückenlos bis 15:35 CEST. Um 15:35
wurde die Datei dann mit einem leeren Wert überschrieben (1 Byte, nur ein Newline),
vermutlich ein `echo "$TOKEN" > ...` mit nicht gesetzter Variable aus einer
SSH-Session heraus. Danach loggte der Cron bis zum 10.09. 09:20 durchgehend
"kein Token" - eine Woche stiller Ausfall, weil niemand ins Log sah. Seit
10.09.2026 09:21 liegt wieder ein Token (Johannes' gh-CLI-Token, Scopes `repo` und
`workflow`, gilt für alle Repos - bei Bedarf gegen einen fine-grained PAT tauschen).

**Ausfall erkennen:** `gh run list` zeigt in der Event-Spalte, woher ein Run kam -
`workflow_dispatch` heißt VPS, `schedule` heißt GitHub-Zeitplan. Stehen dort nur
`schedule`-Zeilen, feuert der VPS nicht. Seit 10.09.2026 macht das der Workflow
`watchdog.yml` automatisch: Er läuft viermal täglich über den GitHub-Zeitplan,
also unabhängig vom VPS, und meldet per ntfy aufs globale Topic, wenn der letzte
`workflow_dispatch` mehr als drei Stunden her ist.

## Offene Fragen / Blocker

- ntfy-Topic: öffentlich oder privat? Sicherheitsrelevant bei sensiblen Plandaten.
- Der Token in `/root/.vplan-github-token` ist seit 10.09. Johannes' gh-CLI-Token (Scopes `repo` und `workflow`, gilt für alle Repos). Auf einem VPS ist das zu breit — gegen einen fine-grained PAT nur für dieses Repo tauschen. Zettel seit 28.09. (dreimal empfohlen, nicht gemacht — kein Sprint-Punkt mehr, bleibt aber ein zu breiter Schlüssel auf einem Server).
- `.claude/` liegt untracked im Working Tree — in `.gitignore` aufnehmen.
- Statuszeile oben sagt "v1.1 läuft produktiv" — BACKLOG.md hat v1.2 komplett abgehakt, Tagesinfo und Watchdog sind live. Beim nächsten Umbau auf v1.2 setzen; der Hinweis unter "Bekannte Bugs" zu `generate_ical.py` ("Push steht aus") ist vermutlich überholt.

---

## Zuletzt aktualisiert

2026-10-05 (Sprint-Analyse KW41: unverändert, läuft.)

2026-09-28 (Sprint-Analyse KW40: unverändert, läuft. Token-Tausch nach KW39-Regel auf den Zettel.)

2026-09-21 (Sprint-Analyse KW39: kein Commit seit 10.09., läuft. Token-Tausch zweite Woche offen. Statuszeile v1.1/v1.2 als veraltet markiert.)

2026-09-14 (Sprint-Analyse KW38: Watchdog vom 10.09. nachgetragen — vier Läufe täglich über den GitHub-Zeitplan, ntfy-Alarm wenn der letzte `workflow_dispatch` über drei Stunden her ist; Konsequenz aus dem einwöchigen stillen Ausfall 03.–10.09. Alten Fokus-Block vom 25.03. als "Fokus davor" markiert, doppelte Blocker-/Datumsabschnitte entfernt. Token-Hinweis bei den Blockern ergänzt.)

2026-09-10 (Neuer Token auf dem VPS 09:21; `watchdog.yml` eingebaut)

2026-09-03 (Tagesinfo eingebaut, VPS-Trigger repariert und mit Token aktiv, Cron So-Fr; defusedxml-Fix vom 31.08. auf main gebracht)

2026-03-25 (v1.2 fast fertig: alle Items abgeschlossen bis auf Kurs/Fach-Filterung; generate_ical.py Push-Problem gelöst)

---

## Wichtige Dateien

| Datei | Zweck |
|---|---|
| `check_plan.py` | Vplan abrufen, parsen, Änderung erkennen, ntfy auslösen |
| `generate_data.py` | `data.json` für Web-App erzeugen |
| `generate_ical.py` | Liest `docs/data.json`, schreibt `docs/ical/<KÜRZEL>.ics` pro Lehrkraft |
| `state.json` | Letzter bekannter Planstand (via Actions Cache persistiert) |
| `.github/workflows/` | Cron-Workflow-Definition |
| `docs/` | Web-App (GitHub Pages) |
| `docs/ical/` | iCal-Feeds pro Lehrkraft (z.B. `Hoh.ics`) |

---

## Wichtige Architektur-Entscheidungen

| Entscheidung | Begründung |
|---|---|
| `generate_ical.py` liest `docs/data.json` statt eigener HTTP-Calls | Erste Version machte eigene HTTP-Calls; das schlug samstags/außerhalb der Schulzeit fehl, weil Plandaten nicht verfügbar. `data.json` ist immer aktuell (wird im selben Workflow-Run davor erstellt). |
| ntfy-Notification nur wenn `data["changes"]` nicht leer | Vorher: Notification bei jeder Hash-Änderung → False Positives bei regulären Plan-Uploads. `changes` enthält nur Stunden mit FaAe/LeAe/RaAe oder Info-Feld. |
| iCal: floating time (keine TZID) | Einfachste Lösung; Kalender-Apps interpretieren die Zeit als Geräte-Localtime, was für deutsche Lehrkräfte korrekt ist. |

## Bekannte Bugs / Eigenheiten

- Shell-Precedenz-Bug in Workflow behoben: `git push` lief früher immer, nicht nur bei Änderungen
- GitHub Actions Cache hat TTL – bei langer Inaktivität kann `state.json` verloren gehen → falscher "Änderung erkannt"
- `generate_ical.py` im Repo ist derzeit noch die alte Version (mit HTTP-Calls) – lokaler Commit mit der data.json-Version liegt vor, aber Push steht aus (GitHub-Credentials fehlen in Claude-Umgebung)

---

## Bewusste Abgrenzungen

- Kein eigener Server – bewusst serverlos via GitHub Actions (Zero-Cost)
- Keine Datenbank – `state.json` als leichtgewichtiger State reicht
- Keine Nutzeranmeldung – Single-User-Tool für privaten Gebrauch

---

## Fokus davor (Stand 2026-03-25, historisch — der aktuelle Fokus steht oben)

**Milestone v1.1** — vollständig abgeschlossen.
**Milestone v1.2** — fast abgeschlossen. Erledigt:
- [x] Externer Cron-Trigger via IONOS VPS (GitHub Actions Schedule unzuverlässig) (3 SP)
- [x] generate_ical.py: data.json statt HTTP-Calls (Wochenende/Ferien-sicher) (2 SP)
- [x] ntfy Push-Notifications debuggen (3 SP)
- [x] Web-App: Letzte Planänderung mit Zeitstempel anzeigen (3 SP)
- [x] Web-App: Historische Planänderungen der letzten 7 Tage (5 SP)
- [x] E-Mail-Fallback bei fehlgeschlagener ntfy-Benachrichtigung (3 SP)
- [x] README mit Setup-Anleitung (2 SP)

- [x] Filterung nach eigenem Kurs / Fach in der Benachrichtigung (5 SP) — laut BACKLOG.md inzwischen erledigt
