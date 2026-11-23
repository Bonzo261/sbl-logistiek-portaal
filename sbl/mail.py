"""Versturen van e-mail via een willekeurige SMTP-server (standaardbibliotheek)."""
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

BEVEILIGING = ("starttls", "ssl", "geen")


class MailFout(Exception):
    pass


def stuur(cfg, aan, onderwerp, tekst):
    """cfg: host, poort, beveiliging, gebruiker, wachtwoord, van. Gooit MailFout met een leesbare melding."""
    if not cfg.get("host") or not cfg.get("van"):
        raise MailFout("Er is geen SMTP-server of afzenderadres ingesteld.")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg["van"], aan, onderwerp
    msg["Date"], msg["Message-ID"] = formatdate(localtime=True), make_msgid()
    msg.set_content(tekst)
    poort = int(cfg.get("poort") or 587)
    bev = cfg.get("beveiliging") or "starttls"
    ctx = ssl.create_default_context()
    try:
        if bev == "ssl":
            smtp = smtplib.SMTP_SSL(cfg["host"], poort, timeout=15, context=ctx)
        else:
            smtp = smtplib.SMTP(cfg["host"], poort, timeout=15)
        with smtp:
            smtp.ehlo()
            if bev == "starttls":
                smtp.starttls(context=ctx)
                smtp.ehlo()
            if cfg.get("gebruiker"):
                smtp.login(cfg["gebruiker"], cfg.get("wachtwoord", ""))
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise MailFout("Inloggen bij de mailserver is mislukt: controleer gebruiker en wachtwoord.")
    except smtplib.SMTPRecipientsRefused:
        raise MailFout("De mailserver weigert het ontvangersadres.")
    except (smtplib.SMTPException, OSError) as e:
        raise MailFout(f"Verbinding met de mailserver mislukt ({type(e).__name__}: {e}).")
