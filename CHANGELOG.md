# Changelog

Alle noemenswaardige wijzigingen worden hier bijgehouden. Opzet volgens [Keep a Changelog](https://keepachangelog.com/nl/); de versies zijn nog niet getagd.

## [Niet uitgebracht]

> Let op bij bijwerken: iedereen moet na deze update één keer opnieuw inloggen.

### Toegevoegd
- Huisstijl: marine en oranje met Fira Sans (zelf gehost), nieuw logo en favicon (route met vinkje) in de kop, op de inlog- en instelpagina, het overzichtsscherm en in de README; alle pagina's, knoppen, tabellen en het overzichtsscherm in de nieuwe stijl; beschrijving in `docs/HUISSTIJL.md`
- Melding voor chauffeurs bij een nieuwe opdracht op de routepagina: pop-up, geluid, trillen en het scherm blijft aan (aan/uit in *Beheer → Werkwijze*). Als een nog niet geaccepteerde opdracht naar een andere route wordt verplaatst, krijgt de oude route een oranje melding. De routepagina ververst nu zonder te herladen
- Geluidssignaal bij een nieuw bericht in het portaal en op het overzichtsscherm (aan/uit in *Beheer → Werkwijze*); compacte geluidsknop (alleen icoon) in de kop, per apparaat aan/uit. Het portaal ververst nu zonder de pagina te herladen
- Optionele acceptatie door de chauffeur (*Beheer → Werkwijze*): toegewezen opdrachten wachten op acceptatie en kunnen tot dat moment door de coördinator naar een andere route verplaatst worden; ook zichtbaar op het overzichtsscherm; waarschuwing (oranje/rood, instelbaar) als een opdracht te lang niet geaccepteerd is, in het portaal en op het overzichtsscherm
- Overzichtsscherm voor de wand (`/scherm`) met kleurcodering op wachttijd, instelbare drempel en optionele geheime link zonder login (zonder adressen en telefoonnummers)
- Automatische dagelijkse back-up (vanaf 03:00) met bewaartermijn, lijst, download en herstel vanuit het scherm; mislukte back-ups worden gemeld
- Sessies vervallen bij wachtwoordwijziging/-reset en 2FA-reset; knop "Uitloggen op alle andere apparaten"
- "Wachtwoord vergeten" per e-mail via een instelbare SMTP-server (*Beheer → E-mail*, met testmail); herstellink een uur geldig en eenmalig, begrensd aantal aanvragen, 2FA blijft gelden
- E-mailadres per gebruiker (bij installatie, aanmaken, op de accountpagina en door de beheerder; uniek, kleine letters)
- Lijst met tijdelijke wachtwoorden downloaden als Excel (route, gebruikersnaam, wachtwoord, inlog-URL)
- Acties op een selectie gebruikers: nieuw tijdelijk wachtwoord (printbare lijst), wachtwoordwijziging afdwingen, 2FA resetten, route wijzigen en verwijderen
- Bulk aanmaken van chauffeursaccounts per route (`route1`, `route2`, …) met een uniek tijdelijk wachtwoord; printbare lijst die één keer getoond wordt
- Verplichte wachtwoordwijziging bij de eerste login voor bulk-accounts en na een wachtwoordreset door de beheerder
- Back-up downloaden en herstellen vanuit de webinterface
- Herstelcodes (8, eenmalig) voor tweestapsverificatie
- Wachtwoord wijzigen door de gebruiker; wachtwoord resetten door de beheerder
- Terugknoppen in het beheer en slepen-en-neerzetten bij het importeren
- Optie `SBL_PROXY` voor gebruik achter een reverse proxy
- GitHub Action die na geslaagde tests een Docker-image naar Docker Hub publiceert
- QR-code bij het instellen van 2FA (`segno`)

## [0.1.0] – 2026-11-23
Eerste versie, losgemaakt van Home Assistant.

### Toegevoegd
- Datamodel voor stembureaus, routes, berichten, gebruikers en instellingen (SQLite)
- Rollen beheerder, coördinator en chauffeur; chauffeur gekoppeld aan één route
- Sms-webhook, route-advies, portaal (Nieuw → Onderweg → Klaar) en routepagina met bel- en navigatieknop
- Beheer: aantal routes, stembureaus en gebruikers, logboek
- Import van stembureaus uit `.csv`, `.xlsx` en `.ods` met voorbeeld en validatie
- Bon afdrukken via de browser
- Tweestapsverificatie (TOTP), verplicht voor beheerder en coördinator; inlogblokkade na 10 mislukte pogingen
- Gateway-heartbeat met storingsbalk en melding via een meldings-URL (bijv. ntfy)
- Dockerfile, docker-compose, testset en GitHub Actions
- Licentie AGPL-3.0-or-later
