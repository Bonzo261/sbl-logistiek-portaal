# Bijdragen

Bijdragen zijn welkom: foutmeldingen, ideeën en pull requests. De software is bewust klein gehouden (Flask + SQLite, geen build-stap) zodat gemeenten er zelf mee uit de voeten kunnen.

## Voor je begint
- Kijk bij de issues en in de roadmap in de [README](README.md) of er al iets over bestaat.
- Open voor een grotere wijziging eerst een issue, zodat we de aanpak kunnen bespreken.
- Beveiligingsproblemen meld je niet openbaar; zie [`SECURITY.md`](SECURITY.md).
- Zet geen echte persoonsgegevens (namen, telefoonnummers, adressen van voorzitters) in issues, tests of voorbeeldbestanden.

## Ontwikkelen
```
pip install -r requirements-dev.txt
python -m pytest
flask --app wsgi run        # lokaal draaien
```
De app staat in `sbl/app.py`, de templates in `sbl/templates/`, de statische bestanden in `sbl/static/`. Zie ook `docs/HUISSTIJL.md` voor kleuren, lettertype en logo.

## Een pull request
1. Maak een branch en houd de wijziging klein en gericht.
2. Voeg een test toe in `tests/test_app.py` en zorg dat `python -m pytest` slaagt.
3. Noteer de wijziging in `CHANGELOG.md` onder de bovenste versie of "Niet uitgebracht".
4. Werk de handleiding in `docs/` bij als het gedrag voor gebruikers verandert.
5. Houd je aan de bestaande stijl: Nederlandse teksten in de interface, geen externe diensten of trackers, geen nieuwe zware afhankelijkheden zonder goede reden.

## Licentie
Door bij te dragen ga je akkoord dat je bijdrage onder de [AGPL-3.0-of-later](LICENSE) wordt gepubliceerd.
