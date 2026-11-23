# Handleiding beheerder

De beheerder richt het portaal in en houdt het gezond. Alles staat onder **Beheer** (alleen zichtbaar voor beheerders). Een beheerder kan daarnaast alles wat een coördinator kan.

## Inloggen en account
- Je logt in met naam, wachtwoord en een code uit je authenticator-app (2FA).
- Onder **Mijn account** wijzig je je wachtwoord, e-mailadres (nodig voor "wachtwoord vergeten") en 2FA. Je kunt jezelf daar ook op andere apparaten uitloggen.
- Raak je je telefoon kwijt: gebruik een van de 8 herstelcodes. Elke code werkt één keer. Een andere beheerder kan je 2FA resetten.

## Aantal routes
Stel het aantal routes in. Een route die nog stembureaus of openstaande berichten heeft, kun je niet weghalen.

## Stembureaus
- *Beheer → Stembureaus*: handmatig toevoegen, wijzigen of verwijderen.
- **Importeren**: sleep een `.csv`, `.xlsx` of `.ods` in het scherm. Een kopregel is verplicht. Herkende kolommen: `nummer` (of `sbNummers`), `naam` (of `locatie`), `adres` (of straat/huisnummer/toevoeging/postcode/plaats), `telefoon`, `route`. Je ziet eerst een voorbeeld. Bestaande stembureaus worden bijgewerkt; je kunt eerst alles wissen.
- Controleer na de import adressen en telefoonnummers steekproefsgewijs.

## Gebruikers
- *Beheer → Gebruikers*: rollen zijn **beheerder**, **coördinator** en **chauffeur** (gekoppeld aan één route).
- **In bulk chauffeursaccounts maken**: één per route (`route1`, `route2`, …) met een tijdelijk wachtwoord. Bij de eerste keer inloggen moet het wachtwoord gewijzigd worden. Download de lijst met tijdelijke wachtwoorden als Excel om per persoon uit te delen.
- **Selectie**: vink gebruikers aan en kies een actie: nieuw tijdelijk wachtwoord, 2FA resetten, route wijzigen of verwijderen.
- Een wachtwoordwijziging of reset beëindigt alle lopende sessies van die gebruiker.
- Bij een blokkade na te veel inlogpogingen: wacht 15 minuten.

## Werkwijze
*Beheer → Werkwijze*:
- **Acceptatie door chauffeur**: aan = de chauffeur moet een toegewezen stembureau eerst accepteren ("ik ga erheen"). Zolang dat niet is gebeurd kan de coördinator het naar een andere route verplaatsen; de oude route krijgt daarvan een melding. Een instelbare waarschuwing kleurt niet-geaccepteerde opdrachten oranje en later rood.
- **Geluid bij nieuw bericht** voor coördinatoren, en **melding voor chauffeurs** (pop-up, geluid, trillen). Beide kun je uitzetten.

## Sms-ontvangst en bewaking
- Hier staan de **webhook-** en **heartbeat-URL** met de geheime sleutel, en de status van de gateway: verbonden, storing of nog geen heartbeat, met de tijd van de laatste heartbeat en sms.
- **Storing na** … seconden: aanbevolen 300 tot 600 bij een ping per minuut.
- **Meldings-URL**: bijvoorbeeld een geheime ntfy-topic. Je krijgt een pushbericht bij een storing en bij herstel.
- **Webhook-sleutel**: kies *huidige behouden*, *nieuwe veilige sleutel* of *zelf invullen*. Een zelfgekozen sleutel is makkelijk te raden; gebruik die alleen om te testen. Na het wijzigen moet de sleutel ook in de gateway aangepast worden.

## Overzichtsscherm
`/scherm` toont op een grote monitor per route het aantal open opdrachten (kleur op wachttijd), wachtende berichten, klaar vandaag en een storingsbalk. Ingelogd werkt het meteen. Voor een scherm dat niet ingelogd hoeft te zijn maak je een **geheime link**. Die toont alleen nummers, namen en wachttijden, geen adressen of telefoonnummers. Wie de link heeft kan meekijken: deel hem niet en trek hem in als hij uitlekt. Instelbaar is de wachttijd waarna een route oranje en rood wordt.

## E-mail
*Beheer → E-mail*: SMTP-server, poort, beveiliging, eventueel gebruiker en wachtwoord, afzender en webadres van de site. *Opslaan en testmail* controleert de instellingen. Zonder mail is er geen "wachtwoord vergeten"; de beheerder reset dan wachtwoorden.

## Back-up en herstel
*Beheer → Back-up*:
- Elke nacht vanaf 03:00 wordt automatisch een back-up gemaakt; je stelt in hoeveel er bewaard blijven.
- **Download** af en toe een back-up en bewaar die op een andere plek. Een back-up bevat wachtwoord-hashes en 2FA-sleutels, dus bewaar hem veilig.
- **Herstellen** vervangt alle gegevens door die uit het bestand. Doe dat alleen bewust.

## Logboek
*Beheer → Logboek* toont de laatste 200 acties (inloggen, wachtwoorden, toewijzingen, gateway-storingen en herstel, instellingen). Filter op type met de keuzelijst bovenaan. Handig om storingen en wijzigingen na te gaan.

## Dagelijks en tijdens de verkiezing
Vóór de verkiezingsdag: stembureaus gecontroleerd, accounts uitgedeeld, testsms gestuurd, gateway "verbonden", back-up gedownload.
Op de dag: houd het overzichtsscherm of **Beheer** in de gaten voor storingen; controleer de gateway-telefoon bij een storingsmelding (stroom, bereik, app actief).
Daarna: back-up downloaden, tijdelijke accounts opruimen.

## Problemen
| Probleem | Oplossing |
|---|---|
| Sms komt niet binnen | Controleer de webhook-URL en sleutel in de gateway; kijk bij *Gateway* of de sleutel klopt |
| Storing terwijl de gateway werkt | Storingstijd te laag; verhoog naar 300–600 s. Zet batterij-optimalisatie uit |
| Gebruiker kan niet inloggen | Wachtwoord resetten via Gebruikers; bij 2FA-probleem 2FA resetten |
| Bericht zonder stembureau | Nummer staat niet in de lijst; het bericht komt als niet herkend binnen. Wijs handmatig toe of voeg het stembureau toe |
| Database kwijt na herstart | Volume stond niet op `/data` (zie de installatiehandleiding) |
