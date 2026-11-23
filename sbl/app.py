"""SBL Logistiek Portaal - kern van de webapp."""
import io
import json
import os
import secrets
import threading
import time
import urllib.request
import sqlite3
from datetime import datetime
from functools import wraps
from zoneinfo import ZoneInfo

from werkzeug.middleware.proxy_fix import ProxyFix
from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import importer, totp

HIER = os.path.dirname(__file__)
ROLLEN = ("beheerder", "coordinator", "chauffeur")


def nu(app=None):
    tz = ZoneInfo((app or __import__("flask").current_app).config["TIJDZONE"])
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def migreer(c):
    """Maakt tabellen/kolommen aan; veilig om herhaald uit te voeren (ook na herstel van een oude back-up)."""
    c.executescript(open(os.path.join(HIER, "schema.sql")).read())
    kolommen = {k[1] for k in c.execute("PRAGMA table_info(gebruiker)")}
    for kol, typ in (("totp_geheim", "TEXT"), ("totp_laatst", "INTEGER NOT NULL DEFAULT 0"),
                     ("herstel", "TEXT NOT NULL DEFAULT '[]'"),
                     ("moet_wijzigen", "INTEGER NOT NULL DEFAULT 0")):
        if kol not in kolommen:
            c.execute(f"ALTER TABLE gebruiker ADD COLUMN {kol} {typ}")
    c.commit()


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.environ.get("SBL_DATABASE", "sbl.db"),
        SECRET_KEY=os.environ.get("SBL_SECRET_KEY", ""),
        TIJDZONE=os.environ.get("SBL_TIJDZONE", "Europe/Amsterdam"),
        TWEEFA_VERPLICHT=os.environ.get("SBL_2FA_VERPLICHT", "1") == "1",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SBL_HTTPS", "0") == "1",
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    )
    if config:
        app.config.update(config)
    if os.environ.get("SBL_PROXY", "0") == "1":  # achter een reverse proxy (Plesk/nginx/Caddy)
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    if not app.config["SECRET_KEY"]:
        # Vaste sleutel in de database zodat sessies een herstart overleven.
        app.config["SECRET_KEY"] = "tijdelijk"
    with sqlite3.connect(app.config["DATABASE"]) as c:
        migreer(c)
        r = c.execute("SELECT value FROM instelling WHERE key='secret_key'").fetchone()
        if not r:
            c.execute("INSERT INTO instelling VALUES ('secret_key', ?)", (secrets.token_hex(32),))
            r = c.execute("SELECT value FROM instelling WHERE key='secret_key'").fetchone()
        if app.config["SECRET_KEY"] == "tijdelijk":
            app.config["SECRET_KEY"] = r[0]
        if not c.execute("SELECT value FROM instelling WHERE key='sms_sleutel'").fetchone():
            c.execute("INSERT INTO instelling VALUES ('sms_sleutel', ?)", (secrets.token_urlsafe(24),))

    # ---------- database ----------
    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys=ON")
        return g.db

    @app.teardown_appcontext
    def sluit(_):
        d = g.pop("db", None)
        if d:
            d.commit()
            d.close()

    def instelling(key, default=""):
        r = db().execute("SELECT value FROM instelling WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def zet_instelling(key, value):
        db().execute("INSERT INTO instelling VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (key, str(value)))

    def audit(actie):
        db().execute("INSERT INTO audit (tijd, gebruiker, actie) VALUES (?,?,?)",
                     (nu(app), session.get("naam"), actie))

    # ---------- inloggen, csrf, rollen ----------
    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return session["csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def csrf_controle():
        if request.method == "POST" and request.endpoint not in ("api_sms", "api_heartbeat"):
            if not secrets.compare_digest(request.form.get("csrf", ""), session.get("csrf", "x")):
                abort(400, "Ongeldig formulier (csrf)")

    @app.before_request
    def laad_gebruiker():
        g.gebruiker = None
        if session.get("uid"):
            g.gebruiker = db().execute("SELECT * FROM gebruiker WHERE id=?", (session["uid"],)).fetchone()
            if not g.gebruiker:
                session.clear()
            elif (g.gebruiker["moet_wijzigen"]
                  and request.endpoint not in ("wachtwoord_verplicht", "wachtwoord_wijzigen", "logout", "static")):
                return redirect(url_for("wachtwoord_verplicht"))
            elif (app.config["TWEEFA_VERPLICHT"] and g.gebruiker["rol"] != "chauffeur"
                  and not g.gebruiker["totp_geheim"]
                  and request.endpoint not in ("account", "tweefa_start", "tweefa_bevestig", "wachtwoord_wijzigen", "logout", "static")):
                return redirect(url_for("account"))

    def rol_vereist(*rollen):
        def deco(f):
            @wraps(f)
            def inner(*a, **k):
                if not g.gebruiker:
                    return redirect(url_for("login", next=request.path))
                if g.gebruiker["rol"] not in rollen:
                    abort(403)
                return f(*a, **k)
            return inner
        return deco

    @app.context_processor
    def sjabloon_context():
        gb = g.get("gebruiker")
        return {"gebruiker": gb, "nu_tijd": nu(app),
                "storing": bool(gb and gb["rol"] != "chauffeur" and storing_nu(db()))}

    # ---------- helpers ----------
    def advies_route(bericht):
        if bericht["stembureau_id"]:
            r = db().execute("SELECT route_id FROM stembureau WHERE id=?", (bericht["stembureau_id"],)).fetchone()
            return r["route_id"] if r else None

    def routes():
        return db().execute("SELECT * FROM route ORDER BY nummer").fetchall()

    # ---------- publiek ----------
    @app.get("/")
    def start():
        if not g.gebruiker:
            if not db().execute("SELECT 1 FROM gebruiker").fetchone():
                return redirect(url_for("setup"))
            return redirect(url_for("login"))
        if g.gebruiker["rol"] == "chauffeur":
            if g.gebruiker["route_id"]:
                return redirect(url_for("route_pagina", route_id=g.gebruiker["route_id"]))
            return render_template("melding.html", tekst="Aan dit account is nog geen route gekoppeld.")
        return redirect(url_for("portaal"))

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        if db().execute("SELECT 1 FROM gebruiker").fetchone():
            abort(404)
        if request.method == "POST":
            naam, ww = request.form["naam"].strip(), request.form["wachtwoord"]
            if not naam or len(ww) < 10:
                flash("Kies een naam en een wachtwoord van minimaal 10 tekens.")
            else:
                db().execute("INSERT INTO gebruiker (naam, hash, rol) VALUES (?,?,'beheerder')",
                             (naam, generate_password_hash(ww)))
                flash("Beheerder aangemaakt. Log nu in.")
                return redirect(url_for("login"))
        return render_template("setup.html")

    def voltooi_login(u, nxt=""):
        session["uid"], session["naam"] = u["id"], u["naam"]
        audit("inloggen")
        return redirect(nxt or url_for("start"))

    def herstel_hash(code):
        norm = "".join(ch for ch in code.upper() if ch.isalnum())
        import hashlib
        import hmac as _hmac
        return _hmac.new(app.config["SECRET_KEY"].encode(), norm.encode(), hashlib.sha256).hexdigest()

    def nieuwe_herstelcodes(uid):
        codes = ["-".join(("".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(10)))[i:i + 5]
                          for i in (0, 5)) for _ in range(8)]
        db().execute("UPDATE gebruiker SET herstel=? WHERE id=?",
                     (json.dumps([herstel_hash(c) for c in codes]), uid))
        return codes

    @app.route("/login/2fa", methods=["GET", "POST"])
    def login_2fa():
        u = db().execute("SELECT * FROM gebruiker WHERE id=?", (session.get("pre_uid"),)).fetchone()
        if not u or time.time() - session.get("pre_tijd", 0) > 300:
            session.clear()
            return redirect(url_for("login"))
        if request.method == "POST":
            nu_ts = time.time()
            sl = "n:" + u["naam"].lower()
            if db().execute("SELECT COUNT(*) c FROM login_poging WHERE sleutel=?", (sl,)).fetchone()["c"] >= 10:
                return render_template("login_2fa.html"), 429
            invoer = request.form.get("code", "")
            teller = totp.controleer(u["totp_geheim"], invoer, u["totp_laatst"])
            hersteld = False
            if not teller:
                lijst = json.loads(u["herstel"] or "[]")
                h = herstel_hash(invoer)
                if h in lijst:
                    lijst.remove(h)
                    db().execute("UPDATE gebruiker SET herstel=? WHERE id=?", (json.dumps(lijst), u["id"]))
                    hersteld = True
                    audit(f"herstelcode gebruikt door {u['naam']}")
            if teller or hersteld:
                if teller:
                    db().execute("UPDATE gebruiker SET totp_laatst=? WHERE id=?", (teller, u["id"]))
                nxt = session.get("pre_next", "")
                session.clear()
                return voltooi_login(u, nxt)
            db().execute("INSERT INTO login_poging (tijd, sleutel) VALUES (?,?)", (nu_ts, sl))
            flash("Onjuiste code.")
        return render_template("login_2fa.html")

    @app.get("/account")
    def account():
        if not g.gebruiker:
            return redirect(url_for("login"))
        geheim = session.get("nieuw_totp")
        n_herstel = len(json.loads(g.gebruiker["herstel"] or "[]"))
        return render_template("account.html", geheim=geheim, n_herstel=n_herstel,
                               uri=totp.uri(geheim, g.gebruiker["naam"]) if geheim else None,
                               qr=totp.qr_svg(totp.uri(geheim, g.gebruiker["naam"])) if geheim else None,
                               verplicht=app.config["TWEEFA_VERPLICHT"] and g.gebruiker["rol"] != "chauffeur")

    @app.post("/account/2fa/start")
    def tweefa_start():
        if not g.gebruiker:
            abort(403)
        session["nieuw_totp"] = totp.nieuw_geheim()
        return redirect(url_for("account"))

    @app.post("/account/2fa/bevestig")
    def tweefa_bevestig():
        if not g.gebruiker or not session.get("nieuw_totp"):
            abort(403)
        teller = totp.controleer(session["nieuw_totp"], request.form.get("code"))
        if not teller:
            flash("Code onjuist. Probeer het opnieuw.")
            return redirect(url_for("account"))
        db().execute("UPDATE gebruiker SET totp_geheim=?, totp_laatst=? WHERE id=?",
                     (session.pop("nieuw_totp"), teller, g.gebruiker["id"]))
        audit("2fa ingeschakeld")
        return render_template("herstelcodes.html", codes=nieuwe_herstelcodes(g.gebruiker["id"]))

    @app.post("/account/2fa/herstelcodes")
    def tweefa_nieuwe_codes():
        if not g.gebruiker or not g.gebruiker["totp_geheim"]:
            abort(403)
        teller = totp.controleer(g.gebruiker["totp_geheim"], request.form.get("code"), g.gebruiker["totp_laatst"])
        if not teller:
            flash("Code onjuist; er zijn geen nieuwe herstelcodes gemaakt.")
            return redirect(url_for("account"))
        db().execute("UPDATE gebruiker SET totp_laatst=? WHERE id=?", (teller, g.gebruiker["id"]))
        audit("nieuwe herstelcodes")
        return render_template("herstelcodes.html", codes=nieuwe_herstelcodes(g.gebruiker["id"]))

    @app.post("/account/wachtwoord")
    def wachtwoord_wijzigen():
        if not g.gebruiker:
            abort(403)
        f = request.form
        if not check_password_hash(g.gebruiker["hash"], f.get("huidig", "")):
            flash("Huidig wachtwoord klopt niet.")
        elif len(f.get("nieuw", "")) < 10 or f.get("nieuw") != f.get("nieuw2"):
            flash("Nieuw wachtwoord: minimaal 10 tekens en beide velden gelijk.")
        elif f["nieuw"] == f.get("huidig"):
            flash("Kies een ander wachtwoord dan het huidige.")
        else:
            db().execute("UPDATE gebruiker SET hash=?, moet_wijzigen=0 WHERE id=?",
                         (generate_password_hash(f["nieuw"]), g.gebruiker["id"]))
            audit("wachtwoord gewijzigd")
            flash("Wachtwoord gewijzigd.")
            return redirect(url_for("start"))
        return redirect(url_for("wachtwoord_verplicht" if g.gebruiker["moet_wijzigen"] else "account"))

    @app.get("/account/nieuw-wachtwoord")
    def wachtwoord_verplicht():
        if not g.gebruiker:
            return redirect(url_for("login"))
        return render_template("wachtwoord_verplicht.html")

    @app.post("/beheer/gebruikers/<int:uid>/wachtwoord")
    @rol_vereist("beheerder")
    def gebruiker_wachtwoord(uid):
        nieuw = request.form.get("nieuw", "")
        if len(nieuw) < 10:
            flash("Wachtwoord moet minimaal 10 tekens zijn.")
        else:
            db().execute("UPDATE gebruiker SET hash=?, moet_wijzigen=1 WHERE id=?", (generate_password_hash(nieuw), uid))
            audit(f"wachtwoord gereset voor gebruiker-id {uid}")
            flash("Wachtwoord ingesteld.")
        return redirect(url_for("beheer_gebruikers"))

    @app.post("/beheer/gebruikers/<int:uid>/reset2fa")
    @rol_vereist("beheerder")
    def gebruiker_reset2fa(uid):
        db().execute("UPDATE gebruiker SET totp_geheim=NULL, totp_laatst=0 WHERE id=?", (uid,))
        audit(f"2fa gereset voor gebruiker-id {uid}")
        flash("2FA gereset; de gebruiker stelt het bij de volgende keer opnieuw in.")
        return redirect(url_for("beheer_gebruikers"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            naam = request.form["naam"].strip().lower()
            nu_ts = time.time()
            db().execute("DELETE FROM login_poging WHERE tijd<?", (nu_ts - 900,))
            mislukt = db().execute("SELECT COUNT(*) c FROM login_poging WHERE sleutel IN (?,?)",
                                   ("n:" + naam, "ip:" + (request.remote_addr or ""))).fetchone()["c"]
            if mislukt >= 10:
                flash("Te veel mislukte pogingen. Probeer het over 15 minuten opnieuw.")
                return render_template("login.html"), 429
            u = db().execute("SELECT * FROM gebruiker WHERE naam=?", (request.form["naam"].strip(),)).fetchone()
            if not (u and check_password_hash(u["hash"], request.form["wachtwoord"])):
                for k in ("n:" + naam, "ip:" + (request.remote_addr or "")):
                    db().execute("INSERT INTO login_poging (tijd, sleutel) VALUES (?,?)", (nu_ts, k))
            if u and check_password_hash(u["hash"], request.form["wachtwoord"]):
                nxt = request.args.get("next", "")
                nxt = nxt if nxt.startswith("/") and not nxt.startswith("//") else ""
                session.clear()
                if u["totp_geheim"]:
                    session["pre_uid"], session["pre_tijd"], session["pre_next"] = u["id"], time.time(), nxt
                    return redirect(url_for("login_2fa"))
                return voltooi_login(u, nxt)
            flash("Onjuiste naam of wachtwoord.")
        return render_template("login.html")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ---------- api ----------
    def sms_tekst():
        d = request.get_json(silent=True) or {}
        for k in ("message", "text", "body", "tekst", "content"):
            v = d.get(k) or request.values.get(k)
            if v:
                return str(v).strip()
        return ""

    @app.post("/api/sms")
    def api_sms():
        sleutel = request.headers.get("X-SBL-Sleutel") or request.args.get("sleutel", "")
        if not secrets.compare_digest(sleutel, instelling("sms_sleutel")):
            abort(403)
        tekst = sms_tekst()
        digits = "".join(ch for ch in tekst if ch.isdigit())
        sb = db().execute("SELECT * FROM stembureau WHERE nummer=?", (int(digits),)).fetchone() if digits else None
        cur = db().execute("INSERT INTO bericht (stembureau_id, tekst, ontvangen) VALUES (?,?,?)",
                           (sb["id"] if sb else None, tekst[:500], nu(app)))
        return jsonify(ok=True, id=cur.lastrowid, herkend=bool(sb)), 201

    @app.route("/api/heartbeat", methods=["GET", "POST"])
    def api_heartbeat():
        sleutel = request.headers.get("X-SBL-Sleutel") or request.args.get("sleutel", "")
        if not secrets.compare_digest(sleutel, instelling("sms_sleutel")):
            abort(403)
        zet_instelling("laatste_ping", nu(app))
        return jsonify(ok=True)

    def storing_nu(conn):
        def inst(k, d=""):
            r = conn.execute("SELECT value FROM instelling WHERE key=?", (k,)).fetchone()
            return r[0] if r else d
        p = inst("laatste_ping")
        if not p:
            return False
        tz = ZoneInfo(app.config["TIJDZONE"])
        verschil = datetime.now(tz) - datetime.strptime(p, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
        return verschil.total_seconds() > int(inst("storing_seconden", "600"))

    def gateway_storing():
        return storing_nu(db())

    def stuur_melding(url, titel, tekst):
        try:
            req = urllib.request.Request(url, data=tekst.encode(), method="POST",
                                         headers={"Title": titel.encode("latin-1", "ignore").decode(), "Priority": "high"})
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:  # melding mag de app nooit laten crashen
            app.logger.warning("Melding versturen mislukt: %s", e)

    def bewaak_gateway():
        """Controleert de heartbeat; meldt storing en herstel precies één keer (ook bij meerdere workers)."""
        with sqlite3.connect(app.config["DATABASE"], timeout=10) as c:
            def inst(k, d=""):
                r = c.execute("SELECT value FROM instelling WHERE key=?", (k,)).fetchone()
                return r[0] if r else d
            url = inst("notificatie_url")
            c.execute("INSERT OR IGNORE INTO instelling VALUES ('storing_gemeld','0')")
            storing = storing_nu(c)
            if storing and c.execute("UPDATE instelling SET value='1' WHERE key='storing_gemeld' AND value='0'").rowcount:
                c.execute("INSERT INTO audit (tijd, gebruiker, actie) VALUES (?,?,?)", (nu(app), None, "gateway-storing"))
                c.commit()
                if url:
                    stuur_melding(url, "SBL Portaal: storing", "De sms-gateway heeft zich niet gemeld. Controleer de gateway-telefoon.")
            elif not storing and c.execute("UPDATE instelling SET value='0' WHERE key='storing_gemeld' AND value='1'").rowcount:
                c.execute("INSERT INTO audit (tijd, gebruiker, actie) VALUES (?,?,?)", (nu(app), None, "gateway hersteld"))
                c.commit()
                if url:
                    stuur_melding(url, "SBL Portaal: hersteld", "De sms-gateway meldt zich weer.")

    app.bewaak_gateway = bewaak_gateway

    def start_bewaking():
        def lus():
            while True:
                time.sleep(30)
                try:
                    bewaak_gateway()
                except Exception as e:
                    app.logger.warning("Bewaking fout: %s", e)
        threading.Thread(target=lus, daemon=True).start()

    if not app.config.get("TESTING") and os.environ.get("SBL_BEWAKING", "1") == "1":
        start_bewaking()

    # ---------- portaal (beheerder + coordinator) ----------
    @app.get("/portaal")
    @rol_vereist("beheerder", "coordinator")
    def portaal():
        rows = db().execute("""SELECT b.*, s.nummer AS sb_nummer, s.naam AS sb_naam, s.adres, s.telefoon,
                                      s.route_id AS advies, r.nummer AS route_nummer
                               FROM bericht b LEFT JOIN stembureau s ON s.id=b.stembureau_id
                               LEFT JOIN route r ON r.id=b.route_id
                               WHERE b.status!='klaar' ORDER BY b.ontvangen""").fetchall()
        nieuw = [r for r in rows if r["status"] == "nieuw"]
        onderweg = [r for r in rows if r["status"] == "onderweg"]
        klaar = db().execute("""SELECT b.*, s.nummer AS sb_nummer, s.naam AS sb_naam, r.nummer AS route_nummer
                                FROM bericht b LEFT JOIN stembureau s ON s.id=b.stembureau_id
                                LEFT JOIN route r ON r.id=b.route_id
                                WHERE b.status='klaar' ORDER BY b.klaar_op DESC LIMIT 20""").fetchall()
        adviesnrs = {r["id"]: r["nummer"] for r in routes()}
        return render_template("portaal.html", nieuw=nieuw, onderweg=onderweg, klaar=klaar,
                               routes=routes(), adviesnrs=adviesnrs)

    @app.post("/bericht/<int:bid>/route")
    @rol_vereist("beheerder", "coordinator")
    def bericht_route(bid):
        route_id = request.form.get("route_id", type=int)
        if not db().execute("SELECT 1 FROM route WHERE id=?", (route_id,)).fetchone():
            abort(400, "Onbekende route")
        db().execute("UPDATE bericht SET status='onderweg', route_id=?, onderweg_op=? WHERE id=? AND status='nieuw'",
                     (route_id, nu(app), bid))
        audit(f"bericht {bid} naar route-id {route_id}")
        return redirect(url_for("portaal"))

    @app.post("/bericht/<int:bid>/klaar")
    @rol_vereist("beheerder", "coordinator", "chauffeur")
    def bericht_klaar(bid):
        b = db().execute("SELECT * FROM bericht WHERE id=?", (bid,)).fetchone()
        if not b:
            abort(404)
        if g.gebruiker["rol"] == "chauffeur" and b["route_id"] != g.gebruiker["route_id"]:
            abort(403)
        db().execute("UPDATE bericht SET status='klaar', klaar_op=? WHERE id=? AND status='onderweg'", (nu(app), bid))
        audit(f"bericht {bid} klaar")
        terug = request.form.get("terug", "")
        return redirect(terug if terug.startswith("/") and not terug.startswith("//") else url_for("start"))

    @app.post("/bericht/<int:bid>/verwijder")
    @rol_vereist("beheerder", "coordinator")
    def bericht_verwijder(bid):
        db().execute("DELETE FROM bericht WHERE id=?", (bid,))
        audit(f"bericht {bid} verwijderd")
        return redirect(url_for("portaal"))

    @app.get("/bericht/<int:bid>/print")
    @rol_vereist("beheerder", "coordinator")
    def bericht_print(bid):
        b = db().execute("""SELECT b.*, s.nummer AS sb_nummer, s.naam AS sb_naam, s.adres, s.telefoon, r.nummer AS route_nummer
                            FROM bericht b LEFT JOIN stembureau s ON s.id=b.stembureau_id
                            LEFT JOIN route r ON r.id=b.route_id WHERE b.id=?""", (bid,)).fetchone()
        if not b:
            abort(404)
        return render_template("print.html", b=b)

    # ---------- routepagina ----------
    @app.get("/route/<int:route_id>")
    @rol_vereist("beheerder", "coordinator", "chauffeur")
    def route_pagina(route_id):
        if g.gebruiker["rol"] == "chauffeur" and g.gebruiker["route_id"] != route_id:
            abort(403)
        route = db().execute("SELECT * FROM route WHERE id=?", (route_id,)).fetchone()
        if not route:
            abort(404)
        items = db().execute("""SELECT b.*, s.nummer AS sb_nummer, s.naam AS sb_naam, s.adres, s.telefoon
                                FROM bericht b LEFT JOIN stembureau s ON s.id=b.stembureau_id
                                WHERE b.route_id=? AND b.status='onderweg' ORDER BY b.onderweg_op""", (route_id,)).fetchall()
        return render_template("route.html", route=route, items=items)

    @app.get("/routes")
    @rol_vereist("beheerder", "coordinator")
    def routes_overzicht():
        rows = db().execute("""SELECT r.*, (SELECT COUNT(*) FROM bericht b WHERE b.route_id=r.id AND b.status='onderweg') AS open
                               FROM route r ORDER BY r.nummer""").fetchall()
        return render_template("routes.html", rows=rows)

    # ---------- beheer ----------
    @app.get("/beheer")
    @rol_vereist("beheerder")
    def beheer():
        return render_template("beheer.html",
                               n_routes=db().execute("SELECT COUNT(*) c FROM route").fetchone()["c"],
                               n_sb=db().execute("SELECT COUNT(*) c FROM stembureau").fetchone()["c"],
                               sleutel=instelling("sms_sleutel"), storing_s=instelling("storing_seconden", "600"),
                               notificatie_url=instelling("notificatie_url"))

    @app.post("/beheer/routes")
    @rol_vereist("beheerder")
    def beheer_routes():
        n = request.form.get("aantal", type=int)
        if n is None or not 1 <= n <= 200:
            flash("Kies een aantal tussen 1 en 200.")
            return redirect(url_for("beheer"))
        for i in range(1, n + 1):
            db().execute("INSERT OR IGNORE INTO route (nummer, naam) VALUES (?,?)", (i, f"Route {i}"))
        extra = db().execute("SELECT id FROM route WHERE nummer>?", (n,)).fetchall()
        in_gebruik = [r["id"] for r in extra if db().execute(
            "SELECT 1 FROM stembureau WHERE route_id=? UNION SELECT 1 FROM bericht WHERE route_id=? AND status!='klaar'",
            (r["id"], r["id"])).fetchone()]
        if in_gebruik:
            flash("Routes boven het aantal zijn nog in gebruik en blijven bestaan.")
        for r in extra:
            if r["id"] not in in_gebruik:
                db().execute("DELETE FROM route WHERE id=?", (r["id"],))
        audit(f"aantal routes {n}")
        flash(f"Aantal routes ingesteld op {n}.")
        return redirect(url_for("beheer"))

    @app.post("/beheer/instellingen")
    @rol_vereist("beheerder")
    def beheer_instellingen():
        if request.form.get("nieuwe_sleutel"):
            zet_instelling("sms_sleutel", secrets.token_urlsafe(24))
            audit("sms-sleutel vernieuwd")
        url = request.form.get("notificatie_url", "").strip()
        if url == "" or url.startswith(("https://", "http://")):
            zet_instelling("notificatie_url", url)
        s = request.form.get("storing_seconden", type=int)
        if s and 60 <= s <= 86400:
            zet_instelling("storing_seconden", s)
        flash("Instellingen opgeslagen.")
        return redirect(url_for("beheer"))

    @app.get("/beheer/stembureaus")
    @rol_vereist("beheerder")
    def beheer_stembureaus():
        rows = db().execute("""SELECT s.*, r.nummer AS route_nummer FROM stembureau s
                               LEFT JOIN route r ON r.id=s.route_id ORDER BY s.nummer""").fetchall()
        return render_template("stembureaus.html", rows=rows, routes=routes())

    @app.post("/beheer/stembureaus/opslaan")
    @rol_vereist("beheerder")
    def stembureau_opslaan():
        f = request.form
        nr = f.get("nummer", type=int)
        if not nr:
            abort(400, "Nummer ontbreekt")
        route_id = f.get("route_id", type=int) or None
        db().execute("""INSERT INTO stembureau (nummer,naam,adres,telefoon,route_id) VALUES (?,?,?,?,?)
                        ON CONFLICT(nummer) DO UPDATE SET naam=excluded.naam, adres=excluded.adres,
                        telefoon=excluded.telefoon, route_id=excluded.route_id""",
                     (nr, f.get("naam", "").strip(), f.get("adres", "").strip(), f.get("telefoon", "").strip(), route_id))
        audit(f"stembureau {nr} opgeslagen")
        return redirect(url_for("beheer_stembureaus"))

    @app.post("/beheer/stembureaus/<int:sid>/verwijder")
    @rol_vereist("beheerder")
    def stembureau_verwijder(sid):
        db().execute("DELETE FROM stembureau WHERE id=?", (sid,))
        audit(f"stembureau-id {sid} verwijderd")
        return redirect(url_for("beheer_stembureaus"))

    @app.route("/beheer/import", methods=["GET", "POST"])
    @rol_vereist("beheerder")
    def beheer_import():
        if request.method == "POST" and "bestand" in request.files:
            f = request.files["bestand"]
            try:
                items, fouten = importer.verwerk(importer.lees_rijen(f.filename, f.read()))
            except importer.ImportFout as e:
                flash(str(e))
                return redirect(url_for("beheer_import"))
            bestaand = {r["nummer"] for r in db().execute("SELECT nummer FROM stembureau")}
            return render_template("import.html", voorbeeld=items, fouten=fouten,
                                   nieuw=sum(i["nummer"] not in bestaand for i in items),
                                   json_data=json.dumps(items))
        if request.method == "POST":  # bevestigen
            items = json.loads(request.form["data"])
            maxroute = max([i["route"] or 0 for i in items] + [0])
            if maxroute > 200:
                abort(400, "Routenummer te hoog")
            for n in range(1, maxroute + 1):
                db().execute("INSERT OR IGNORE INTO route (nummer, naam) VALUES (?,?)", (n, f"Route {n}"))
            if request.form.get("vervang") == "1":
                db().execute("DELETE FROM stembureau")
            for i in items:
                rid = None
                if i["route"]:
                    rid = db().execute("SELECT id FROM route WHERE nummer=?", (i["route"],)).fetchone()["id"]
                db().execute("""INSERT INTO stembureau (nummer,naam,adres,telefoon,route_id) VALUES (?,?,?,?,?)
                                ON CONFLICT(nummer) DO UPDATE SET naam=excluded.naam, adres=excluded.adres,
                                telefoon=excluded.telefoon, route_id=excluded.route_id""",
                             (i["nummer"], i["naam"], i["adres"], i["telefoon"], rid))
            audit(f"import van {len(items)} stembureaus")
            flash(f"{len(items)} stembureaus geïmporteerd.")
            return redirect(url_for("beheer_stembureaus"))
        return render_template("import.html", voorbeeld=None)

    @app.get("/beheer/gebruikers")
    @rol_vereist("beheerder")
    def beheer_gebruikers():
        rows = db().execute("""SELECT u.*, r.nummer AS route_nummer FROM gebruiker u
                               LEFT JOIN route r ON r.id=u.route_id ORDER BY u.rol, u.naam""").fetchall()
        return render_template("gebruikers.html", rows=rows, routes=routes(), rollen=ROLLEN)

    @app.post("/beheer/gebruikers/nieuw")
    @rol_vereist("beheerder")
    def gebruiker_nieuw():
        f = request.form
        rol = f.get("rol")
        if rol not in ROLLEN or not f.get("naam", "").strip() or len(f.get("wachtwoord", "")) < 10:
            flash("Vul naam, rol en een wachtwoord van minimaal 10 tekens in.")
            return redirect(url_for("beheer_gebruikers"))
        try:
            db().execute("INSERT INTO gebruiker (naam,hash,rol,route_id,moet_wijzigen) VALUES (?,?,?,?,?)",
                         (f["naam"].strip(), generate_password_hash(f["wachtwoord"]), rol,
                          f.get("route_id", type=int) if rol == "chauffeur" else None,
                          1 if f.get("moet_wijzigen") else 0))
        except sqlite3.IntegrityError:
            flash("Deze naam bestaat al.")
        audit(f"gebruiker {f['naam']} aangemaakt")
        return redirect(url_for("beheer_gebruikers"))

    def tijdelijk_wachtwoord():
        alfabet = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
        return "".join(secrets.choice(alfabet) for _ in range(12))

    @app.post("/beheer/gebruikers/selectie")
    @rol_vereist("beheerder")
    def gebruikers_selectie():
        actie = request.form.get("actie", "")
        ids = [i for i in request.form.getlist("uid", type=int) if i != g.gebruiker["id"]]
        if not ids:
            flash("Selecteer eerst één of meer gebruikers (jezelf kun je hier niet wijzigen).")
            return redirect(url_for("beheer_gebruikers"))
        marks = ",".join("?" * len(ids))
        gekozen = db().execute(f"SELECT u.*, r.nummer AS route_nummer FROM gebruiker u "
                               f"LEFT JOIN route r ON r.id=u.route_id WHERE u.id IN ({marks}) ORDER BY u.naam", ids).fetchall()
        if actie == "wachtwoord":
            uit = []
            for u in gekozen:
                ww = tijdelijk_wachtwoord()
                db().execute("UPDATE gebruiker SET hash=?, moet_wijzigen=1 WHERE id=?", (generate_password_hash(ww), u["id"]))
                uit.append((u["naam"], u["route_nummer"], ww))
            audit(f"selectie: {len(uit)} wachtwoorden opnieuw ingesteld")
            return (render_template("bulk.html", routes=routes(), resultaat=uit, overgeslagen=[],
                                    melding=f"{len(uit)} nieuwe tijdelijke wachtwoorden ingesteld."),
                    200, {"Cache-Control": "no-store"})
        if actie == "wijzig_verplicht":
            db().execute(f"UPDATE gebruiker SET moet_wijzigen=1 WHERE id IN ({marks})", ids)
            flash(f"{len(ids)} gebruiker(s) moeten hun wachtwoord wijzigen bij de volgende login.")
        elif actie == "reset2fa":
            db().execute(f"UPDATE gebruiker SET totp_geheim=NULL, totp_laatst=0, herstel='[]' WHERE id IN ({marks})", ids)
            flash(f"2FA gereset voor {len(ids)} gebruiker(s).")
        elif actie == "route":
            rid = request.form.get("route_id", type=int)
            if not db().execute("SELECT 1 FROM route WHERE id=?", (rid,)).fetchone():
                flash("Kies een route.")
                return redirect(url_for("beheer_gebruikers"))
            n = db().execute(f"UPDATE gebruiker SET route_id=? WHERE rol='chauffeur' AND id IN ({marks})", [rid] + ids).rowcount
            flash(f"Route gewijzigd voor {n} chauffeur(s); anderen zijn overgeslagen.")
        elif actie == "verwijder":
            beheerders_over = db().execute(
                f"SELECT COUNT(*) c FROM gebruiker WHERE rol='beheerder' AND id NOT IN ({marks})", ids).fetchone()["c"]
            if beheerders_over < 1:
                flash("Je kunt niet alle beheerders verwijderen.")
                return redirect(url_for("beheer_gebruikers"))
            db().execute(f"DELETE FROM gebruiker WHERE id IN ({marks})", ids)
            flash(f"{len(ids)} gebruiker(s) verwijderd.")
        else:
            abort(400, "Onbekende actie")
        audit(f"selectie: {actie} voor {len(ids)} gebruiker(s)")
        return redirect(url_for("beheer_gebruikers"))

    @app.post("/beheer/gebruikers/wachtwoorden.xlsx")
    @rol_vereist("beheerder")
    def wachtwoorden_excel():
        from flask import send_file
        from openpyxl import Workbook
        from openpyxl.styles import Font
        try:
            rijen = json.loads(request.form.get("data", "[]"))[:500]
            rijen = [(str(n)[:80], "" if r is None else str(r)[:10], str(w)[:40]) for n, r, w in rijen]
        except (ValueError, TypeError):
            abort(400, "Ongeldige gegevens")
        wb = Workbook()
        ws = wb.active
        ws.title = "Tijdelijke wachtwoorden"
        ws.append(["Route", "Gebruikersnaam", "Tijdelijk wachtwoord", "Inloggen op"])
        for c in ws[1]:
            c.font = Font(bold=True)
        url = request.url_root.rstrip("/") + url_for("login")
        for n, r, w in rijen:
            ws.append([int(r) if r.isdigit() else r, n, w, url])
        for kol, breedte in zip("ABCD", (8, 22, 24, 40)):
            ws.column_dimensions[kol].width = breedte
        # wachtwoorden als tekst, zodat Excel er niets van maakt
        for rij in ws.iter_rows(min_row=2, min_col=3, max_col=3):
            rij[0].number_format = "@"
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        audit(f"wachtwoordenlijst gedownload ({len(rijen)} rijen)")
        resp = send_file(buf, as_attachment=True, download_name="tijdelijke-wachtwoorden.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/beheer/gebruikers/bulk", methods=["GET", "POST"])
    @rol_vereist("beheerder")
    def gebruikers_bulk():
        if request.method == "GET":
            return render_template("bulk.html", routes=routes(), resultaat=None)
        voorvoegsel = "".join(ch for ch in request.form.get("voorvoegsel", "route").strip() if ch.isalnum() or ch in "-_") or "route"
        gekozen = set(request.form.getlist("route_id", type=int))
        gemaakt, overgeslagen = [], []
        for r in routes():
            if r["id"] not in gekozen:
                continue
            naam = f"{voorvoegsel}{r['nummer']}"
            ww = tijdelijk_wachtwoord()
            try:
                db().execute("INSERT INTO gebruiker (naam,hash,rol,route_id,moet_wijzigen) VALUES (?,?,'chauffeur',?,1)",
                             (naam, generate_password_hash(ww), r["id"]))
                gemaakt.append((naam, r["nummer"], ww))
            except sqlite3.IntegrityError:
                overgeslagen.append(naam)
        audit(f"bulk: {len(gemaakt)} chauffeursaccounts aangemaakt")
        resp = render_template("bulk.html", routes=routes(), resultaat=gemaakt, overgeslagen=overgeslagen,
                               melding=f"{len(gemaakt)} accounts aangemaakt.")
        return resp, 200, {"Cache-Control": "no-store"}

    @app.post("/beheer/gebruikers/<int:uid>/verwijder")
    @rol_vereist("beheerder")
    def gebruiker_verwijder(uid):
        if uid == g.gebruiker["id"]:
            flash("Je kunt jezelf niet verwijderen.")
        else:
            db().execute("DELETE FROM gebruiker WHERE id=?", (uid,))
            audit(f"gebruiker-id {uid} verwijderd")
        return redirect(url_for("beheer_gebruikers"))

    @app.get("/beheer/backup")
    @rol_vereist("beheerder")
    def beheer_backup_pagina():
        return render_template("backup.html")

    @app.post("/beheer/backup/download")
    @rol_vereist("beheerder")
    def backup_download():
        import tempfile
        from flask import send_file
        db().commit()
        fd, pad = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        bron = sqlite3.connect(app.config["DATABASE"])
        doel = sqlite3.connect(pad)
        bron.backup(doel)
        doel.close()
        bron.close()
        audit("back-up gedownload")
        db().commit()
        naam = "sbl-backup-" + nu(app).replace(" ", "_").replace(":", "") + ".db"
        resp = send_file(pad, as_attachment=True, download_name=naam, mimetype="application/octet-stream")
        resp.call_on_close(lambda: os.path.exists(pad) and os.remove(pad))
        return resp

    @app.post("/beheer/backup/herstel")
    @rol_vereist("beheerder")
    def backup_herstel():
        import tempfile
        f = request.files.get("bestand")
        if request.form.get("bevestig", "").strip().upper() != "HERSTEL" or not f:
            flash("Kies een bestand en typ HERSTEL om te bevestigen.")
            return redirect(url_for("beheer_backup_pagina"))
        fd, pad = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            f.save(pad)
            bron = sqlite3.connect(pad)
            try:
                ok = bron.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                tabellen = {r[0] for r in bron.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                ok = ok and {"route", "stembureau", "bericht", "gebruiker", "instelling"} <= tabellen
                ok = ok and bron.execute("SELECT COUNT(*) FROM gebruiker WHERE rol='beheerder'").fetchone()[0] > 0
            except sqlite3.DatabaseError:
                ok = False
            if not ok:
                bron.close()
                flash("Dit is geen geldig back-upbestand (of er staat geen beheerder in).")
                return redirect(url_for("beheer_backup_pagina"))
            db().commit()
            doel = sqlite3.connect(app.config["DATABASE"], timeout=30)
            bron.backup(doel)
            bron.close()
            migreer(doel)
            doel.execute("INSERT INTO instelling VALUES ('secret_key', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                         (app.config["SECRET_KEY"],))
            doel.execute("INSERT INTO audit (tijd, gebruiker, actie) VALUES (?,?,?)",
                         (nu(app), session.get("naam"), "back-up hersteld"))
            doel.commit()
            doel.close()
        finally:
            os.remove(pad)
        session.clear()
        flash("Back-up hersteld. Log opnieuw in.")
        return redirect(url_for("login"))

    @app.get("/beheer/audit")
    @rol_vereist("beheerder")
    def beheer_audit():
        return render_template("audit.html", rows=db().execute("SELECT * FROM audit ORDER BY id DESC LIMIT 200").fetchall())

    @app.after_request
    def headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    return app
