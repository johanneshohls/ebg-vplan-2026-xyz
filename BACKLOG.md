# Vplan fix – Backlog

> EBG Vertretungsplan Benachrichtigungs-Checker.
> Letzte Aktualisierung: 2026-03-21

---

## Milestone: v1.0

Grundfunktionalität: automatisches Prüfen, Benachrichtigen und Web-App-Ausgabe.

- [x] check_plan.py: Vertretungsplan per HTTP abrufen und parsen (2)
- [x] Änderungserkennung mit state.json und GitHub Actions Cache (3)
- [x] Push-Benachrichtigung via ntfy bei Planänderung (2)
- [x] generate_data.py: data.json für Web-App erzeugen (2)
- [x] GitHub Actions Workflow: automatischer Cron-Schedule alle 5 min (3)
- [x] GitHub Pages Deployment der Web-App aus docs/ (2)
- [x] Shell-Precedenz-Bug in Workflow (git push lief immer) behoben (1)

## Milestone: v1.1

Stabilität und Fehlerbehandlung: der Checker soll robuster gegen Netzwerk- und Format-Probleme werden.

- [x] Fehlerbehandlung bei nicht erreichbarem Vplan (Timeout, HTTP-Fehler) (3)
- [x] Retry-Logik bei fehlgeschlagener ntfy-Benachrichtigung (2)
- [x] Logging: Fehler und Planänderungen strukturiert in Workflow-Logs ausgeben (2)
- [x] Parsing-Logik gegen unerwartete Vplan-Formate absichern (3)
- [x] Benachrichtigung bei dauerhaft fehlgeschlagenem Abruf (Monitoring) (3)

## Milestone: v1.2

Feature-Erweiterungen: bessere Nutzererfahrung und mehr Kontrolle.

- [ ] Web-App: Letzte Planänderung mit Zeitstempel anzeigen (3)
- [ ] Web-App: Historische Planänderungen der letzten 7 Tage einsehbar (5)
- [ ] Filterung nach eigenem Kurs / Fach in der Benachrichtigung (5)
- [ ] E-Mail-Fallback bei fehlgeschlagener Push-Benachrichtigung (3)
- [ ] README mit Setup-Anleitung für eigene Instanzen (2)
