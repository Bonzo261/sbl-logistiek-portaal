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
