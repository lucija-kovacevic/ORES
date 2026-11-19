"""
Jezgra vježbe: čišćenje dan-unaprijed tržišta električne energije.

Python prijevod GAMS modela ("gams kod.txt"):

    min  sum_{i,b,t} gen(i,b,t) * price(i,b,t)
    s.t. sum_{i,b} gen(i,b,t) = demand(t)          (balance, dual = MCP)
         0 <= gen(i,b,t) <= capacity(i,b,t)

Budući da nema mreže ni međuvremenskih ograničenja, svaki sat je zaseban LP
čije je optimalno rješenje upravo merit-order: ponude se slažu od najjeftinije
prema najskupljoj dok se ne pokrije potražnja. Cijena (MCP, dual bilance) je
cijena posljednje (marginalne) prihvaćene ponude. Zato ovdje nije potreban
LP solver - rezultat je isti kao iz GAMS-a, a kod je jednostavan za čitanje.

Razlika od GAMS-a samo u rubnim slučajevima:
  * ako više ponuda ima ISTU marginalnu cijenu, GAMS/CPLEX proizvoljno odabere
    jednu; ovdje se preostala količina dijeli proporcionalno (pro-rata).
  * ako potražnja točno "pogodi" kraj jednog bloka, dual nije jednoznačan;
    ovdje se uzima cijena tog posljednjeg prihvaćenog bloka.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pandas as pd

EPS = 1e-9


# ---------------------------------------------------------------------------
# Format ponude jednog tima: tablica 24 x (Cijena 1, Količina 1, ..., Količina 3)
# ---------------------------------------------------------------------------
def stupci_ponude(broj_ponuda: int = 3) -> list[str]:
    cols = []
    for b in range(1, broj_ponuda + 1):
        cols += [f"Cijena {b}", f"Količina {b}"]
    return cols


def ponuda_iz_liste(redovi, broj_ponuda: int = 3) -> pd.DataFrame:
    df = pd.DataFrame(redovi, columns=stupci_ponude(broj_ponuda), dtype=float)
    df.index = range(1, len(df) + 1)
    df.index.name = "Sat"
    return df


def _rasponi(sati) -> str:
    """[2,3,4,7,9,10] -> '2–4, 7, 9–10'"""
    sati, dijelovi, i = sorted(int(s) for s in sati), [], 0
    while i < len(sati):
        j = i
        while j + 1 < len(sati) and sati[j + 1] == sati[j] + 1:
            j += 1
        dijelovi.append(f"{sati[i]}" if i == j else f"{sati[i]}–{sati[j]}")
        i = j + 1
    return ", ".join(dijelovi)


def provjeri_ponudu(df: pd.DataFrame, kapacitet: float, broj_ponuda: int = 3):
    """Vraća (greske, upozorenja) kao liste tekstova."""
    greske, upozorenja = [], []
    kol = df[[f"Količina {b}" for b in range(1, broj_ponuda + 1)]]
    cij = df[[f"Cijena {b}" for b in range(1, broj_ponuda + 1)]]
    prazni = df.isna().any(axis=1)
    if prazni.any():
        greske.append(f"Nepopunjeni sati: {_rasponi(df.index[prazni])}")
    if (kol.fillna(0) < 0).any().any():
        greske.append("Količine ne smiju biti negativne.")
    zbroj = kol[~prazni].sum(axis=1)
    previse = zbroj[zbroj > kapacitet + 1e-6]
    premalo = zbroj[zbroj < kapacitet - 1e-6]
    if len(previse):
        greske.append(
            f"Zbroj količina veći od kapaciteta ({kapacitet:g} MW) u satima: "
            + ", ".join(f"{s} ({v:g})" for s, v in previse.items())
        )
    if len(premalo):
        upozorenja.append(
            f"Zbroj količina manji od kapaciteta ({kapacitet:g} MW) u satima: "
            + ", ".join(f"{s} ({v:g})" for s, v in premalo.items())
            + " - ostatak kapaciteta se ne nudi na tržištu."
        )
    if (cij.fillna(0) < 0).any().any():
        upozorenja.append("Neke cijene su negativne.")
    return greske, upozorenja


# ---------------------------------------------------------------------------
# Čišćenje tržišta
# ---------------------------------------------------------------------------
@dataclass
class Rezultati:
    satni: pd.DataFrame        # Sat, Potražnja, MCP, proizvodnja po elektrani
    ponude: pd.DataFrame       # sve ponude + prihvaćena količina
    sazetak: pd.DataFrame      # po elektrani: energija, prihod, trošak, profit
    nepokriveno: dict          # sat -> nepokrivena potražnja [MWh]


def ponude_u_dugi_format(ponude: dict[str, pd.DataFrame], broj_ponuda: int = 3) -> pd.DataFrame:
    redovi = []
    for el, df in ponude.items():
        for sat, r in df.iterrows():
            for b in range(1, broj_ponuda + 1):
                redovi.append({
                    "Elektrana": el, "Sat": int(sat), "Blok": b,
                    "Cijena": float(r[f"Cijena {b}"]),
                    "Količina": float(r[f"Količina {b}"]),
                })
    return pd.DataFrame(redovi)


def ocisti_trziste(ponude: dict[str, pd.DataFrame], potraznja: list[float],
                   trosak: dict[str, float], broj_ponuda: int = 3) -> Rezultati:
    elektrane = list(ponude)
    duge = ponude_u_dugi_format(ponude, broj_ponuda)
    duge["Prihvaćeno"] = 0.0

    satni, nepokriveno = [], {}
    for sat, d in enumerate(potraznja, start=1):
        maska = (duge["Sat"] == sat) & (duge["Količina"] > EPS)
        ps = duge[maska].sort_values("Cijena", kind="stable")
        ostatak, mcp = float(d), None
        for cijena, grupa in ps.groupby("Cijena", sort=True):
            if ostatak <= EPS:
                break
            q = grupa["Količina"].sum()
            udio = 1.0 if q <= ostatak + EPS else ostatak / q
            duge.loc[grupa.index, "Prihvaćeno"] = grupa["Količina"] * udio
            ostatak -= min(q, ostatak)
            mcp = float(cijena)
        if ostatak > 1e-6:
            nepokriveno[sat] = ostatak
        red = {"Sat": sat, "Potražnja": float(d), "MCP": mcp if mcp is not None else 0.0}
        for el in elektrane:
            red[el] = duge.loc[(duge["Sat"] == sat) & (duge["Elektrana"] == el), "Prihvaćeno"].sum()
        satni.append(red)

    satni = pd.DataFrame(satni)
    sazetak = []
    for el in elektrane:
        energija = satni[el].sum()
        prihod = (satni[el] * satni["MCP"]).sum()
        tros = energija * trosak[el]
        sazetak.append({
            "Elektrana": el,
            "Energija [MWh]": energija,
            "Prihod [EUR]": prihod,
            "Trošak [EUR]": tros,
            "Profit [EUR]": prihod - tros,
            "Prosj. cijena [EUR/MWh]": prihod / energija if energija > EPS else 0.0,
        })
    return Rezultati(satni, duge, pd.DataFrame(sazetak), nepokriveno)


def krivulja_ponude(ponude_dugo: pd.DataFrame, sat: int) -> pd.DataFrame:
    """Merit-order za jedan sat: ponude sortirane po cijeni, s kumulativnom količinom."""
    p = ponude_dugo[(ponude_dugo["Sat"] == sat) & (ponude_dugo["Količina"] > EPS)]
    p = p.sort_values(["Cijena", "Elektrana", "Blok"]).copy()
    p["Do"] = p["Količina"].cumsum()
    p["Od"] = p["Do"] - p["Količina"]
    return p


# ---------------------------------------------------------------------------
# Excel ulaz / izlaz
# ---------------------------------------------------------------------------
_RE_CIJENA = re.compile(r"(?:^|_)(?:price|cijena|cij)\s*_?\s*(\d)$", re.I)
_RE_KOL = re.compile(r"(?:^|_)(?:cap|kol|kolicina|količina|kapacitet|qty)\s*_?\s*(\d)$", re.I)
_RE_TIM = re.compile(r"^([A-Za-z])_(?:price|cap|cost)", re.I)


def citaj_ponudu_excel(datoteka, broj_ponuda: int = 3, broj_sati: int = 24):
    """Čita ponudu iz Excela/CSV-a u formatu predloška (time, A_price1, A_cap1, ...).

    Prihvaća i stupce 'Cijena 1', 'Količina 1' (format koji izvozi aplikacija).
    Vraća (DataFrame ponude, slovo tima ili None).
    """
    ime = getattr(datoteka, "name", str(datoteka)).lower()
    raw = pd.read_csv(datoteka) if ime.endswith(".csv") else pd.read_excel(datoteka, sheet_name=0)
    mapa, tim = {}, None
    for c in raw.columns:
        s = str(c).strip()
        if (m := _RE_CIJENA.search(s)):
            mapa[f"Cijena {m.group(1)}"] = c
        elif (m := _RE_KOL.search(s)):
            mapa[f"Količina {m.group(1)}"] = c
        if tim is None and (m := _RE_TIM.match(s)):
            tim = m.group(1).upper()
    potrebno = stupci_ponude(broj_ponuda)
    nedostaje = [c for c in potrebno if c not in mapa]
    if nedostaje:
        raise ValueError(
            "U datoteci nedostaju stupci: " + ", ".join(nedostaje)
            + ". Očekuje se format predloška (npr. A_price1, A_cap1, ...)."
        )
    df = raw[[mapa[c] for c in potrebno]].copy()
    df.columns = potrebno
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna(how="all").head(broj_sati)
    if len(df) < broj_sati:
        raise ValueError(f"Datoteka ima samo {len(df)} sati s podacima (treba {broj_sati}).")
    df.index = range(1, broj_sati + 1)
    df.index.name = "Sat"
    return df, tim


def predlozak_excel(tim: str, ponuda: pd.DataFrame, kapacitet: float,
                    trosak: float, potraznja: list[float], scenarij: str,
                    broj_ponuda: int = 3) -> bytes:
    """Excel predložak za studente, u istom formatu kao originalni 'A_Scenarij 1.xlsx'."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "ponuda"
    zaglavlje = ["time"]
    for b in range(1, broj_ponuda + 1):
        zaglavlje += [f"{tim}_price{b}", f"{tim}_cap{b}"]
    zaglavlje += [f"Provjera ({kapacitet:g} - zbroj kol.)", "", "Trošak [EUR/MWh]", "Potražnja [MWh]"]
    ws.append(zaglavlje)
    for c in ws[1]:
        c.font = Font(bold=True)
    zuto = PatternFill("solid", fgColor="FFF2CC")
    kol_stupci = [chr(ord("C") + 2 * k) for k in range(broj_ponuda)]
    prov = chr(ord("B") + 2 * broj_ponuda)
    for i, (sat, r) in enumerate(ponuda.iterrows(), start=2):
        red = [f"t{sat}"]
        for b in range(1, broj_ponuda + 1):
            red += [None if pd.isna(r[k]) else float(r[k]) for k in (f"Cijena {b}", f"Količina {b}")]
        red += [f"={kapacitet:g}-" + "-".join(f"{k}{i}" for k in kol_stupci), None,
                float(trosak), float(potraznja[sat - 1])]
        ws.append(red)
        for col in range(2, 2 + 2 * broj_ponuda):
            ws.cell(row=i, column=col).fill = zuto
    ws.column_dimensions[prov].width = 24
    ws.column_dimensions[chr(ord(prov) + 2)].width = 18
    ws.column_dimensions[chr(ord(prov) + 3)].width = 18
    ws.cell(row=27, column=1, value=(
        f"{scenarij}: upišite cijene [EUR/MWh] i količine [MW] u žuta polja. "
        f"Stupac 'Provjera' mora biti 0 (zbroj količina = {kapacitet:g} MW)."))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def rezultati_excel(rez: Rezultati, scenarij: str) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        rez.sazetak.round(2).to_excel(w, sheet_name="Sazetak", index=False)
        rez.satni.round(3).to_excel(w, sheet_name="Po satu", index=False)
        rez.ponude.round(3).to_excel(w, sheet_name="Ponude", index=False)
        pd.DataFrame({"Scenarij": [scenarij]}).to_excel(w, sheet_name="Info", index=False)
        for ws in w.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = max(
                    10, min(28, max(len(str(c.value or "")) for c in col) + 2))
    return buf.getvalue()
