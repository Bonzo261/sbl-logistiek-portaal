# Installatiehandleiding

Voor wie het SBL Logistiek Portaal op een eigen server zet. Je hebt een server nodig met Docker (aanbevolen), een domeinnaam met HTTPS en een telefoon met een sms-forwarder-app voor het ontvangen van de sms'jes.

## 1. Voorbereiding
- Een domeinnaam, bijvoorbeeld `portaal.voorbeeld.nl`, die naar de server wijst.
- Een reverse proxy met HTTPS (Caddy, nginx of Apache/Plesk). Zonder HTTPS werken inloggen en de beveiligde cookies niet goed.
- Een telefoon die de sms'jes van de stembureauvoorzitters ontvangt en doorstuurt (de *gateway*). Bij voorkeur een eigen telefoon die aan de lader blijft en niet voor iets anders wordt gebruikt.
- Een lijst van de stembureaus (nummer, naam, adres, telefoon, eventueel route) als `.csv`, `.xlsx` of `.ods`.

## 2. De app starten
### Met Docker Compose (uit de repository)
```
docker compose up -d --build
```
### Met de kant-en-klare image
```
docker run -d --name sbl --restart unless-stopped -p 127.0.0.1:8000:8000 \
  -v sbl-data:/data -e SBL_HTTPS=1 -e SBL_PROXY=1 <gebruiker>/sbl-logistiek-portaal:latest
```
Let op bij Portainer of een andere beheertool:
- Het volume moet op `/data` in de container staan, anders raakt de database bij een nieuwe container kwijt.
- Zet `SBL_HTTPS=1` en `SBL_PROXY=1` bij de omgevingsvariabelen.
- Publiceer poort 8000, bij voorkeur alleen op `127.0.0.1`.

### Zonder Docker
```
pip install -r requirements.txt
gunicorn -b 127.0.0.1:8000 -w 2 wsgi:app
```

## 3. Reverse proxy
Laat de proxy verkeer doorsturen naar `http://127.0.0.1:8000` en laat hem de header `X-Forwarded-Proto` op `https` zetten.

Apache (bijvoorbeeld in Plesk bij *Extra Apache-richtlijnen voor HTTPS*):
```
ProxyPreserveHost On
ProxyRequests Off
RequestHeader set X-Forwarded-Proto "https"
ProxyPass /.well-known !
ProxyPass / http://127.0.0.1:8000/
ProxyPassReverse / http://127.0.0.1:8000/
```
Zet `SBL_PROXY=1` alleen aan als de app niet rechtstreeks van buiten bereikbaar is.

## 4. Eerste keer instellen
1. Open het webadres. Je komt op de pagina om het eerste **beheerdersaccount** aan te maken (wachtwoord minimaal 10 tekens).
2. Stel **tweestapsverificatie** in met een authenticator-app en bewaar de 8 herstelcodes op een veilige plek.
3. Ga naar **Beheer** en stel het **aantal routes** in.
4. Importeer de **stembureaus** (*Beheer → Stembureaus → Importeren*). Sleep het bestand in het scherm; je ziet een voorbeeld voordat er iets wordt opgeslagen.
5. Maak de **chauffeursaccounts** aan (*Beheer → Gebruikers*, bulk): één account per route met een tijdelijk wachtwoord. Download de lijst als Excel om per persoon uit te delen.
6. Maak accounts aan voor de **coördinatoren**.

## 5. De sms-gateway koppelen
Onder *Beheer → Sms-ontvangst en bewaking* staan twee adressen met een geheime sleutel.
- **Sms-webhook** (POST): `https://jouw-domein/api/sms?sleutel=…`. De tekst mag in het veld `message`, `text`, `body`, `tekst` of `content` staan, als formulier of JSON. Alleen het stembureaunummer is nodig.
- **Heartbeat** (GET of POST): `https://jouw-domein/api/heartbeat?sleutel=…`. Laat de forwarder dit elke minuut aanroepen.

Test met een sms vanaf je eigen telefoon. Het bericht verschijnt in het portaal. Bij *Gateway* in Beheer moet "verbonden" staan.

Tips voor de gateway-telefoon:
- Zet batterij-optimalisatie voor de forwarder-app uit ("Geen beperkingen").
- Houd de telefoon aan de lader en op wifi.
- Zet de storingstijd in Beheer op 300 tot 600 seconden.
- Vul een meldings-URL in (bijvoorbeeld een geheime [ntfy](https://ntfy.sh)-topic) om bij een storing een pushbericht te krijgen.

## 6. Eventueel: e-mail
Onder *Beheer → E-mail* stel je een SMTP-server in zodat gebruikers hun wachtwoord per e-mail kunnen herstellen. Vul het webadres van de site in; dat komt in de herstellink. Gebruik *Opslaan en testmail* om te controleren.

## 7. Back-ups
De app maakt elke nacht vanaf 03:00 een back-up in `/data/backups`. Die staat op dezelfde server en beschermt dus niet bij verlies van de server. Download daarom regelmatig een back-up (*Beheer → Back-up*) en bewaar die elders. Een back-up bevat wachtwoord-hashes en 2FA-sleutels: bewaar hem veilig.

## 8. Bijwerken
Haal de nieuwste image op en maak de container opnieuw aan. Het volume blijft behouden. Lees eerst `CHANGELOG.md`. Maak vooraf een back-up.

## 9. Instellingen via omgevingsvariabelen
Zie de tabel in de [README](../README.md#instellingen-omgevingsvariabelen).

## 10. Controlelijst voor je live gaat
- [ ] Site bereikbaar via HTTPS
- [ ] Beheerder heeft 2FA en bewaarde herstelcodes
- [ ] Stembureaus geïmporteerd en gecontroleerd
- [ ] Accounts voor chauffeurs en coördinatoren aangemaakt
- [ ] Testsms ontvangen, ook met een onbekend nummer
- [ ] Gateway toont "verbonden"; storingsmelding getest
- [ ] Back-up gedownload en op een andere plek bewaard
- [ ] Webhook-sleutel is een gegenereerde, geen eigen testsleutel
- [ ] Chauffeurs en coördinatoren hebben hun handleiding
