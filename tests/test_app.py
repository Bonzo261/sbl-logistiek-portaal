import io
import re

import pytest

from sbl import create_app

CSV = "Nummer;Locatie;Adres;Telefoon;Route\n1;School A;Dorpsstraat 1;0612345678;1\n2;Hal B;Kerklaan 2;0687654321;2\n"


@pytest.fixture()
def client(tmp_path):
    app = create_app({"DATABASE": str(tmp_path / "t.db"), "TESTING": True})
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
