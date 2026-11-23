import io
import re

import pytest

from sbl import create_app

CSV = "Nummer;Locatie;Adres;Telefoon;Route\n1;School A;Dorpsstraat 1;0612345678;1\n2;Hal B;Kerklaan 2;0687654321;2\n"


@pytest.fixture()
def client(tmp_path):
    app = create_app({"DATABASE": str(tmp_path / "t.db"), "TESTING": True, "TWEEFA_VERPLICHT": False})
    return app.test_client()


def token(c, url="/login"):
    return re.search(r'name="csrf" value="(\w+)"', c.get(url).get_data(as_text=True)).group(1)


def post(c, url, data=None, tokenurl="/login", **kw):
    d = dict(data or {})
    d["csrf"] = token(c, tokenurl)
    return c.post(url, data=d, **kw)


def maak_admin(c):
    assert c.get("/", follow_redirects=False).headers["Location"].endswith("/setup")
    post(c, "/setup", {"naam": "admin", "wachtwoord": "langwachtwoord1"}, "/setup")
    post(c, "/login", {"naam": "admin", "wachtwoord": "langwachtwoord1"})


def sleutel(c):
    return re.search(r"sleutel=([\w-]+)", c.get("/beheer").get_data(as_text=True)).group(1)


def test_volledige_flow(client):
    c = client
    maak_admin(c)
    post(c, "/beheer/routes", {"aantal": "3"}, "/beheer")
    r = post(c, "/beheer/import", {"bestand": (io.BytesIO(CSV.encode()), "x.csv")}, "/beheer/import",
             content_type="multipart/form-data")
    assert "2 stembureaus gevonden" in r.get_data(as_text=True)
    data = re.search(r'name="data" value="([^"]+)"', r.get_data(as_text=True)).group(1).replace("&#34;", '"')
    post(c, "/beheer/import", {"data": data}, "/beheer/import")
    assert "School A" in c.get("/beheer/stembureaus").get_data(as_text=True)

    k = sleutel(c)
    assert c.post("/api/sms", json={"message": "1"}).status_code == 403
    resp = c.post(f"/api/sms?sleutel={k}", json={"message": "stembureau 1"})
    assert resp.status_code == 201 and resp.get_json()["herkend"]
    assert "Advies: route 1" in c.get("/portaal").get_data(as_text=True)

    post(c, "/bericht/1/route", {"route_id": "1"}, "/portaal")
    assert "Bel voorzitter stembureau-1" in c.get("/route/1").get_data(as_text=True)
    post(c, "/bericht/1/klaar", tokenurl="/portaal")
    assert "Bel voorzitter" not in c.get("/route/1").get_data(as_text=True)


def test_chauffeur_ziet_alleen_eigen_route(client):
    c = client
    maak_admin(c)
    post(c, "/beheer/routes", {"aantal": "2"}, "/beheer")
    post(c, "/beheer/gebruikers/nieuw",
         {"naam": "chauf1", "wachtwoord": "langwachtwoord2", "rol": "chauffeur", "route_id": "1"}, "/beheer/gebruikers")
    post(c, "/logout", tokenurl="/beheer")
    post(c, "/login", {"naam": "chauf1", "wachtwoord": "langwachtwoord2"})
    assert c.get("/route/1").status_code == 200
    assert c.get("/route/2").status_code == 403
    assert c.get("/beheer").status_code == 403
    assert c.get("/portaal").status_code == 403


def test_csrf_vereist(client):
    assert client.post("/login", data={"naam": "a", "wachtwoord": "b"}).status_code == 400


def test_heartbeat(client):
    maak_admin(client)
    k = sleutel(client)
    assert client.get(f"/api/heartbeat?sleutel={k}").get_json()["ok"]


def test_import_formaten():
    import os
    from sbl import importer
    pad = os.path.join(os.path.dirname(__file__), "voorbeeld.ods")
    items, fouten = importer.verwerk(importer.lees_rijen("v.ods", open(pad, "rb").read()))
    assert not fouten
    assert items == [{"nummer": 5, "naam": "School A", "adres": "Dorpsstraat 1a, 1234 AB Dorp",
                      "telefoon": "0612345678", "route": 2}]
    csv_items, _ = importer.verwerk(importer.lees_rijen("v.csv", "Locatie,Staat,Huisnummer,Toevoeging,Postcode,Plaats,sbNummers,telefoonnummer,route\nSchool  A,Dorpsstraat,1,a,1234 AB,Dorp,5,0612345678,2\n".encode()))
    assert csv_items == items


def test_login_geblokkeerd_na_tien_pogingen(client):
    maak_admin(client)
    post(client, "/logout", tokenurl="/beheer")
    for _ in range(10):
        post(client, "/login", {"naam": "admin", "wachtwoord": "fout"})
    r = post(client, "/login", {"naam": "admin", "wachtwoord": "langwachtwoord1"})
    assert r.status_code == 429


def test_tweefa_verplicht_en_login(tmp_path):
    import time
    from sbl import totp
    c = create_app({"DATABASE": str(tmp_path / "2.db"), "TESTING": True}).test_client()
    post(c, "/setup", {"naam": "admin", "wachtwoord": "langwachtwoord1"}, "/setup")
    post(c, "/login", {"naam": "admin", "wachtwoord": "langwachtwoord1"})
    assert c.get("/portaal").headers["Location"].endswith("/account")  # verplicht instellen
    post(c, "/account/2fa/start", tokenurl="/account")
    geheim = re.search(r"<code[^>]*>(\w+)</code>", c.get("/account").get_data(as_text=True)).group(1)
    teller = int(time.time() // 30)
    assert "onjuist" in post(c, "/account/2fa/bevestig", {"code": "000000"}, "/account", follow_redirects=True).get_data(as_text=True)
    post(c, "/account/2fa/bevestig", {"code": totp.code(geheim, teller)}, "/account")
    assert c.get("/portaal").status_code == 200
    post(c, "/logout", tokenurl="/portaal")
    r = post(c, "/login", {"naam": "admin", "wachtwoord": "langwachtwoord1"})
    assert r.headers["Location"].endswith("/login/2fa")
    assert c.get("/portaal", follow_redirects=False).status_code == 302  # nog niet ingelogd
    # dezelfde code mag niet nogmaals (replay) ...
    post(c, "/login/2fa", {"code": totp.code(geheim, teller)}, "/login/2fa")
    assert c.get("/portaal").status_code == 302
    # ... een nieuwe wel
    post(c, "/login/2fa", {"code": totp.code(geheim, teller + 1)}, "/login/2fa")
    assert c.get("/portaal").status_code == 200


def test_totp_rfc6238_vector():
    from sbl import totp
    import base64
    geheim = base64.b32encode(b"12345678901234567890").decode()
    assert totp.code(geheim, 59 // 30) == "287082"


def test_storing_bewaking_meldt_een_keer(tmp_path, monkeypatch):
    import sqlite3
    app = create_app({"DATABASE": str(tmp_path / "s.db"), "TESTING": True, "TWEEFA_VERPLICHT": False})
    verzonden = []
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: verzonden.append(req.full_url) or io.BytesIO(b""))
    with sqlite3.connect(str(tmp_path / "s.db")) as c:
        c.execute("INSERT INTO instelling VALUES ('notificatie_url','https://ntfy.example/topic')")
        c.execute("INSERT INTO instelling VALUES ('laatste_ping','2020-01-01 00:00:00')")
    app.bewaak_gateway(); app.bewaak_gateway()
    assert len(verzonden) == 1  # storing maar één keer gemeld
    with sqlite3.connect(str(tmp_path / "s.db")) as c:
        c.execute("UPDATE instelling SET value='2999-01-01 00:00:00' WHERE key='laatste_ping'")
    app.bewaak_gateway()
    assert len(verzonden) == 2  # herstel gemeld


def test_qr_code():
    pytest.importorskip("segno")
    from sbl import totp
    assert totp.qr_svg("otpauth://totp/x?secret=ABC").startswith("data:image/svg+xml")


def test_wachtwoord_wijzigen_en_reset(client):
    c = client
    maak_admin(c)
    assert "klopt niet" in post(c, "/account/wachtwoord", {"huidig": "fout", "nieuw": "nieuwwachtwoord1", "nieuw2": "nieuwwachtwoord1"},
                                "/account", follow_redirects=True).get_data(as_text=True)
    post(c, "/account/wachtwoord", {"huidig": "langwachtwoord1", "nieuw": "nieuwwachtwoord1", "nieuw2": "nieuwwachtwoord1"}, "/account")
    post(c, "/logout", tokenurl="/account")
    post(c, "/login", {"naam": "admin", "wachtwoord": "nieuwwachtwoord1"})
    assert c.get("/beheer").status_code == 200
    # beheerder reset wachtwoord van een andere gebruiker
    post(c, "/beheer/gebruikers/nieuw", {"naam": "co", "wachtwoord": "coordinator123", "rol": "coordinator"}, "/beheer/gebruikers")
    uid = re.findall(r"/beheer/gebruikers/(\d+)/wachtwoord", c.get("/beheer/gebruikers").get_data(as_text=True))[-1]
    post(c, f"/beheer/gebruikers/{uid}/wachtwoord", {"nieuw": "weergewijzigd99"}, "/beheer/gebruikers")
    post(c, "/logout", tokenurl="/beheer")
    r = post(c, "/login", {"naam": "co", "wachtwoord": "weergewijzigd99"})
    assert r.status_code == 302


def test_backup_en_herstel(client):
    c = client
    maak_admin(c)
    post(c, "/beheer/routes", {"aantal": "2"}, "/beheer")
    post(c, "/beheer/stembureaus/opslaan", {"nummer": "7", "naam": "Test", "adres": "x", "telefoon": "0611111111", "route_id": ""}, "/beheer/stembureaus")
    bk = post(c, "/beheer/backup/download", tokenurl="/beheer/backup")
    assert bk.status_code == 200 and bk.data[:15] == b"SQLite format 3"
    post(c, "/beheer/stembureaus/1/verwijder", tokenurl="/beheer/stembureaus")
    assert "Test" not in c.get("/beheer/stembureaus").get_data(as_text=True)
    # ongeldig bestand wordt geweigerd
    r = post(c, "/beheer/backup/herstel", {"bestand": (io.BytesIO(b"geen database"), "x.db"), "bevestig": "HERSTEL"},
             "/beheer/backup", content_type="multipart/form-data", follow_redirects=True)
    assert "geen geldig" in r.get_data(as_text=True)
    # zonder bevestiging gebeurt er niets
    r = post(c, "/beheer/backup/herstel", {"bestand": (io.BytesIO(bk.data), "x.db"), "bevestig": "nee"},
             "/beheer/backup", content_type="multipart/form-data", follow_redirects=True)
    assert "typ HERSTEL" in r.get_data(as_text=True)
    post(c, "/beheer/backup/herstel", {"bestand": (io.BytesIO(bk.data), "x.db"), "bevestig": "herstel"},
         "/beheer/backup", content_type="multipart/form-data")
    post(c, "/login", {"naam": "admin", "wachtwoord": "langwachtwoord1"})
    assert "Test" in c.get("/beheer/stembureaus").get_data(as_text=True)


def test_herstelcode_werkt_een_keer(tmp_path):
    import time
    from sbl import totp
    c = create_app({"DATABASE": str(tmp_path / "h.db"), "TESTING": True}).test_client()
    post(c, "/setup", {"naam": "admin", "wachtwoord": "langwachtwoord1"}, "/setup")
    post(c, "/login", {"naam": "admin", "wachtwoord": "langwachtwoord1"})
    post(c, "/account/2fa/start", tokenurl="/account")
    geheim = re.search(r"<code[^>]*>(\w+)</code>", c.get("/account").get_data(as_text=True)).group(1)
    r = post(c, "/account/2fa/bevestig", {"code": totp.code(geheim, int(time.time() // 30))}, "/account")
    codes = re.findall(r"[A-Z0-9]{5}-[A-Z0-9]{5}", r.get_data(as_text=True))
    assert len(codes) == 8
    post(c, "/logout", tokenurl="/portaal")
    post(c, "/login", {"naam": "admin", "wachtwoord": "langwachtwoord1"})
    post(c, "/login/2fa", {"code": codes[0].lower()}, "/login/2fa")
    assert c.get("/portaal").status_code == 200
    post(c, "/logout", tokenurl="/portaal")
    post(c, "/login", {"naam": "admin", "wachtwoord": "langwachtwoord1"})
    post(c, "/login/2fa", {"code": codes[0]}, "/login/2fa")  # hergebruik
    assert c.get("/portaal").status_code == 302


def test_bulk_accounts_en_verplichte_wijziging(client):
    c = client
    maak_admin(c)
    post(c, "/beheer/routes", {"aantal": "3"}, "/beheer")
    r = post(c, "/beheer/gebruikers/bulk", {"voorvoegsel": "route", "route_id": ["1", "2", "3"]}, "/beheer/gebruikers/bulk")
    html = r.get_data(as_text=True)
    assert "3 accounts aangemaakt" in html
    rijen = re.findall(r"<td>(route\d)</td><td><code>(\w{12})</code>", html)
    assert [n for n, _ in rijen] == ["route1", "route2", "route3"]
    assert len({w for _, w in rijen}) == 3  # uniek per account
    # opnieuw: bestaande worden overgeslagen
    r2 = post(c, "/beheer/gebruikers/bulk", {"voorvoegsel": "route", "route_id": ["1"]}, "/beheer/gebruikers/bulk")
    assert "0 accounts aangemaakt" in r2.get_data(as_text=True)
    post(c, "/logout", tokenurl="/beheer")
    naam, tijdelijk = rijen[1]
    post(c, "/login", {"naam": naam, "wachtwoord": tijdelijk})
    # alles wordt omgeleid naar wachtwoord kiezen
    assert c.get("/route/2").headers["Location"].endswith("/account/nieuw-wachtwoord")
    assert c.get("/account/nieuw-wachtwoord").status_code == 200
    # zelfde wachtwoord wordt geweigerd
    post(c, "/account/wachtwoord", {"huidig": tijdelijk, "nieuw": tijdelijk, "nieuw2": tijdelijk}, "/account/nieuw-wachtwoord")
    assert c.get("/route/2").status_code == 302
    post(c, "/account/wachtwoord", {"huidig": tijdelijk, "nieuw": "eigenwachtwoord12", "nieuw2": "eigenwachtwoord12"}, "/account/nieuw-wachtwoord")
    assert c.get("/route/2").status_code == 200
    assert c.get("/route/1").status_code == 403
    post(c, "/logout", tokenurl="/route/2")
    assert post(c, "/login", {"naam": naam, "wachtwoord": tijdelijk}).get_data(as_text=True).count("Onjuiste") == 1


def test_selectie_acties(client):
    c = client
    maak_admin(c)
    post(c, "/beheer/routes", {"aantal": "3"}, "/beheer")
    post(c, "/beheer/gebruikers/bulk", {"voorvoegsel": "route", "route_id": ["1", "2", "3"]}, "/beheer/gebruikers/bulk")
    html = c.get("/beheer/gebruikers").get_data(as_text=True)
    ids = re.findall(r'class="sel" name="uid" value="(\d+)"', html)
    assert len(ids) == 3 and html.count('name="uid"') == 3  # admin zelf niet selecteerbaar
    # nieuwe wachtwoorden voor selectie
    r = post(c, "/beheer/gebruikers/selectie", {"actie": "wachtwoord", "uid": ids[:2]}, "/beheer/gebruikers")
    assert "2 nieuwe tijdelijke wachtwoorden" in r.get_data(as_text=True)
    assert len(re.findall(r"<code>\w{12}</code>", r.get_data(as_text=True))) == 2
    # route wijzigen
    post(c, "/beheer/gebruikers/selectie", {"actie": "route", "uid": [ids[0]], "route_id": "3"}, "/beheer/gebruikers")
    assert "Route wijzigen" in c.get("/beheer/gebruikers").get_data(as_text=True)
    # zonder selectie: melding
    r = post(c, "/beheer/gebruikers/selectie", {"actie": "verwijder"}, "/beheer/gebruikers", follow_redirects=True)
    assert "Selecteer eerst" in r.get_data(as_text=True)
    # onbekende actie
    assert post(c, "/beheer/gebruikers/selectie", {"actie": "boem", "uid": ids}, "/beheer/gebruikers").status_code == 400
    # verwijderen
    post(c, "/beheer/gebruikers/selectie", {"actie": "verwijder", "uid": ids}, "/beheer/gebruikers")
    assert 'name="uid"' not in c.get("/beheer/gebruikers").get_data(as_text=True)


def test_laatste_beheerder_niet_verwijderen(client):
    c = client
    maak_admin(c)
    post(c, "/beheer/gebruikers/nieuw", {"naam": "b2", "wachtwoord": "langwachtwoord2", "rol": "beheerder"}, "/beheer/gebruikers")
    ids = re.findall(r'class="sel" name="uid" value="(\d+)"', c.get("/beheer/gebruikers").get_data(as_text=True))
    # admin (ikzelf) blijft altijd over; b2 mag dus weg
    post(c, "/beheer/gebruikers/selectie", {"actie": "verwijder", "uid": ids}, "/beheer/gebruikers")
    assert 'name="uid"' not in c.get("/beheer/gebruikers").get_data(as_text=True)


def test_wachtwoorden_excel(client):
    import html as _html
    from openpyxl import load_workbook
    c = client
    maak_admin(c)
    post(c, "/beheer/routes", {"aantal": "2"}, "/beheer")
    r = post(c, "/beheer/gebruikers/bulk", {"voorvoegsel": "route", "route_id": ["1", "2"]}, "/beheer/gebruikers/bulk")
    pagina = r.get_data(as_text=True)
    data = _html.unescape(re.search(r'name="data" value="([^"]*)"', pagina).group(1))
    x = post(c, "/beheer/gebruikers/wachtwoorden.xlsx", {"data": data}, "/beheer/gebruikers/bulk")
    assert x.status_code == 200 and x.headers["Cache-Control"] == "no-store"
    ws = load_workbook(io.BytesIO(x.data)).active
    rijen = list(ws.iter_rows(values_only=True))
    assert rijen[0][:3] == ("Route", "Gebruikersnaam", "Tijdelijk wachtwoord")
    assert [r[1] for r in rijen[1:]] == ["route1", "route2"]
    for r_, (naam, ww) in zip(rijen[1:], re.findall(r"<td>(route\d)</td><td><code>(\w{12})</code>", pagina)):
        assert r_[2] == ww and r_[3].endswith("/login")
    assert post(c, "/beheer/gebruikers/wachtwoorden.xlsx", {"data": "kapot"}, "/beheer/gebruikers/bulk").status_code == 400


def test_email_instellen(client):
    c = client
    c.get("/setup")
    post(c, "/setup", {"naam": "admin", "wachtwoord": "langwachtwoord1", "email": "Beheer@Voorbeeld.NL"}, "/setup")
    post(c, "/login", {"naam": "admin", "wachtwoord": "langwachtwoord1"})
    assert 'value="beheer@voorbeeld.nl"' in c.get("/account").get_data(as_text=True)  # kleine letters
    r = post(c, "/account/email", {"email": "geen-adres"}, "/account", follow_redirects=True)
    assert "geen geldig" in r.get_data(as_text=True)
    post(c, "/beheer/gebruikers/nieuw", {"naam": "co", "wachtwoord": "coordinator123", "rol": "coordinator",
                                          "email": "co@voorbeeld.nl"}, "/beheer/gebruikers")
    assert "co@voorbeeld.nl" in c.get("/beheer/gebruikers").get_data(as_text=True)
    # hetzelfde adres bij een andere gebruiker wordt geweigerd
    r = post(c, "/account/email", {"email": "co@voorbeeld.nl"}, "/account", follow_redirects=True)
    assert "al in gebruik" in r.get_data(as_text=True)
    # leegmaken kan
    post(c, "/account/email", {"email": ""}, "/account")
    assert 'value="beheer@' not in c.get("/account").get_data(as_text=True)


class NepSMTP:
    verzonden = []
    fout = None

    def __init__(self, host, poort, timeout=0, context=None):
        self.host, self.poort = host, poort

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self): pass
    def starttls(self, context=None): pass

    def login(self, g, w):
        if NepSMTP.fout:
            import smtplib
            raise smtplib.SMTPAuthenticationError(535, b"nee")

    def send_message(self, m):
        NepSMTP.verzonden.append(m)


def mail_setup(c, monkeypatch):
    import smtplib
    NepSMTP.verzonden, NepSMTP.fout = [], None
    monkeypatch.setattr(smtplib, "SMTP", NepSMTP)
    c.get("/setup")
    post(c, "/setup", {"naam": "admin", "wachtwoord": "langwachtwoord1", "email": "admin@voorbeeld.nl"}, "/setup")
    post(c, "/login", {"naam": "admin", "wachtwoord": "langwachtwoord1"})


MAILFORM = {"host": "mail.test", "poort": "587", "beveiliging": "starttls", "gebruiker": "u", "wachtwoord": "w",
            "van": "noreply@voorbeeld.nl", "publieke_url": "https://portaal.voorbeeld.nl"}


def test_wachtwoord_vergeten_flow(client, monkeypatch):
    c = client
    mail_setup(c, monkeypatch)
    post(c, "/logout", tokenurl="/beheer")
    assert c.get("/wachtwoord-vergeten").status_code == 404  # nog geen mail ingesteld
    assert "vergeten" not in c.get("/login").get_data(as_text=True)
    post(c, "/login", {"naam": "admin", "wachtwoord": "langwachtwoord1"})
    post(c, "/beheer/mail", MAILFORM, "/beheer")
    post(c, "/logout", tokenurl="/beheer")
    assert "Wachtwoord vergeten?" in c.get("/login").get_data(as_text=True)
    # onbekend adres: zelfde antwoord, geen mail
    r = post(c, "/wachtwoord-vergeten", {"email": "niemand@voorbeeld.nl"}, "/wachtwoord-vergeten")
    assert "Als dit e-mailadres" in r.get_data(as_text=True) and not NepSMTP.verzonden
    r = post(c, "/wachtwoord-vergeten", {"email": "ADMIN@voorbeeld.nl"}, "/wachtwoord-vergeten")
    assert "Als dit e-mailadres" in r.get_data(as_text=True) and len(NepSMTP.verzonden) == 1
    tekst = NepSMTP.verzonden[0].get_content()
    link = re.search(r"https://portaal\.voorbeeld\.nl(/wachtwoord-herstel/[\w-]+)", tekst).group(1)  # vaste, geconfigureerde host
    assert c.get(link).status_code == 200
    assert "Minimaal" in post(c, link, {"nieuw": "kort", "nieuw2": "kort"}, link, follow_redirects=True).get_data(as_text=True)
    post(c, link, {"nieuw": "herstelwachtwoord1", "nieuw2": "herstelwachtwoord1"}, link)
    assert c.get(link).status_code == 410  # token is één keer bruikbaar
    post(c, "/login", {"naam": "admin", "wachtwoord": "herstelwachtwoord1"})
    assert c.get("/beheer").status_code == 200


def test_herstel_token_verloopt_en_ratelimit(client, monkeypatch):
    import sqlite3
    c = client
    mail_setup(c, monkeypatch)
    post(c, "/beheer/mail", MAILFORM, "/beheer")
    post(c, "/logout", tokenurl="/beheer")
    post(c, "/wachtwoord-vergeten", {"email": "admin@voorbeeld.nl"}, "/wachtwoord-vergeten")
    link = re.search(r"(/wachtwoord-herstel/[\w-]+)", NepSMTP.verzonden[0].get_content()).group(1)
    with sqlite3.connect(c.application.config["DATABASE"]) as d:
        d.execute("UPDATE herstel_token SET verloopt=1")
    assert c.get(link).status_code == 410
    for _ in range(6):
        r = post(c, "/wachtwoord-vergeten", {"email": "admin@voorbeeld.nl"}, "/wachtwoord-vergeten")
    assert r.status_code == 429


def test_testmail_en_fouten(client, monkeypatch):
    c = client
    mail_setup(c, monkeypatch)
    r = post(c, "/beheer/mail", dict(MAILFORM, testmail="1"), "/beheer", follow_redirects=True)
    assert "Testmail verstuurd naar admin@voorbeeld.nl" in r.get_data(as_text=True)
    NepSMTP.fout = True
    r = post(c, "/beheer/mail", dict(MAILFORM, testmail="1"), "/beheer", follow_redirects=True)
    assert "controleer gebruiker en wachtwoord" in r.get_data(as_text=True)
    r = post(c, "/beheer/mail", dict(MAILFORM, poort="99999"), "/beheer", follow_redirects=True)
    assert "Controleer de mailinstellingen" in r.get_data(as_text=True)
    # wachtwoord blijft behouden als het veld leeg is
    post(c, "/beheer/mail", dict(MAILFORM, wachtwoord=""), "/beheer")
    assert "ingesteld – leeg laten" in c.get("/beheer").get_data(as_text=True)


def test_automatische_backup_bewaren_en_herstellen(client):
    import os
    import sqlite3
    c = client
    maak_admin(c)
    app = c.application
    post(c, "/beheer/routes", {"aantal": "2"}, "/beheer")
    post(c, "/beheer/stembureaus/opslaan", {"nummer": "7", "naam": "Eerste", "adres": "x", "telefoon": "061", "route_id": ""}, "/beheer/stembureaus")
    naam = app.auto_backup(forceer=True)
    assert naam and re.fullmatch(r"sbl-auto-\d{8}-\d{6}\.db", naam)
    assert app.auto_backup() is None  # niet nogmaals op dezelfde dag
    mapje = os.path.join(os.path.dirname(app.config["DATABASE"]), "backups")
    assert oct(os.stat(os.path.join(mapje, naam)).st_mode)[-3:] == "600"
    with sqlite3.connect(os.path.join(mapje, naam)) as d:
        assert d.execute("SELECT naam FROM stembureau").fetchone()[0] == "Eerste"
    assert naam in c.get("/beheer/backup").get_data(as_text=True)
    # retentie: oude bestanden worden opgeruimd
    post(c, "/beheer/backup/instellingen", {"auto": "1", "bewaar": "2"}, "/beheer/backup")
    for oud in ("20200101-000000", "20200102-000000", "20200103-000000"):
        open(os.path.join(mapje, f"sbl-auto-{oud}.db"), "wb").close()
    app.auto_backup(forceer=True)
    over = sorted(os.listdir(mapje))
    assert len(over) == 2 and "sbl-auto-20200101-000000.db" not in over
    # wijzig gegevens en herstel vanaf de opgeslagen back-up
    post(c, "/beheer/stembureaus/opslaan", {"nummer": "8", "naam": "Tweede", "adres": "y", "telefoon": "062", "route_id": ""}, "/beheer/stembureaus")
    nieuwste = [n for n in over if not n.startswith("sbl-auto-2020")][-1]
    # alleen een back-up waar 'Tweede' nog niet in zit: de eerste
    post(c, "/beheer/backup/herstel", {"opgeslagen": naam, "bevestig": "HERSTEL"}, "/beheer/backup")
    assert c.get("/beheer").status_code == 302  # alle sessies vervallen
    post(c, "/login", {"naam": "admin", "wachtwoord": "langwachtwoord1"})
    pagina = c.get("/beheer/stembureaus").get_data(as_text=True)
    assert "Eerste" in pagina and "Tweede" not in pagina


def test_backupbestand_download_beveiligd(client):
    c = client
    maak_admin(c)
    naam = c.application.auto_backup(forceer=True)
    assert post(c, f"/beheer/backup/bestand/{naam}", tokenurl="/beheer/backup").data[:15] == b"SQLite format 3"
    assert post(c, "/beheer/backup/bestand/..%2Fsbl.db", tokenurl="/beheer/backup").status_code == 404
    assert post(c, "/beheer/backup/bestand/passwd", tokenurl="/beheer/backup").status_code == 404


def test_sessies_vervallen_bij_wachtwoordwijziging(client):
    c1 = client
    maak_admin(c1)
    c2 = c1.application.test_client()
    post(c2, "/login", {"naam": "admin", "wachtwoord": "langwachtwoord1"})
    assert c2.get("/beheer").status_code == 200
    # wachtwoord wijzigen op apparaat 1: apparaat 1 blijft ingelogd, apparaat 2 niet
    post(c1, "/account/wachtwoord", {"huidig": "langwachtwoord1", "nieuw": "nieuwwachtwoord99", "nieuw2": "nieuwwachtwoord99"}, "/account")
    assert c1.get("/beheer").status_code == 200
    assert c2.get("/beheer").status_code == 302
    # 'uitloggen op andere apparaten'
    c3 = c1.application.test_client()
    post(c3, "/login", {"naam": "admin", "wachtwoord": "nieuwwachtwoord99"})
    assert c3.get("/beheer").status_code == 200
    post(c1, "/account/uitloggen-elders", tokenurl="/account")
    assert c1.get("/beheer").status_code == 200 and c3.get("/beheer").status_code == 302


def test_sessie_vervalt_bij_reset_door_beheerder(client):
    adm = client
    maak_admin(adm)
    post(adm, "/beheer/gebruikers/nieuw", {"naam": "co", "wachtwoord": "coordinator123", "rol": "coordinator"}, "/beheer/gebruikers")
    co = adm.application.test_client()
    post(co, "/login", {"naam": "co", "wachtwoord": "coordinator123"})
    assert co.get("/portaal").status_code == 200
    uid = re.findall(r"/beheer/gebruikers/(\d+)/wachtwoord", adm.get("/beheer/gebruikers").get_data(as_text=True))[-1]
    post(adm, f"/beheer/gebruikers/{uid}/wachtwoord", {"nieuw": "nieuwwachtwoord77"}, "/beheer/gebruikers")
    assert co.get("/portaal").status_code == 302  # opnieuw inloggen nodig


def test_overzichtsscherm(client):
    c = client
    maak_admin(c)
    post(c, "/beheer/routes", {"aantal": "2"}, "/beheer")
    post(c, "/beheer/stembureaus/opslaan", {"nummer": "5", "naam": "School A", "adres": "Geheimstraat 1", "telefoon": "0611111111", "route_id": "1"}, "/beheer/stembureaus")
    k = sleutel(c)
    c.post(f"/api/sms?sleutel={k}", json={"message": "5"})
    d = c.get("/scherm/data.json").get_json()
    assert [n["nr"] for n in d["nieuw"]] == [5] and len(d["routes"]) == 2 and d["klaar_vandaag"] == 0
    post(c, "/bericht/1/route", {"route_id": "1"}, "/portaal")
    d = c.get("/scherm/data.json").get_json()
    assert d["nieuw"] == [] and d["routes"][0]["open"][0]["nr"] == 5 and d["routes"][0]["niveau"] == "groen"
    # zonder login en zonder sleutel: geen toegang
    anon = c.application.test_client()
    assert anon.get("/scherm/data.json").status_code == 403
    assert anon.get("/scherm").status_code == 302
    # met geheime sleutel: toegang, maar zonder adres en telefoon
    post(c, "/beheer/scherm", {"actie": "nieuw", "drempel": "10"}, "/beheer")
    sl = re.search(r"scherm\?sleutel=([\w-]+)", c.get("/beheer").get_data(as_text=True)).group(1)
    r = anon.get(f"/scherm/data.json?sleutel={sl}")
    assert r.status_code == 200 and "Geheimstraat" not in r.get_data(as_text=True) and "0611111111" not in r.get_data(as_text=True)
    assert anon.get("/scherm/data.json?sleutel=fout").status_code == 403
    assert anon.get(f"/scherm?sleutel={sl}").status_code == 200
    post(c, "/beheer/scherm", {"actie": "uit"}, "/beheer")
    assert anon.get(f"/scherm/data.json?sleutel={sl}").status_code == 403
    # chauffeurs hebben geen toegang
    post(c, "/beheer/gebruikers/nieuw", {"naam": "ch", "wachtwoord": "chauffeur1234", "rol": "chauffeur", "route_id": "1"}, "/beheer/gebruikers")
    ch = c.application.test_client()
    post(ch, "/login", {"naam": "ch", "wachtwoord": "chauffeur1234"})
    assert ch.get("/scherm/data.json").status_code == 403


def test_acceptatie_door_chauffeur_en_verplaatsen(client):
    c = client
    maak_admin(c)
    post(c, "/beheer/routes", {"aantal": "2"}, "/beheer")
    post(c, "/beheer/stembureaus/opslaan", {"nummer": "5", "naam": "School A", "adres": "Dorpsstraat 1", "telefoon": "0611111111", "route_id": "1"}, "/beheer/stembureaus")
    post(c, "/beheer/gebruikers/bulk", {"voorvoegsel": "r", "route_id": ["1", "2"]}, "/beheer/gebruikers/bulk")
    # zet tijdelijke wachtwoorden om naar bruikbare accounts via admin-reset
    ids = re.findall(r'class="sel" name="uid" value="(\d+)"', c.get("/beheer/gebruikers").get_data(as_text=True))
    for i, uid in enumerate(ids):
        post(c, f"/beheer/gebruikers/{uid}/wachtwoord", {"nieuw": f"chauffeur-wachtwoord{i}"}, "/beheer/gebruikers")

    def chauffeur(naam, ww):
        k = c.application.test_client()
        post(k, "/login", {"naam": naam, "wachtwoord": ww})
        post(k, "/account/wachtwoord", {"huidig": ww, "nieuw": ww + "x", "nieuw2": ww + "x"}, "/account/nieuw-wachtwoord")
        return k
    ch1, ch2 = chauffeur("r1", "chauffeur-wachtwoord0"), chauffeur("r2", "chauffeur-wachtwoord1")

    # uit (standaard): direct onderweg, geen acceptatie nodig
    k = sleutel(c)
    c.post(f"/api/sms?sleutel={k}", json={"message": "5"})
    post(c, "/bericht/1/route", {"route_id": "1"}, "/portaal")
    assert "Bel voorzitter" in ch1.get("/route/1").get_data(as_text=True)
    post(c, "/bericht/1/klaar", tokenurl="/portaal")

    # aan: eerst toegewezen
    post(c, "/beheer/werkwijze", {"accepteren_verplicht": "1"}, "/beheer")
    c.post(f"/api/sms?sleutel={k}", json={"message": "5"})
    post(c, "/bericht/2/route", {"route_id": "1"}, "/portaal")
    pagina = ch1.get("/route/1").get_data(as_text=True)
    assert "Accepteren" in pagina and "Bel voorzitter" not in pagina
    assert "Wacht op acceptatie (1)" in c.get("/portaal").get_data(as_text=True)
    # klaarmelden zonder acceptatie kan niet
    post(ch1, "/bericht/2/klaar", tokenurl="/route/1")
    assert "Accepteren" in ch1.get("/route/1").get_data(as_text=True)
    # coördinator verplaatst naar route 2
    post(c, "/bericht/2/route", {"route_id": "2"}, "/portaal")
    assert "Accepteren" not in ch1.get("/route/1").get_data(as_text=True)
    assert "Accepteren" in ch2.get("/route/2").get_data(as_text=True)
    # chauffeur van de verkeerde route mag niet accepteren
    assert post(ch1, "/bericht/2/accepteer", tokenurl="/route/1").status_code == 403
    # juiste chauffeur accepteert: nu onderweg met bel-knop
    post(ch2, "/bericht/2/accepteer", tokenurl="/route/2")
    pagina = ch2.get("/route/2").get_data(as_text=True)
    assert "Bel voorzitter stembureau-5" in pagina
    # geaccepteerd: verplaatsen niet meer mogelijk
    r = post(c, "/bericht/2/route", {"route_id": "1"}, "/portaal", follow_redirects=True)
    assert "al geaccepteerd" in r.get_data(as_text=True)
    assert "Bel voorzitter" in ch2.get("/route/2").get_data(as_text=True)
    # uitzetten: wachtende opdrachten gaan direct onderweg
    c.post(f"/api/sms?sleutel={k}", json={"message": "5"})
    post(c, "/bericht/3/route", {"route_id": "1"}, "/portaal")
    post(c, "/beheer/werkwijze", {}, "/beheer")
    assert "Bel voorzitter" in ch1.get("/route/1").get_data(as_text=True)


def test_waarschuwing_niet_geaccepteerd(client):
    import sqlite3
    c = client
    maak_admin(c)
    post(c, "/beheer/routes", {"aantal": "1"}, "/beheer")
    post(c, "/beheer/stembureaus/opslaan", {"nummer": "5", "naam": "A", "adres": "x", "telefoon": "061", "route_id": "1"}, "/beheer/stembureaus")
    post(c, "/beheer/werkwijze", {"accepteren_verplicht": "1", "accepteer_drempel": "5"}, "/beheer")
    c.post(f"/api/sms?sleutel={sleutel(c)}", json={"message": "5"})
    post(c, "/bericht/1/route", {"route_id": "1"}, "/portaal")
    assert "Nog niet geaccepteerd" not in c.get("/portaal").get_data(as_text=True)
    assert c.get("/scherm/data.json").get_json()["routes"][0]["niveau"] == "groen"

    def oud_maken(minuten):
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        t = (datetime.now(ZoneInfo("Europe/Amsterdam")) - timedelta(minutes=minuten)).strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(c.application.config["DATABASE"]) as d:
            d.execute("UPDATE bericht SET onderweg_op=? WHERE id=1", (t,))
    oud_maken(6)
    assert "Nog niet geaccepteerd na 6 min" in c.get("/portaal").get_data(as_text=True)
    assert c.get("/scherm/data.json").get_json()["routes"][0]["niveau"] == "oranje"
    oud_maken(11)
    assert c.get("/scherm/data.json").get_json()["routes"][0]["niveau"] == "rood"
    post(c, "/bericht/1/accepteer", tokenurl="/portaal")
    assert "Nog niet geaccepteerd" not in c.get("/portaal").get_data(as_text=True)


def test_portaal_status_en_geluidinstelling(client):
    c = client
    maak_admin(c)
    post(c, "/beheer/routes", {"aantal": "1"}, "/beheer")
    post(c, "/beheer/stembureaus/opslaan", {"nummer": "5", "naam": "A", "adres": "x", "telefoon": "061", "route_id": "1"}, "/beheer/stembureaus")
    s0 = c.get("/portaal/status.json").get_json()
    assert s0["geluid"] is True and s0["nieuwste"] == 0  # standaard aan
    c.post(f"/api/sms?sleutel={sleutel(c)}", json={"message": "5"})
    s1 = c.get("/portaal/status.json").get_json()
    assert s1["nieuwste"] == 1 and s1["handtekening"] != s0["handtekening"]
    post(c, "/bericht/1/route", {"route_id": "1"}, "/portaal")
    s2 = c.get("/portaal/status.json").get_json()
    assert s2["handtekening"] != s1["handtekening"] and s2["nieuwste"] == 1  # wijziging, maar geen nieuw bericht
    assert c.get("/portaal/status.json").get_json()["handtekening"] == s2["handtekening"]  # stabiel
    # uitschakelen in beheer
    post(c, "/beheer/werkwijze", {"accepteer_drempel": "5"}, "/beheer")
    assert c.get("/portaal/status.json").get_json()["geluid"] is False
    assert "geluidknop" in c.get("/portaal").get_data(as_text=True)  # knop blijft in pagina, JS verbergt hem
    post(c, "/beheer/werkwijze", {"geluid_nieuw": "1"}, "/beheer")
    assert c.get("/portaal/status.json").get_json()["geluid"] is True
    # alleen voor coördinator/beheerder
    assert c.application.test_client().get("/portaal/status.json").status_code == 302


def test_chauffeur_melding_status_en_instelling(client):
    c = client
    maak_admin(c)
    post(c, "/beheer/routes", {"aantal": "2"}, "/beheer")
    post(c, "/beheer/stembureaus/opslaan", {"nummer": "5", "naam": "School A", "adres": "x", "telefoon": "061", "route_id": "1"}, "/beheer/stembureaus")
    post(c, "/beheer/gebruikers/nieuw", {"naam": "ch1", "wachtwoord": "chauffeur1234", "rol": "chauffeur", "route_id": "1"}, "/beheer/gebruikers")
    ch = c.application.test_client()
    post(ch, "/login", {"naam": "ch1", "wachtwoord": "chauffeur1234"})
    s0 = ch.get("/route/1/status.json").get_json()
    assert s0["items"] == [] and s0["melding"] is True
    assert ch.get("/route/2/status.json").status_code == 403  # alleen eigen route
    c.post(f"/api/sms?sleutel={sleutel(c)}", json={"message": "5"})
    assert ch.get("/route/1/status.json").get_json()["items"] == []  # nog niet toegewezen
    post(c, "/bericht/1/route", {"route_id": "1"}, "/portaal")
    s1 = ch.get("/route/1/status.json").get_json()
    assert s1["items"][0]["nr"] == 5 and s1["items"][0]["naam"] == "School A" and s1["handtekening"] != s0["handtekening"]
    assert 'id="geluidknop"' in ch.get("/route/1").get_data(as_text=True)  # knop in de header
    # beheerder zet de melding uit
    post(c, "/beheer/werkwijze", {"geluid_nieuw": "1"}, "/beheer")
    assert ch.get("/route/1/status.json").get_json()["melding"] is False
    # overzichtsscherm krijgt ook de gegevens voor het geluid
    d = c.get("/scherm/data.json").get_json()
    assert d["nieuwste"] == 1 and d["geluid"] is True
    assert "geluid.js" in c.get("/scherm").get_data(as_text=True)
    assert c.get("/static/geluid.js").status_code == 200


def test_oude_route_krijgt_melding_bij_verplaatsen(client):
    c = client
    maak_admin(c)
    post(c, "/beheer/routes", {"aantal": "2"}, "/beheer")
    post(c, "/beheer/stembureaus/opslaan", {"nummer": "5", "naam": "School A", "adres": "x", "telefoon": "061", "route_id": "1"}, "/beheer/stembureaus")
    post(c, "/beheer/gebruikers/nieuw", {"naam": "ch1", "wachtwoord": "chauffeur1234", "rol": "chauffeur", "route_id": "1"}, "/beheer/gebruikers")
    post(c, "/beheer/gebruikers/nieuw", {"naam": "ch2", "wachtwoord": "chauffeur5678", "rol": "chauffeur", "route_id": "2"}, "/beheer/gebruikers")
    ch1, ch2 = c.application.test_client(), c.application.test_client()
    post(ch1, "/login", {"naam": "ch1", "wachtwoord": "chauffeur1234"})
    post(ch2, "/login", {"naam": "ch2", "wachtwoord": "chauffeur5678"})
    post(c, "/beheer/werkwijze", {"accepteren_verplicht": "1", "melding_chauffeur": "1", "geluid_nieuw": "1"}, "/beheer")
    c.post(f"/api/sms?sleutel={sleutel(c)}", json={"message": "5"})
    post(c, "/bericht/1/route", {"route_id": "1"}, "/portaal")
    assert ch1.get("/route/1/status.json").get_json()["meldingen"] == []  # eerste toewijzing: geen verplaatsmelding
    post(c, "/bericht/1/route", {"route_id": "2"}, "/portaal")
    m = ch1.get("/route/1/status.json?na=0").get_json()["meldingen"]
    assert len(m) == 1 and "Stembureau 5 – School A" in m[0]["tekst"] and "route 2" in m[0]["tekst"]
    assert ch1.get(f"/route/1/status.json?na={m[0]['id']}").get_json()["meldingen"] == []  # maar één keer
    assert ch2.get("/route/2/status.json").get_json()["meldingen"] == []  # nieuwe route krijgt gewone opdracht-melding
    assert ch2.get("/route/2/status.json").get_json()["items"][0]["nr"] == 5
    # pagina begint na de laatste melding, zodat oude meldingen niet opnieuw getoond worden
    assert f"laatsteMelding={m[0]['id']}" in ch1.get("/route/1").get_data(as_text=True).replace(" ", "")


def test_logo_en_favicon(client):
    r = client.get("/favicon.ico")
    assert r.status_code == 200 and r.data[:4] == b"\x00\x00\x01\x00"
    for f in ("favicon.svg", "logo.svg", "logo-licht.svg", "icon.svg", "apple-touch-icon.png", "icon-192.png", "icon-512.png"):
        assert client.get("/static/" + f).status_code == 200
    login = client.get("/login").get_data(as_text=True)
    assert "favicon.svg" in login and "logo.svg" in login and "StemBureauLogistiek" in login


def test_huisstijl_bestanden(client):
    css = client.get("/static/stijl.css").get_data(as_text=True)
    assert "--marine:#0b2a5b" in css and "--oranje:#ff7a1a" in css
    fonts = client.get("/static/fonts.css").get_data(as_text=True)
    assert "FiraSans-Regular.woff" in fonts
    for f in ("FiraSans-Regular.woff", "FiraSans-Medium.woff", "FiraSans-Bold.woff", "OFL-FiraSans.txt"):
        assert client.get("/static/fonts/" + f).status_code == 200
    assert "stijl.css" in client.get("/login").get_data(as_text=True) and "fonts.css" in client.get("/login").get_data(as_text=True)


def test_eigen_webhooksleutel(client):
    maak_admin(client)
    t = token(client)
    post(client, "/beheer/instellingen", {"csrf": t, "sleutel_modus": "eigen", "eigen_sleutel": "test123"})
    assert client.post("/api/sms?sleutel=test123", data={"message": "1"}).status_code != 403
    post(client, "/beheer/instellingen", {"csrf": t, "sleutel_modus": "eigen", "eigen_sleutel": "a b!"})
    assert client.post("/api/sms?sleutel=a b!", data={"message": "1"}).status_code == 403
    post(client, "/beheer/instellingen", {"csrf": t, "sleutel_modus": "veilig"})
    assert client.post("/api/sms?sleutel=test123", data={"message": "1"}).status_code == 403


def test_routes_pagina_stadia(client):
    maak_admin(client)
    r = client.get("/routes")
    assert r.status_code == 200
    t = r.get_data(as_text=True)
    assert "Onderweg" in t and "Klaar vandaag" in t
