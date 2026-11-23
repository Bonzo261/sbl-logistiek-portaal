# SBL Logistiek Portaal

Webapp voor de logistiek rond stembureaus (Stembureau-Bezorg-Logistiek): een voorzitter stuurt een sms met alleen het stembureaunummer, de coördinator ziet de melding met adres en telefoonnummer, kiest de (geadviseerde) route, de chauffeur van die route ziet de opdracht, belt de voorzitter en vinkt af.

Elke gemeente draait een eigen installatie (geen multi-tenant). Geen Home Assistant nodig.

## Functies
- Rollen: **beheerder**, **coördinator**, **chauffeur** (gekoppeld aan één route)
- Sms-ontvangst via webhook (`/api/sms`), gateway-heartbeat (`/api/heartbeat`) met storingsmelding
- Portaal: Nieuw → Onderweg → Klaar, route-advies per stembureau of andere route kiezen
- Routepagina per chauffeur met bel- en navigatieknop
- Beheer: aantal routes instellen, stembureaus invoeren of importeren (CSV/Excel met voorbeeld), gebruikers, logboek
- Bon afdrukken via de browser (80 mm)

## Starten
```
docker compose up -d --build
```
Open `http://localhost:8000`, maak het eerste beheerdersaccount aan en stel onder *Beheer* het aantal routes in en importeer de stembureaus. De sms-webhook-URL staat onder *Beheer*.

Zonder Docker: `pip install -r requirements.txt && gunicorn -b 0.0.0.0:8000 wsgi:app` (of `flask --app wsgi run` om te ontwikkelen).

**Productie:** zet de app achter een reverse proxy met HTTPS (bijv. Caddy of nginx) en maak regelmatig een back-up van `data/sbl.db`. De beheerder van de installatie is zelf verantwoordelijk voor beheer, updates en back-ups.

## Import
Kolommen (kopregel verplicht): `nummer`, `naam` of `locatie`, `adres` (of `straat`/`huisnummer`/`toevoeging`/`postcode`/`plaats`), `telefoon`, `route`.

## Ontwikkelen
```
pip install -r requirements-dev.txt
python -m pytest
```
Bijdragen zijn welkom via pull requests.

## Roadmap
Pushmeldingen bij storing, automatisch printen (kiosk), 2FA voor beheerder/coördinator, rate limiting, optionele Epson ePOS-printer, Postgres, historie per verkiezing.
