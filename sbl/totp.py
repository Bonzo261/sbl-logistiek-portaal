"""TOTP (RFC 6238) met alleen de standaardbibliotheek."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote


def nieuw_geheim():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def code(geheim, teller):
    sleutel = base64.b32decode(geheim + "=" * (-len(geheim) % 8))
    h = hmac.new(sleutel, struct.pack(">Q", teller), hashlib.sha1).digest()
    o = h[-1] & 15
    return "%06d" % ((struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000)


def controleer(geheim, invoer, laatste=0, nu=None):
    """Geeft de gebruikte teller terug als de code klopt (en nog niet gebruikt is), anders None."""
    invoer = "".join(ch for ch in (invoer or "") if ch.isdigit())
    t = int((nu if nu is not None else time.time()) // 30)
    for teller in (t - 1, t, t + 1):
        if teller > laatste and hmac.compare_digest(code(geheim, teller), invoer):
            return teller
    return None


def uri(geheim, naam, uitgever="SBL Portaal"):
    return f"otpauth://totp/{quote(uitgever)}:{quote(naam)}?secret={geheim}&issuer={quote(uitgever)}"


def qr_svg(tekst):
    """QR-code als data-URI (SVG). Geeft None als de bibliotheek 'segno' ontbreekt."""
    try:
        import segno
    except ImportError:
        return None
    return segno.make(tekst, error="m").svg_data_uri(scale=5, border=2)
