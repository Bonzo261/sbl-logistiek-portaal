"""Import van stembureaus en routes uit CSV of Excel (.xlsx)."""
import csv
import io

ALIASSEN = {
    "nummer": ["nummer", "stembureau", "nr", "stembureaunummer", "stembureau nummer"],
    "naam": ["naam", "locatie", "stembureaunaam"],
    "adres": ["adres"],
    "straat": ["straat", "staat"],
    "huisnummer": ["huisnummer"],
    "toevoeging": ["toevoeging", "huisnummertoevoeging"],
    "postcode": ["postcode"],
    "plaats": ["plaats", "woonplaats"],
    "telefoon": ["telefoon", "telefoonnummer", "tel", "voorzitter"],
    "route": ["route", "routenummer"],
}


class ImportFout(ValueError):
    pass


def _cel(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def lees_rijen(bestandsnaam, data):
    """Geeft lijst van lijsten (eerste rij = kopregel)."""
    naam = (bestandsnaam or "").lower()
    if naam.endswith(".xlsx"):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        return [[_cel(c) for c in r] for r in wb.worksheets[0].iter_rows(values_only=True)]
    if naam.endswith((".csv", ".txt")):
        try:
            tekst = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            tekst = data.decode("latin-1")
        try:
            dialect = csv.Sniffer().sniff(tekst[:4096], delimiters=";,\t")
        except csv.Error:
            dialect = csv.excel
        return [[c.strip() for c in r] for r in csv.reader(io.StringIO(tekst), dialect)]
    raise ImportFout("Alleen .csv en .xlsx worden ondersteund.")


def verwerk(rijen):
    """Zet rijen om naar stembureaus. Geeft (stembureaus, fouten)."""
    rijen = [r for r in rijen if any(c for c in r)]
    if len(rijen) < 2:
        raise ImportFout("Het bestand bevat geen gegevens.")
    kop = [c.strip().lower() for c in rijen[0]]
    kol = {}
    for sleutel, namen in ALIASSEN.items():
        for i, k in enumerate(kop):
            if k in namen and sleutel not in kol:
                kol[sleutel] = i
    if "nummer" not in kol:
        raise ImportFout("Kolom 'nummer' (stembureaunummer) niet gevonden. Kolommen: " + ", ".join(rijen[0]))
    uit, fouten, gezien = [], [], set()
    for regel, r in enumerate(rijen[1:], start=2):
        def g(s):
            i = kol.get(s)
            return r[i].strip() if i is not None and i < len(r) else ""
        try:
            nr = int(float(g("nummer")))
        except ValueError:
            fouten.append(f"Regel {regel}: ongeldig stembureaunummer '{g('nummer')}'")
            continue
        if nr in gezien:
            fouten.append(f"Regel {regel}: stembureau {nr} komt dubbel voor")
            continue
        gezien.add(nr)
        adres = g("adres")
        if not adres:
            deel = " ".join(x for x in [g("straat"), g("huisnummer") + g("toevoeging")] if x.strip())
            adres = ", ".join(x for x in [deel.strip(), (g("postcode") + " " + g("plaats")).strip()] if x)
        route = None
        if g("route"):
            try:
                route = int(float(g("route")))
            except ValueError:
                fouten.append(f"Regel {regel}: ongeldige route '{g('route')}'")
        uit.append({"nummer": nr, "naam": g("naam"), "adres": adres,
                    "telefoon": g("telefoon"), "route": route})
    return uit, fouten
