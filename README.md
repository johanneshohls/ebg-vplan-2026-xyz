# EBG Vertretungsplan Checker

Automatischer Vertretungsplan-Checker fuer Indiware/Stundenplan24-Schulen. Laeuft vollstaendig als GitHub Actions Workflow — kein eigener Server noetig.

- Prueft alle 5 Minuten auf Planaenderungen
- Push-Benachrichtigung via [ntfy](https://ntfy.sh) bei Aenderungen
- Web-App (GitHub Pages) mit Wochenansicht pro Lehrkraft
- iCal-Abo pro Lehrkraft
- Aenderungshistorie der letzten 7 Tage

## Eigene Instanz einrichten

### 1. Repository forken/klonen

```bash
git clone <dieses-repo>
cd <repo-name>
```

### 2. GitHub Secrets konfigurieren

Im Repository unter **Settings > Secrets and variables > Actions** folgende Secrets anlegen:

| Secret | Beschreibung | Beispiel |
|--------|-------------|---------|
| `PLAN_URL` | Basis-URL des Stundenplan24-Servers | `https://www.stundenplan24.de/SCHULNUMMER/wplan` |
| `PLAN_USER` | Benutzername fuer Stundenplan24 | `lehrer` |
| `PLAN_PASS` | Passwort fuer Stundenplan24 | `geheim123` |
| `NTFY_TOPIC` | Praefix fuer ntfy-Benachrichtigungen | `meine-schule-vplan` |
| `NOTIFY_EMAIL` | (Optional) E-Mail fuer Fallback-Benachrichtigungen | `mail@example.com` |

### 3. GitHub Pages aktivieren

1. **Settings > Pages**
2. Source: **Deploy from a branch**
3. Branch: `main`, Ordner: `/docs`
4. Speichern

Die Web-App ist danach erreichbar unter `https://<user>.github.io/<repo>/`.

### 4. ntfy einrichten

1. [ntfy-App](https://ntfy.sh) auf dem Smartphone installieren
2. Topic abonnieren: `<NTFY_TOPIC>-<kuerzel>` (z.B. `meine-schule-vplan-hoh`)
3. Optional: globales Topic `<NTFY_TOPIC>` fuer alle Aenderungen abonnieren

### 5. Workflow aktivieren

Der Cron-Workflow laeuft automatisch Mo-Fr von 05:00-17:59 alle 5 Minuten.
Zum manuellen Testen: **Actions > Vertretungsplan pruefen > Run workflow**.

## Projektstruktur

```
check_plan.py          # Aenderungserkennung + ntfy-Benachrichtigung
generate_data.py       # Erzeugt docs/data.json fuer die Web-App
generate_ical.py       # Erzeugt iCal-Dateien pro Lehrkraft
state.json             # Letzter bekannter Planstand (via Actions Cache)
docs/
  index.html           # Web-App (PWA-faehig)
  data.json            # Aktuelle Plandaten (generiert)
  history.json         # Aenderungshistorie der letzten 7 Tage (generiert)
  ical/                # iCal-Feeds pro Lehrkraft (generiert)
  manifest.json        # PWA-Manifest
.github/workflows/
  check.yml            # GitHub Actions Workflow
```

## Web-App nutzen

- URL aufrufen und Lehrkuerzel waehlen
- **Zum Home-Bildschirm hinzufuegen** fuer App-aehnliche Nutzung
- Wochenansicht mit Pfeilen zwischen KWs wechseln
- "Verlauf"-Button zeigt Planaenderungen der letzten 7 Tage
- Rote Markierung = geaenderte Stunde
- Blaue Punkte = Info-Hinweis (antippen fuer Details)

## iCal-Abo

Kalender-URL: `https://<user>.github.io/<repo>/ical/<KUERZEL>.ics`

In Apple Kalender, Google Calendar o.ae. als Abo-Kalender hinzufuegen.

## Anpassen

- **Cron-Zeitfenster**: In `.github/workflows/check.yml` die Cron-Expression aendern
- **Stundenzeiten**: In `check_plan.py` das `STUNDEN_ZEITEN`-Dict anpassen
- **Schulnummer**: Ergibt sich aus der `PLAN_URL` (Stundenplan24-Server der Schule)
