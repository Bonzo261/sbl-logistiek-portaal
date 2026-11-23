# Privacy en beveiliging

Dit document beschrijft welke gegevens het portaal verwerkt en hoe het die beschermt. Het is geen juridisch advies. De gemeente (of organisatie) die het portaal draait is zelf de verwerkingsverantwoordelijke en beoordeelt zelf of een verwerkingsregister, een DPIA en een verwerkersovereenkomst met de hostingpartij nodig zijn.

## Welke gegevens
| Gegevens | Waar | Opmerking |
|---|---|---|
| Naam, adres en telefoonnummer van stembureaus en voorzitters | tabel `stembureau` | Komt uit je eigen import. Telefoonnummers van voorzitters kunnen persoonsgegevens zijn |
| Inhoud en tijdstip van binnengekomen sms'jes (max. 500 tekens) | tabel `bericht` | Hoort alleen het stembureaunummer te bevatten; een voorzitter kan meer schrijven |
| Accountnaam, rol, route, optioneel e-mailadres, wachtwoord-hash, 2FA-sleutel | tabel `gebruiker` | Wachtwoorden worden gehasht opgeslagen; herstelcodes als HMAC |
| Logboek: tijdstip, gebruiker, actie | tabel `audit` | Bevat geen telefoonnummers of sms-inhoud |
| Mislukte inlogpogingen en foute sleutels (IP-adres of naam, tijdstip) | tabel `login_poging` | Wordt na 15 minuten opgeruimd |
| Instellingen, o.a. de webhook-sleutel, de schermsleutel en eventueel het SMTP-wachtwoord | tabel `instelling` | Staan dus ook in back-ups |

De app gebruikt geen externe diensten, trackers of lettertype-servers. Verkeer naar buiten gaat alleen naar de meldings-URL (bijv. ntfy) en de SMTP-server die de beheerder zelf instelt. De melding bij een storing bevat geen persoonsgegevens.

## Toegang
- Drie rollen: beheerder, coördinator en chauffeur. Een chauffeur ziet alleen de opdrachten van zijn eigen route.
- Beheerders en coördinatoren moeten tweestapsverificatie gebruiken (standaard).
- Na 10 mislukte inlogpogingen in 15 minuten volgt een blokkade. Foute sleutels op de webhook en heartbeat worden per IP-adres begrensd (30 per 15 minuten).
- Sessies vervallen bij een wachtwoordwijziging, reset of 2FA-reset. Cookies zijn `HttpOnly`, `SameSite=Lax` en bij HTTPS `Secure`. Formulieren zijn beschermd tegen CSRF.
- Het overzichtsscherm via de geheime link toont alleen stembureaunummers, namen en wachttijden. Geen adressen, telefoonnummers of sms-teksten. Wie de link heeft kan meekijken: trek hem in als hij uitlekt.

## Technische maatregelen
- Beveiligingsheaders: `Content-Security-Policy` (alleen eigen bronnen), `X-Frame-Options: DENY`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` en bij HTTPS `Strict-Transport-Security`.
- Pagina's worden niet in de browsercache bewaard (`Cache-Control: no-store`), zodat gegevens niet via de terugknop of een gedeelde computer zichtbaar blijven.
- Gebruikersinvoer wordt in de pagina's ge-escaped.

## Aandachtspunten voor wie het draait
1. **HTTPS is verplicht.** Zet `SBL_HTTPS=1` en `SBL_PROXY=1` achter een proxy.
2. **De webhook-sleutel staat in de URL.** Die kan terechtkomen in toegangslogs van de proxy. De app accepteert de sleutel ook in de header `X-SBL-Sleutel`; gebruik die als je forwarder dat kan. Gebruik een gegenereerde sleutel, geen zelfgekozen testsleutel.
3. **Back-ups** bevatten wachtwoord-hashes, 2FA-sleutels en alle stembureau- en berichtgegevens. Bewaar ze versleuteld of op een afgeschermde plek en ruim oude kopieën op.
4. **Bewaartermijn.** Berichten, het logboek en accounts blijven bewaard tot je ze verwijdert. Wis na de verkiezing de berichten, tijdelijke chauffeursaccounts, stembureaugegevens en oude back-ups met *Beheer → Opruimen*. Back-ups die je naar je eigen computer hebt gedownload, ruim je zelf op.
5. **Het sms-nummer van de gateway** en de gateway-telefoon bevatten ook persoonsgegevens (berichten). Beveilig de telefoon met een schermvergrendeling en wis berichten na afloop.
6. **Meldings-URL**: een ntfy-topic is voor iedereen leesbaar die de naam weet. Kies een lange, willekeurige naam of host je eigen ntfy-server.
7. **Updates**: werk regelmatig bij naar de nieuwste image; zie `CHANGELOG.md`.
8. De beheerder kan een meldings-URL instellen waar de app naartoe verbindt. Geef de beheerdersrol daarom alleen aan vertrouwde personen.

## Een kwetsbaarheid melden
Zie [`SECURITY.md`](../SECURITY.md).
