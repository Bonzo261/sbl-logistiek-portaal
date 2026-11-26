<p align="center"><img src="sbl/static/logo.svg" alt="SBL – StemBureauLogistiek" width="320"></p>

# SBL Logistiek Portaal

**SBL staat voor StemBureauLogistiek.** Webapp voor de logistiek rond stembureaus. Een voorzitter stuurt een sms met alleen het stembureaunummer. De coördinator ziet de melding met adres en telefoonnummer en kiest de (geadviseerde) route. De chauffeur van die route ziet de opdracht, belt de voorzitter en vinkt af.

Elke gemeente draait een eigen installatie (geen multi-tenant) op een eigen server, ook in de cloud. De beheerder van de installatie is zelf verantwoordelijk voor beheer, updates en back-ups.

## Handleidingen
- [Installatie](docs/INSTALLATIE.md)
- [Beheerder](docs/HANDLEIDING-BEHEERDER.md)
- [Coördinator](docs/HANDLEIDING-COORDINATOR.md)
- [Chauffeur](docs/HANDLEIDING-CHAUFFEUR.md)
- [Privacy en beveiliging](docs/PRIVACY-EN-BEVEILIGING.md)

## Functies
**Werkproces**
- Sms-ontvangst via webhook (`/api/sms`); stembureau, adres, voorzitter en route-advies worden automatisch opgezocht
- Portaal voor coördinator/beheerder: *Nieuw → Onderweg → Klaar*, route-advies accepteren of een andere route kiezen; ververst vanzelf en speelt optioneel een geluid bij een nieuw bericht (door de beheerder uit te zetten; browsers eisen dat de gebruiker het geluid eerst met een klik activeert)
- Optioneel (*Beheer → Werkwijze*): de chauffeur moet een toegewezen stembureau eerst accepteren; zolang dat niet gebeurd is kan de coördinator het naar een andere route verplaatsen; een instelbare waarschuwing (oranje/rood) vlagt opdrachten die te lang niet geaccepteerd zijn
- Routepagina per chauffeur met knoppen **Bel voorzitter** en **Navigeer**; ververst zichzelf en meldt een nieuwe opdracht met pop-up, geluid en trillen zolang de pagina open staat (geen pushmelding bij een vergrendelde telefoon)
- Overzichtsscherm voor een grote monitor (`/scherm`): per route het aantal open opdrachten met kleur op wachttijd, wachtende berichten zonder route, klaar vandaag en storingsmelding; ververst zichzelf. Ingelogd, of zonder login via een geheime link die alleen nummers, namen en wachttijden toont

**Beheer**
- Aantal routes instellen; stembureaus handmatig beheren of importeren uit `.csv`, `.xlsx` of `.ods` (slepen-en-neerzetten, met voorbeeld vóór het opslaan)
- Gebruikers beheren, ook in bulk: één chauffeursaccount per route (`route1`, `route2`, …) met een tijdelijk wachtwoord dat bij de eerste login gewijzigd moet worden; acties op een selectie gebruikers (nieuw tijdelijk wachtwoord, 2FA resetten, route wijzigen, verwijderen)
- Back-up: automatisch elke nacht (vanaf 03:00) in de map `backups/` naast de database, met instelbaar aantal te bewaren back-ups; handmatig downloaden en herstellen (*Beheer → Back-up*)
- Logboek van acties

**Bewaking en beveiliging**
- Gateway-heartbeat (`/api/heartbeat`) met storingsmelding bovenaan het scherm en als push via een meldings-URL (bijv. [ntfy](https://ntfy.sh))
- Rollen: **beheerder**, **coördinator**, **chauffeur** (gekoppeld aan één route)
- Tweestapsverificatie (TOTP, met QR-code) is verplicht voor beheerder en coördinator; 8 eenmalige herstelcodes
- Blokkade na 10 mislukte inlogpogingen in 15 minuten, CSRF-bescherming, beveiligde cookies
- Sessies vervallen automatisch bij een wachtwoordwijziging, -reset of 2FA-reset, en je kunt jezelf op andere apparaten uitloggen. Wachtwoord wijzigen door gebruiker zelf; reset door beheerder; "wachtwoord vergeten" per e-mail (link een uur geldig, één keer bruikbaar; 2FA blijft gelden)

## Installatie
### Docker (aanbevolen)
```
docker compose up -d --build
```
of met de kant-en-klare image (zie *Docker-image*):
```
docker run -d --name sbl --restart unless-stopped -p 8000:8000 \
  -v sbl-data:/data -e SBL_HTTPS=1 -e SBL_PROXY=1 <gebruiker>/sbl-logistiek-portaal:latest
```
Open de site, maak het eerste beheerdersaccount aan (minimaal 10 tekens wachtwoord) en stel 2FA in. Stel daarna onder *Beheer* het aantal routes in en importeer de stembureaus. De sms- en heartbeat-URL's staan ook onder *Beheer*.

### Zonder Docker
```
pip install -r requirements.txt
gunicorn -b 127.0.0.1:8000 -w 2 wsgi:app
```
Om te ontwikkelen: `flask --app wsgi run`.

### Productie
- Zet de app achter een reverse proxy met **HTTPS** (Caddy, nginx of Apache/Plesk) en zet `SBL_HTTPS=1` en `SBL_PROXY=1`. Zet `SBL_PROXY` alleen aan als de app niet rechtstreeks bereikbaar is; laat poort 8000 bij voorkeur alleen op `127.0.0.1` luisteren.
- Apache-voorbeeld (extra richtlijnen voor HTTPS):
  ```
  ProxyPreserveHost On
  ProxyRequests Off
  RequestHeader set X-Forwarded-Proto "https"
  ProxyPass /.well-known !
  ProxyPass / http://127.0.0.1:8000/
  ProxyPassReverse / http://127.0.0.1:8000/
  ```
- Bewaar de data in een volume (`/data`). De app maakt elke nacht een back-up in `/data/backups` (te wijzigen met `SBL_BACKUP_DIR`), maar die staat op dezelfde server: download of kopieer regelmatig een back-up naar een andere plek (*Beheer → Back-up*). Een back-up bevat wachtwoord-hashes en 2FA-sleutels: bewaar hem veilig.
- Bijwerken: haal de nieuwste image op en maak de container opnieuw aan; het volume blijft behouden. Zie `CHANGELOG.md` voor wijzigingen.

### Instellingen (omgevingsvariabelen)
| Variabele | Standaard | Betekenis |
|---|---|---|
| `SBL_DATABASE` | `sbl.db` (in Docker: `/data/sbl.db`) | Pad naar de SQLite-database |
| `SBL_HTTPS` | `0` | `1` = cookies alleen via HTTPS (zet aan in productie) |
| `SBL_PROXY` | `0` | `1` = vertrouw `X-Forwarded-*`-headers van een reverse proxy |
| `SBL_2FA_VERPLICHT` | `1` | `0` = 2FA niet verplicht voor beheerder/coördinator |
| `SBL_TIJDZONE` | `Europe/Amsterdam` | Tijdzone voor tijden en bewaking |
| `SBL_SECRET_KEY` | automatisch | Sleutel voor sessies; standaard gegenereerd en in de database bewaard |
| `SBL_BEWAKING` | `1` | `0` = achtergrondtaken (gateway-bewaking en automatische back-up) uitzetten |
| `SBL_BACKUP_DIR` | `<map van database>/backups` | Map voor automatische back-ups |

## E-mail (wachtwoord vergeten)
Onder *Beheer → E-mail* stel je een SMTP-server in: server, poort, beveiliging (STARTTLS/SSL/geen), optioneel gebruiker en wachtwoord, afzenderadres en het webadres van de site (dat komt in de herstellink; het wordt bewust niet uit het verzoek afgeleid). Werkt met elke aanbieder: een postvak van je hosting, Microsoft 365, Google Workspace, een mailservice of de mailrelay van de gemeente. Met *Opslaan en testmail* controleer je de instellingen. Zonder mailinstellingen is er geen "wachtwoord vergeten"; de beheerder reset dan wachtwoorden. Het SMTP-wachtwoord staat in de database en dus in back-ups; wie dat liever niet wil, gebruikt de omgevingsvariabelen `SBL_SMTP_HOST`, `SBL_SMTP_POORT`, `SBL_SMTP_BEVEILIGING`, `SBL_SMTP_GEBRUIKER`, `SBL_SMTP_WACHTWOORD`, `SBL_SMTP_VAN` en `SBL_PUBLIEKE_URL` (die gaan voor op de instellingen in het scherm).

## Sms-forwarder koppelen
Stel in de forwarder een **POST**-webhook in naar de URL onder *Beheer* (`/api/sms?sleutel=…`). De tekst mag in het veld `message`, `text`, `body`, `tekst` of `content` staan, als formulier of JSON; alleen het stembureaunummer is nodig. Voor de bewaking: laat de forwarder regelmatig (GET of POST) `/api/heartbeat?sleutel=…` aanroepen. Na de ingestelde tijd zonder ping (standaard 600 seconden) volgt een storingsmelding. Vul een meldings-URL in (bijv. een geheime ntfy-topic) voor een push naar de telefoon. De sleutel kun je onder *Beheer* vernieuwen.

## API voor een softwareleverancier
Naast de sms-webhook is er een aparte koppeling met een eigen sleutel (*Beheer → Koppeling voor een softwareleverancier*). Standaard staat die uit; zonder sleutel wordt alles geweigerd. De sleutel kun je vernieuwen of intrekken zonder de sms-gateway aan te passen.

```
POST /api/v1/berichten
Authorization: Bearer <sleutel>        (of: X-API-Key: <sleutel>)
Content-Type: application/json

{"stembureau": 12}                      of  {"tekst": "12"}
```
Antwoord `201`: `{"ok": true, "id": 57, "herkend": true, "stembureau": {"nummer": 12, "naam": "School A"}}`. Een onbekend nummer geeft `herkend: false`; het bericht komt dan als niet herkend binnen. Foutcodes: `400` ongeldige invoer, `403` onjuiste of ontbrekende sleutel, `429` te veel foute pogingen vanaf één IP-adres. Zet de sleutel nooit in de URL, zodat hij niet in logs terechtkomt.

## Import
Kopregel verplicht. Herkende kolommen: `nummer` (of `sbNummers`), `naam` (of `locatie`), `adres` (of `straat`/`huisnummer`/`toevoeging`/`postcode`/`plaats`), `telefoon`, `route`. Een weggevallen voorloopnul in een telefoonnummer wordt hersteld. Bestaande stembureaus worden bijgewerkt; optioneel kun je eerst alles wissen.

## Docker-image
Bij elke wijziging op `main` draaien de tests en bouwt GitHub een image voor Docker Hub (`<gebruiker>/sbl-logistiek-portaal:latest`, `amd64` en `arm64`). Dit vereist de repository-secrets `DOCKERHUB_USERNAME` en `DOCKERHUB_TOKEN`.

## Ontwikkelen
```
pip install -r requirements-dev.txt
python -m pytest
```
De code is bewust klein gehouden: Flask + SQLite, geen build-stap. Zie `sbl/app.py` (routes en logica), `sbl/importer.py`, `sbl/totp.py` en `sbl/templates/`. Bijdragen zijn welkom, zie [`CONTRIBUTING.md`](CONTRIBUTING.md); beveiligingsproblemen meld je volgens [`SECURITY.md`](SECURITY.md).

## Roadmap
Automatisch printen (kiosk), optionele Epson ePOS-printer, historie per verkiezing, Postgres.

Wensen:
- Pushmeldingen bij een vergrendelde telefoon (Web Push; op iOS alleen als de site op het beginscherm staat).

## Licentie
GNU Affero General Public License v3.0 of later (AGPL-3.0-or-later). Je mag de software vrij gebruiken en aanpassen; wie aangepaste versies als dienst aanbiedt, moet de aangepaste broncode ook beschikbaar stellen. De volledige tekst staat in `LICENSE`.

## Huisstijl
Logo, kleuren en lettertype (Fira Sans, marine en oranje) staan beschreven in [`docs/HUISSTIJL.md`](docs/HUISSTIJL.md). Logo's en favicon staan in `sbl/static/` en vallen onder dezelfde licentie als de software; het lettertype heeft de SIL Open Font License (zie `sbl/static/fonts/`).
