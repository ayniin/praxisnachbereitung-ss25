## Projektstruktur
- backend/app/main.py: FastAPI-Routen, Seitenlogik, Formular-Handling, CSV-Export, Health.
- backend/app/db.py: zentrale DB-Verbindung mit psycopg und dict_row.
- backend/app/models.py: Pydantic-Modelle fuer Eingaben und Datentypen.
- backend/app/templates/: Jinja-Templates fuer Seiten und Teilansichten.
- db/init/001_schema.sql: relationales Schema (student, module, grade) und Seed-Daten.
- docker-compose.yml + Dockerfile: lokaler Stack mit API, Postgres, MQTT.

## Wie Formulare verarbeitet werden
- HTML-Formulare senden meist per POST an FastAPI-Endpunkte.
- FastAPI liest Felder ueber Form(...), z. B. matrikel, vorname, semester.
- Eingaben werden in Pydantic-Modelle gemappt (z. B. StudentCreate, GradeCreate).
- Danach SQL-Ausfuehrung ueber get_conn() und cursor() in main.py.
- Nach Erfolg erfolgt meist RedirectResponse mit Status 303 auf die Uebersichtsseite.
- Bei Noten wird teilweise HTMX genutzt: POST auf /grades/htmx liefert nur HTML-Teilfragment.

## Wie Templates eingebunden sind
- Jinja2Templates wird in main.py mit backend/app/templates als Basisordner initialisiert.
- Seiten werden mit TemplateResponse gerendert und erhalten ein Kontext-Dict.
- request wird immer an das Template uebergeben (wichtig fuer FastAPI/Jinja).
- Vollseiten: index.html, students/index.html, students/edit.html, grades/index.html.
- Partials: grades/_list.html wird in grades/index.html eingebunden.
- Mit HTMX wird genau dieses Partial dynamisch neu geladen (Target grade-list).

## Einfache CRUD-Flows

### Student
- Create: Formular auf /students sendet POST /students, Datensatz wird eingefuegt.
- Read: GET /students liest alle Studierenden und rendert Tabelle.
- Update: GET /students/{id}/edit zeigt Formular, POST /students/{id}/edit speichert Aenderungen.
- Delete: POST /students/{id}/delete loescht den Datensatz und redirectet.

### Module
- Create: Formular auf /grades sendet POST /modules.
- Read: Module werden bei GET /grades fuer Auswahlfelder geladen.
- Update/Delete: aktuell nicht als eigener UI-Flow umgesetzt.

### Grade
- Create: Formular auf /grades sendet POST /grades/htmx, neue Note wird gespeichert.
- Read: GET /grades zeigt Notenliste fuer ausgewaehlte Studierende.
- Read (partial): GET /grades/htmx liefert nur die Tabellenansicht als Partial.
- Update/Delete: aktuell nicht vorhanden, Fokus liegt auf Erfassung + Anzeige + Export.

## Kurzfazit
- Klassischer serverseitiger Flow mit FastAPI + Jinja.
- HTMX reduziert Reloads bei der Notenliste.
- Einfaches, gut nachvollziehbares Lernprojekt fuer Grundmuster von Web + DB + CRUD.
