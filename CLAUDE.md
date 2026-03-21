# Vplan fix – Projektkontext für Claude

> Diese Datei bei jeder Session zuerst lesen. Nach Entscheidungen oder Änderungen aktualisieren.

---

## Was ist dieses Projekt?

Automatischer Vertretungsplan-Checker für die EBG-Schule. Läuft vollständig als GitHub Actions Workflow – kein eigener Server.

Prüft alle 5 Minuten ob sich der Vertretungsplan geändert hat, sendet bei Änderung eine Push-Benachrichtigung via **ntfy** und stellt die aktuelle Ansicht als **GitHub Pages Web-App** bereit.

- **Repository:** GitHub (ebg-vplan-2026-xyz)
- **Benachrichtigung:** ntfy (Push auf Mobilgerät)
- **Web-App:** GitHub Pages unter `docs/`
- **Status:** v1.0 abgeschlossen, läuft produktiv

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

**Milestone v1.1** – Robustheit und Fehlerbehandlung

Kernfunktion läuft stabil, aber der Checker ist noch anfällig gegen:
- Netzwerkprobleme (kein Timeout, kein Retry)
- Unerwartete Vplan-Formate (kein Parsing-Fallback)
- Stille Fehler (keine Benachrichtigung bei dauerhaft fehlgeschlagenem Abruf)

---

## Wichtige Dateien

| Datei | Zweck |
|---|---|
| `check_plan.py` | Vplan abrufen, parsen, Änderung erkennen, ntfy auslösen |
| `generate_data.py` | `data.json` für Web-App erzeugen |
| `state.json` | Letzter bekannter Planstand (via Actions Cache persistiert) |
| `.github/workflows/` | Cron-Workflow-Definition |
| `docs/` | Web-App (GitHub Pages) |

---

## Bekannte Bugs / Eigenheiten

- Shell-Precedenz-Bug in Workflow behoben: `git push` lief früher immer, nicht nur bei Änderungen
- GitHub Actions Cache hat TTL – bei langem Inaktivität kann `state.json` verloren gehen → falscher "Änderung erkannt"

---

## Bewusste Abgrenzungen

- Kein eigener Server – bewusst serverlos via GitHub Actions (Zero-Cost)
- Keine Datenbank – `state.json` als leichtgewichtiger State reicht
- Keine Nutzeranmeldung – Single-User-Tool für privaten Gebrauch

---

## Offene Fragen

- Ist das ntfy-Topic öffentlich oder privat? (Sicherheitsrelevant bei sensiblen Plandaten)

---

## Zuletzt aktualisiert

2026-03-21 (initial, aus BACKLOG.md und README abgeleitet)
