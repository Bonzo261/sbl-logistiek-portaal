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
