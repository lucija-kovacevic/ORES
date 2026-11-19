"""
Zajedničko spremište na serveru (JSON datoteka u mapi podaci/).

Svi studenti spajaju se na istu aplikaciju, pa se predane ponude, postavke
scenarija i status objave rezultata čuvaju ovdje, a ne u pregledniku.
"""
import json
import os
import threading
from datetime import datetime
from pathlib import Path

import pandas as pd

import postavke as P
import trziste as T

MAPA = Path(__file__).parent / "podaci"
DATOTEKA = MAPA / "stanje.json"
_LOCK = threading.Lock()


def _prazno():
    return {
        "postavke": {
            "trosak": P.TROSAK,
            "potraznja": P.POTRAZNJA,
            "kapacitet": P.KAPACITET,
        },
        "ponude": {s: {} for s in P.SCENARIJI},          # scenarij -> tim -> {"ponuda": [[...]], "vrijeme": str}
        "objavljeno": {s: False for s in P.SCENARIJI},  # smiju li studenti vidjeti rezultate
        "zakljucano": {s: False for s in P.SCENARIJI},  # je li predaja ponuda zatvorena
    }


def _citaj():
    if not DATOTEKA.exists():
        return _prazno()
    with open(DATOTEKA, encoding="utf-8") as f:
        st = json.load(f)
    baza = _prazno()
    for k, v in baza.items():           # dopuni ako nešto nedostaje (npr. novi scenarij)
        if k not in st:
            st[k] = v
        elif isinstance(v, dict):
            for kk, vv in v.items():
                st[k].setdefault(kk, vv)
    return st


def _pisi(st):
    MAPA.mkdir(exist_ok=True)
    tmp = DATOTEKA.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DATOTEKA)


def stanje():
    with _LOCK:
        return _citaj()


def izmijeni(fn):
    """Atomarna izmjena: fn(stanje) mijenja rječnik na mjestu."""
    with _LOCK:
        st = _citaj()
        fn(st)
        _pisi(st)


# --- pomoćne funkcije --------------------------------------------------------
def predaj_ponudu(scen, tim, df: pd.DataFrame):
    def f(st):
        st["ponude"][scen][tim] = {
            "ponuda": df[T.stupci_ponude(P.BROJ_PONUDA)].astype(float).values.tolist(),
            "vrijeme": datetime.now().strftime("%d.%m.%Y. %H:%M:%S"),
        }
    izmijeni(f)


def predane_ponude(st, scen) -> dict[str, pd.DataFrame]:
    return {tim: T.ponuda_iz_liste(v["ponuda"], P.BROJ_PONUDA)
            for tim, v in sorted(st["ponude"][scen].items())}


def postavke_df(st):
    p = st["postavke"]
    trosak = pd.DataFrame(p["trosak"]).T.loc[P.SCENARIJI, P.ELEKTRANE].astype(float)
    potraznja = pd.DataFrame(p["potraznja"], index=pd.Index(range(1, 25), name="Sat"))[P.SCENARIJI].astype(float)
    kapacitet = {e: float(p["kapacitet"][e]) for e in P.ELEKTRANE}
    return trosak, potraznja, kapacitet


def spremi_postavke(trosak: pd.DataFrame, potraznja: pd.DataFrame, kapacitet: dict):
    def f(st):
        st["postavke"] = {
            "trosak": {s: {e: float(trosak.loc[s, e]) for e in P.ELEKTRANE} for s in P.SCENARIJI},
            "potraznja": {s: [float(x) for x in potraznja[s]] for s in P.SCENARIJI},
            "kapacitet": {e: float(kapacitet[e]) for e in P.ELEKTRANE},
        }
    izmijeni(f)
