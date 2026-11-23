# Huisstijl SBL StemBureauLogistiek

## Logo
- `sbl/static/logo.svg` – logo voor lichte achtergronden
- `sbl/static/logo-licht.svg` – logo met witte tekst voor donkere achtergronden (de kop van de app)
- `sbl/static/icon.svg` / `favicon.svg` – pictogram (afgerond), `icon-vierkant.svg` voor app-iconen
- PNG- en ICO-varianten: `favicon.ico`, `favicon-32.png`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`

Het pictogram is een route die eindigt in een vinkje. In de naam *StemBureauLogistiek* hebben de S, B en L de accentkleur, zodat de afkorting zichtbaar blijft. De tekst in de logobestanden is omgezet naar vormen: er is geen lettertype nodig om ze correct te tonen. Houd rondom het logo minimaal de hoogte van het vinkje vrij en rek het niet uit.

## Kleuren
| Naam | Hex | Gebruik |
|---|---|---|
| Marine | `#0b2a5b` | kop, titels, standaardknoppen |
| Marine hover | `#15397a` | knop bij aanwijzen |
| Diep marine | `#071a3b` | achtergrond overzichtsscherm |
| Oranje | `#ff7a1a` | accent: lijn onder de kop, hoofdactie (*Advies*), focusrand |
| Route-blauw | `#7fb2ff` | route in het pictogram, randen op donker |
| Achtergrond | `#f3f6fb` | pagina |
| Succes | `#15803d` | *Klaar*, *Accepteren* |
| Gevaar | `#b91c1c` | verwijderen, storing |
| Waarschuwing | `#f59e0b` | wachttijd te lang |

Statuskleuren (groen, oranje, rood) blijven functioneel en worden niet voor decoratie gebruikt.

## Lettertype
**Fira Sans** (Regular 400, Medium 500, Bold 700), SIL Open Font License 1.1. De bestanden staan in `sbl/static/fonts/` (inclusief licentie) en worden door de app zelf aangeboden, zodat er geen externe verzoeken nodig zijn. Alle variabelen staan bovenaan `sbl/static/stijl.css`.
