"""Managementrapportage: rekent een lijst berichten (zonder persoonsgegevens) om naar cijfers.

Elke regel is een dict met: nummer (stembureau), naam, route_nummer, ontvangen, toegewezen,
geaccepteerd, klaar. De tijden zijn "JJJJ-MM-DD UU:MM:SS" (lokale tijd) of leeg.
"""
from datetime import datetime
from statistics import mean, median

FORMAAT = "%Y-%m-%d %H:%M:%S"


def _t(s):
    try:
        return datetime.strptime(s, FORMAAT) if s else None
    except ValueError:
        return None


def _sec(a, b):
    a, b = _t(a), _t(b)
    if a is None or b is None:
        return None
    return max(0, int((b - a).total_seconds()))


def duur(sec):
    """Seconden als leesbare tekst: '45 s', '12 min', '1 u 05 min'."""
    if sec is None:
        return "–"
    sec = int(round(sec))
    if sec < 60:
        return f"{sec} s"
    m = round(sec / 60)
    if m < 60:
        return f"{m} min"
    return f"{m // 60} u {m % 60:02d} min"


def _stat(waarden):
    w = [x for x in waarden if x is not None]
    if not w:
        return {"n": 0, "gem": None, "mediaan": None, "max": None, "min": None}
    return {"n": len(w), "gem": mean(w), "mediaan": median(w), "max": max(w), "min": min(w)}


def maak_rapport(regels, storingen=0):
    for r in regels:
        r["_wacht"] = _sec(r.get("ontvangen"), r.get("toegewezen"))
        r["_accept"] = _sec(r.get("toegewezen"), r.get("geaccepteerd"))
        r["_rit"] = _sec(r.get("toegewezen"), r.get("klaar"))      # toewijzen -> klaar
        r["_totaal"] = _sec(r.get("ontvangen"), r.get("klaar"))    # ontvangen -> klaar
    herkend = [r for r in regels if r.get("nummer") is not None]
    klaar = [r for r in regels if r.get("klaar")]

    # per stembureau: de eerste melding telt voor de tijden, het aantal meldingen staat erbij
    per_sb = {}
    for r in sorted(herkend, key=lambda x: x.get("ontvangen") or ""):
        d = per_sb.setdefault(r["nummer"], {"nummer": r["nummer"], "naam": r.get("naam") or "", "route": r.get("route_nummer"),
                                            "meldingen": 0, "eerste": r})
        d["meldingen"] += 1
    stembureaus = []
    for d in per_sb.values():
        e = d["eerste"]
        stembureaus.append({"nummer": d["nummer"], "naam": d["naam"], "route": e.get("route_nummer"), "meldingen": d["meldingen"],
                            "ontvangen": e.get("ontvangen"), "toegewezen": e.get("toegewezen"), "klaar": e.get("klaar"),
                            "wacht": e["_wacht"], "rit": e["_rit"], "totaal": e["_totaal"]})
    met_klaar = sorted([s for s in stembureaus if s["klaar"]], key=lambda s: s["klaar"])
    open_ = [s for s in stembureaus if not s["klaar"]]

    routes = {}
    for r in regels:
        if r.get("route_nummer") is None:
            continue
        routes.setdefault(r["route_nummer"], []).append(r)
    per_route = [{"route": n, "berichten": len(rs), "klaar": sum(1 for r in rs if r.get("klaar")),
                  "rit": _stat([r["_rit"] for r in rs])} for n, rs in sorted(routes.items())]

    uren = []
    for u in range(24):
        o = sum(1 for r in regels if (_t(r.get("ontvangen")) or datetime.min).hour == u and r.get("ontvangen"))
        k = sum(1 for r in regels if r.get("klaar") and (_t(r["klaar"]) or datetime.min).hour == u)
        uren.append({"uur": u, "ontvangen": o, "klaar": k})
    while uren and uren[0]["ontvangen"] == 0 and uren[0]["klaar"] == 0:
        uren.pop(0)
    while uren and uren[-1]["ontvangen"] == 0 and uren[-1]["klaar"] == 0:
        uren.pop()

    ontvangen = sorted(r["ontvangen"] for r in regels if r.get("ontvangen"))
    klaar_tijden = sorted(r["klaar"] for r in klaar)
    return {
        "berichten": len(regels), "herkend": len(herkend), "onbekend": len(regels) - len(herkend),
        "klaar": len(klaar), "open": len(regels) - len(klaar),
        "stembureaus": len(stembureaus), "stembureaus_klaar": len(met_klaar),
        "stembureaus_dubbel": sum(1 for s in stembureaus if s["meldingen"] > 1),
        "eerste_ontvangen": ontvangen[0] if ontvangen else None,
        "laatste_klaar": klaar_tijden[-1] if klaar_tijden else None,
        "looptijd": _sec(ontvangen[0], klaar_tijden[-1]) if ontvangen and klaar_tijden else None,
        "storingen": storingen,
        "wacht": _stat([r["_wacht"] for r in regels]),
        "accept": _stat([r["_accept"] for r in regels]),
        "rit": _stat([r["_rit"] for r in regels]),
        "totaal": _stat([r["_totaal"] for r in regels]),
        "eerst_klaar": met_klaar[:10], "laatst_klaar": list(reversed(met_klaar[-10:])),
        "langzaamst": sorted([s for s in stembureaus if s["rit"] is not None], key=lambda s: -s["rit"])[:10],
        "snelst": sorted([s for s in stembureaus if s["rit"] is not None], key=lambda s: s["rit"])[:10],
        "nog_open": sorted(open_, key=lambda s: s["nummer"]),
        "alle_stembureaus": sorted(stembureaus, key=lambda s: s["nummer"]),
        "per_route": per_route, "per_uur": uren,
    }
