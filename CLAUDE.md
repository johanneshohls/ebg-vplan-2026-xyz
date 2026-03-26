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

## Aktueller Fokus

**Milestone v1.1** – vollständig abgeschlossen.

Abgeschlossen:
- iCal-Abo pro Lehrkraft (`generate_ical.py` + Workflow-Integration)
- Push-Notifications jetzt nur noch bei echten Vertretungen (nicht bei regulären Plan-Uploads)
- Retry-Logik bei fehlgeschlagener ntfy-Benachrichtigung (3 Versuche, exponentielles Backoff)
- Strukturiertes Logging via Python `logging` Modul (Timestamp + Level in Workflow-Logs)
- Parsing-Absicherung gegen unerwartete XML-Formate (try/except pro Lehrer/Stunde, `_safe_text()` Helper)
- Monitoring: Benachrichtigung nach 6 konsekutiven Fetch-Fehlschlägen (~30 min), Zähler in `state.json`

**Nächster Milestone:** v1.2 (Feature-Erweiterungen)

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

## Aktueller Fokus (Stand 2026-03-25)

**Milestone v1.1** — vollständig abgeschlossen.
**Milestone v1.2** — fast abgeschlossen. Erledigt:
- [x] Externer Cron-Trigger via IONOS VPS (GitHub Actions Schedule unzuverlässig) (3 SP)
- [x] generate_ical.py: data.json statt HTTP-Calls (Wochenende/Ferien-sicher) (2 SP)
- [x] ntfy Push-Notifications debuggen (3 SP)
- [x] Web-App: Letzte Planänderung mit Zeitstempel anzeigen (3 SP)
- [x] Web-App: Historische Planänderungen der letzten 7 Tage (5 SP)
- [x] E-Mail-Fallback bei fehlgeschlagener ntfy-Benachrichtigung (3 SP)
- [x] README mit Setup-Anleitung (2 SP)

Noch offen:
- [ ] Filterung nach eigenem Kurs / Fach in der Benachrichtigung (5 SP)

## Offene Fragen / Blocker

- ntfy-Topic: öffentlich oder privat? Sicherheitsrelevant bei sensiblen Plandaten.

---

## Zuletzt aktualisiert

2026-03-25 (v1.2 fast fertig: alle Items abgeschlossen bis auf Kurs/Fach-Filterung; generate_ical.py Push-Problem gelöst)
