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
- Tweestapsverificatie (TOTP, authenticator-app) — verplicht voor beheerder en coördinator (uitzetten: `SBL_2FA_VERPLICHT=0`)
- Herstelcodes voor 2FA (8 stuks, eenmalig), wachtwoord wijzigen, wachtwoord-reset door beheerder
- Back-up downloaden en herstellen vanuit *Beheer → Back-up*
- Inlogbeveiliging: blokkade na 10 mislukte pogingen
- Storingsmelding bovenaan het scherm en als push via een meldings-URL (bijv. [ntfy](https://ntfy.sh): maak een geheime topic aan, installeer de ntfy-app en vul de URL in onder *Beheer*)

## Starten
```
docker compose up -d --build
```
Open `http://localhost:8000`, maak het eerste beheerdersaccount aan en stel onder *Beheer* het aantal routes in en importeer de stembureaus. De sms-webhook-URL staat onder *Beheer*.

Zonder Docker: `pip install -r requirements.txt && gunicorn -b 0.0.0.0:8000 wsgi:app` (of `flask --app wsgi run` om te ontwikkelen).

**Achter een reverse proxy:** zet `SBL_PROXY=1` zodat het echte IP-adres (voor de inlogblokkade) en `https` worden herkend. Zet dit alleen aan als de app niet rechtstreeks bereikbaar is.

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
Automatisch printen (kiosk),  optionele Epson ePOS-printer, Postgres, historie per verkiezing.

## Licentie
GNU Affero General Public License v3.0 of later (AGPL-3.0-or-later). Je mag de software vrij gebruiken en aanpassen; wie aangepaste versies als dienst aanbiedt, moet de aangepaste broncode ook beschikbaar stellen. De volledige licentietekst staat in het bestand `LICENSE`.

## Docker-image (Docker Hub)
Bij elke wijziging op `main` bouwt GitHub automatisch een image en zet die op Docker Hub (`<gebruiker>/sbl-logistiek-portaal:latest`). Vereist de repository-secrets `DOCKERHUB_USERNAME` en `DOCKERHUB_TOKEN`.
Draaien: `docker run -d -p 8000:8000 -v sbl-data:/data -e SBL_HTTPS=1 <gebruiker>/sbl-logistiek-portaal:latest`
