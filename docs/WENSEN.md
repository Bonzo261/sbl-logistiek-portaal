# Wensen en haalbaarheid

Hier staan wensen met een inschatting van de haalbaarheid. De korte lijst staat in de [README](../README.md#roadmap).

## Spullen registreren bij het ophalen
**Wens:** de chauffeur geeft bij het ophalen op de locatie aan wat hij meeneemt: aantal tassen, kratten en stembussen.

**Haalbaarheid: goed.** Past binnen de bestaande opzet (Flask + SQLite), vraagt geen nieuwe techniek en raakt het bestaande proces weinig.

**Ontwerpidee**
- Bij **Klaar** op de routepagina verschijnt een klein formulier met per soort een teller (− / +), met als startwaarde de vooraf ingestelde aantallen. Eén tik op *Opslaan en klaar* rondt de opdracht af.
- In *Beheer* stel je de soorten in (standaard: tassen, kratten, stembussen) en of invullen verplicht is.
- De aantallen worden per bericht bewaard (nieuwe tabel of kolommen) en zijn door de coördinator achteraf te corrigeren.
- Het portaal en het rapport tonen totalen per soort, per route en per stembureau, bijvoorbeeld "stembussen: 41 van 42 stembureaus ontvangen".
- Optioneel: een verwacht aantal per stembureau, met een waarschuwing bij afwijking.

**Inschatting:** klein tot middelgroot (ongeveer een dag werk, inclusief tests, handleiding en rapport).

**Aandachtspunten**
- *Snelheid in het veld:* weinig invoer, grote knoppen, sensible standaardwaarden, anders slaat een chauffeur het over. Daarom bij voorkeur niet verplicht, of verplicht met één tik op "klopt zo".
- *Verschil tussen ophalen en afronden:* nu is er één stap (Klaar). Als het ophalen en het afleveren aparte momenten zijn, is een extra status nodig. Dat is meer werk.
- *Controle:* aantallen zijn door de chauffeur ingevoerd en dus geen bewijs. Wil je sluitende controle (zegelnummers, handtekening), dan is dat een aparte uitbreiding.
- *Privacy:* geen persoonsgegevens, alleen aantallen.

**Open vragen:** welke soorten precies, verplicht of niet, is er een verwacht aantal per stembureau, en gaat het om één moment (afronden) of om aparte ophaal- en afleverstappen?

## Stembescheiden: meerdere verkiezingen, centrale controle en overdrachtsdocument
Drie wensen die samen één onderdeel vormen, samen met "Spullen registreren" hierboven. Ze worden daarom het best samen ontworpen en daarna in stappen gebouwd.

### 1. Meerdere verkiezingen op één dag
**Wens:** op sommige dagen zijn er meerdere verkiezingen; de stembescheiden worden dan per verkiezing ingevuld.

**Haalbaarheid: goed, maar het raakt de basis.** Er komt een begrip *verkiezing* bij (naam, datum, soorten stembescheiden). De registratie van spullen (tassen, kratten, stembussen, enveloppen) wordt per stembureau én per verkiezing bijgehouden. Dit moet er eerst zijn voordat de volgende twee onderdelen kunnen. Het bestaande vastleggen van rapportages gebruikt nu de naam *verkiezing*; die twee worden dan samengevoegd.

**Inschatting:** middelgroot (twee tot drie dagen), omdat het datamodel, het formulier voor de chauffeur en het rapport veranderen.

### 2. Controle op de centrale locatie
**Wens:** de chauffeurs brengen de spullen naar een centrale locatie; daar moet gecontroleerd worden dat alles wat is ingevuld ook daadwerkelijk wordt ontvangen.

**Haalbaarheid: goed**, nadat de registratie per verkiezing bestaat.

**Ontwerpidee**
- Een ontvangstpagina voor de centrale locatie (coördinator of een aparte rol): per stembureau en per verkiezing staat wat de chauffeur heeft opgegeven; de ontvanger bevestigt of voert het ontvangen aantal in.
- Afwijkingen (te weinig, te veel, niets ontvangen) worden direct zichtbaar, met een opmerkingveld. Een totaaloverzicht laat zien wat nog moet binnenkomen.
- Optioneel later: stickers met QR-code per stembureau of kist, zodat de controle met de telefoon kan door te scannen.

**Inschatting:** klein tot middelgroot (een tot twee dagen).

### 3. Invoer voor het overdrachtsdocument (Model N 5)
**Wens:** het overdrachtsdocument (Model N 5) moet per verkiezing worden opgesteld; het portaal levert de gegevens.

**Wat Model N 5 is:** het *overdrachtsdocument*. Het wordt ingevuld door de burgemeester of een aangewezen ambtenaar en legt de overdracht aan het gemeentelijk stembureau vast. Volgens de versie van 2022 bevat het:
- de datum en begintijd van de zitting van het gemeentelijk stembureau;
- het totaal aantal overgedragen transportboxen/stembussen en het totaal aantal overgedragen enveloppen (met daarin het proces-verbaal van het stembureau en de sleutel van de transportbox of stembus). Het zijn totalen, niet per stembureau;
- een ja/nee-vraag over bijzonderheden tijdens vervoer en opslag, met een toelichting als het ja is;
- datum, tijd, naam, functie en handtekening van de ondertekenaar.

**Haalbaarheid: goed**, maar het portaal kan het formulier niet vervangen. Het portaal kan per verkiezing de aantallen en de bijzonderheden leveren uit de controle op de centrale locatie, als printbare invulhulp of als Excel. Het officiële model, met handtekening, blijft het document dat de gemeente zelf invult en ondertekent.

**Let op:** de modellen worden herzien. Er is een regeling van 2026 die N 5 wijzigt, en concepten van de Kiesraad noemen een nieuw proces-verbaal van het gemeentelijk stembureau dat deels in de plaats komt van N 5. Controleer voor elke verkiezing welke versie van het model geldt en pas de invulhulp daarop aan.

**Inschatting:** klein (een dag), nadat onderdeel 2 bestaat.

### Uitgangspunt: een optionele module
De stembescheiden-onderdelen komen als **module die je in Beheer aan of uit zet** (standaard uit). Zolang de module uit staat, verandert er niets: geen extra stappen of velden voor de chauffeur, geen extra pagina's of menu-items, en de bestaande werkwijze en rapportage blijven precies zoals ze nu zijn. Zet je de module later uit, dan blijven de ingevoerde gegevens bewaard.

Zo kan een gemeente die alleen de logistiek van de routes wil, de app ongewijzigd blijven gebruiken, en kan een gemeente die ook de stembescheiden wil bijhouden de module aanzetten. De module wordt pas gebouwd als de vraag er daadwerkelijk komt; dit is vastgelegd om er bij het ontwerpen van de basis rekening mee te houden (bijvoorbeeld door de nieuwe tabellen los te houden van de bestaande).

### Open vragen
- Decentrale of centrale stemopneming (DSO of CSO)? Dat bepaalt wat er fysiek naar de centrale locatie gaat.
- Welke soorten stembescheiden per verkiezing precies (stembussen of transportboxen, enveloppen met proces-verbaal, overige)?
- Wie voert de controle op de centrale locatie uit, en met welk apparaat?
- Is scannen van een code gewenst, of is aanvinken genoeg?
- Welk formaat wil je bij het overdrachtsdocument: printbare pagina, Excel, of beide?

### Voorgestelde volgorde
1. Verkiezingen en spullen registreren (per verkiezing) bij het ophalen.
2. Controle op de centrale locatie met afwijkingen.
3. Invoer voor het overdrachtsdocument.
4. Rapportage uitbreiden met de uitkomsten van de controle.

## Android-app voor chauffeurs (meldingen en locatie)
**Wens:** een Android-app waarmee chauffeurs inloggen, zodat meldingen beter aankomen. Met toegang tot de locatie zou je chauffeurs ook kunnen volgen.

**Haalbaarheid: kan, maar het is zwaarder dan het lijkt, en voor de meldingen is geen app nodig.**

### Meldingen
- Een gewone website kan op Android al pushmeldingen sturen (Web Push), ook bij een vergrendeld scherm en een gesloten browser. Daarvoor is geen eigen app nodig. De site moet als app op het beginscherm worden gezet (progressive web app). Op iOS werkt Web Push alleen als de site op het beginscherm staat.
- Dat is veel goedkoper dan een eigen app: een service worker, een sleutelpaar voor de server en een knop "meldingen aanzetten". Dit staat al als wens (*Pushmeldingen bij een vergrendelde telefoon*). Geen Google-account of app-winkel nodig.
- Een eigen app verbetert dit niet vanzelf. Ook een app moet pushmeldingen via Google (Firebase) laten lopen, wat voor een zelf te hosten open-sourceproject een extra afhankelijkheid en een Firebase-project per gemeente betekent. Batterij-optimalisatie van de telefoon blijft een risico, ook bij een app.

### Locatie volgen
- **Techniek:** een website kan alleen de locatie bepalen zolang de pagina op het scherm open staat. Doorlopend volgen op de achtergrond kan alleen met een echte app (met een voorgrondservice en toestemming voor locatie op de achtergrond). Dat kost batterij en google toetst zulke apps streng bij publicatie in de Play Store.
- **Privacy (belangrijk):** locatiegegevens van personen zijn persoonsgegevens. Chauffeurs volgen heeft een wettelijke grondslag en een duidelijk doel nodig, een DPIA ligt voor de hand, bij medewerkers is vaak instemming van de ondernemingsraad nodig, en je moet de bewaartermijn beperken en chauffeurs vooraf informeren. Het is geen pure techniek-vraag.
- **Lichtere varianten:** alleen een locatiestempel op het moment van accepteren of klaar (eenmalig, met toestemming), of delen van de locatie zolang de chauffeur een route heeft en de pagina open staat. Dat geeft het overzicht dat de coördinator wil, zonder doorlopend volgen.

### Een eigen app bouwen
- Een aparte codebasis (bijvoorbeeld Kotlin), een Play Store-account met eenmalige kosten, privacyverklaring, goedkeuring en blijvend onderhoud bij elke Android-versie. Voor een open-sourceproject met veel gemeenten betekent dat ook beheer van de bouw en ondertekening.
- Een lichte tussenvorm is een app die alleen de website verpakt (Trusted Web Activity). Die staat in de Play Store en gebruikt Web Push, maar heeft dezelfde beperkingen voor locatie op de achtergrond als de website.

### Voorgestelde volgorde
1. **Web Push met installeerbare site (progressive web app).** Lost de meldingen waarschijnlijk op, voor Android en iOS, tegen lage kosten.
2. **Optioneel en uit by default:** locatiestempel bij accepteren en klaar, met uitleg en toestemming.
3. **Eigen app alleen** als blijkt dat Web Push onvoldoende betrouwbaar is of als doorlopend volgen echt nodig is, en pas na een privacybeoordeling.

### Open vragen
- Is het probleem dat meldingen nu niet aankomen, of dat ze te laat aankomen? Op welke toestellen?
- Wat moet de coördinator met de locatie kunnen: weten waar iemand is, de aankomsttijd schatten, of controleren of iemand bij het stembureau was?
- Zijn de chauffeurs vrijwilligers, uitzendkrachten of medewerkers, en is er een ondernemingsraad?
