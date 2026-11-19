"""
Skupni izračun bez web-sučelja (za nastavnika).

Stavite Excel datoteke s ponudama timova u jednu mapu (npr. ponude/), u formatu
predloška: stupci time, A_price1, A_cap1, A_price2, ... (tim se prepoznaje po
prefiksu stupaca ili po prvom slovu imena datoteke), pa pokrenite:

    python izracun.py ponude --scenarij 1

Rezultat: rezultati_Scenarij_1.xlsx i grafovi_Scenarij_1.html (otvara se u pregledniku).
"""
import argparse
import sys
from pathlib import Path

import grafovi as G
import postavke as P
import trziste as T


def main():
    ap = argparse.ArgumentParser(description="ORES - čišćenje tržišta iz Excel ponuda timova")
    ap.add_argument("mapa", help="mapa s .xlsx/.csv ponudama timova")
    ap.add_argument("--scenarij", type=int, default=1, choices=range(1, len(P.SCENARIJI) + 1))
    ap.add_argument("--izlaz", default=".", help="mapa za rezultate (zadano: trenutna)")
    a = ap.parse_args()

    scen = P.SCENARIJI[a.scenarij - 1]
    ponude, ok = {}, True
    for f in sorted(Path(a.mapa).iterdir()):
        if f.suffix.lower() not in (".xlsx", ".xls", ".csv") or f.name.startswith("~$"):
            continue
        df, tim = T.citaj_ponudu_excel(f, P.BROJ_PONUDA)
        tim = tim or f.stem[0].upper()
        if tim not in P.ELEKTRANE:
            print(f"  ! {f.name}: nepoznat tim '{tim}', preskačem")
            continue
        if tim in ponude:
            print(f"  ! {f.name}: tim {tim} već učitan, preskačem")
            continue
        greske, upoz = T.provjeri_ponudu(df, P.KAPACITET[tim], P.BROJ_PONUDA)
        print(f"  {tim} <- {f.name}")
        for u in upoz:
            print(f"      upozorenje: {u}")
        for g in greske:
            print(f"      GREŠKA: {g}")
            ok = False
        ponude[tim] = df

    nedostaju = [e for e in P.ELEKTRANE if e not in ponude]
    if nedostaju:
        print("Nedostaju ponude za: " + ", ".join(nedostaju))
        ok = False
    if not ok:
        sys.exit(1)

    ponude = {e: ponude[e] for e in P.ELEKTRANE}
    rez = T.ocisti_trziste(ponude, P.POTRAZNJA[scen], P.TROSAK[scen], P.BROJ_PONUDA)
    if rez.nepokriveno:
        print("UPOZORENJE - nepokrivena potražnja:", rez.nepokriveno)

    izlaz = Path(a.izlaz)
    izlaz.mkdir(parents=True, exist_ok=True)
    ime = scen.replace(" ", "_")
    (izlaz / f"rezultati_{ime}.xlsx").write_bytes(T.rezultati_excel(rez, scen))

    s = rez.satni
    vrh = int(s["Potražnja"].idxmax()) + 1
    figs = [G.cijena_po_satu(s), G.proizvodnja_po_satu(s, P.ELEKTRANE),
            G.profit_po_elektrani(rez.sazetak), G.krivulja_ponude(rez, vrh, P.ELEKTRANE)]
    html = [f"<html><head><meta charset='utf-8'><title>ORES {scen}</title></head>"
            f"<body style='font-family:system-ui,Segoe UI,sans-serif;max-width:1100px;margin:auto'>"
            f"<h2>ORES – rezultati tržišta, {scen}</h2>",
            rez.sazetak.round(0).to_html(index=False)]
    for i, f in enumerate(figs):
        html.append(f.to_html(full_html=False, include_plotlyjs="cdn" if i == 0 else False))
    html.append("</body></html>")
    (izlaz / f"grafovi_{ime}.html").write_text("\n".join(html), encoding="utf-8")

    print()
    print(rez.sazetak.round(1).to_string(index=False))
    print(f"\nSpremljeno: {izlaz / f'rezultati_{ime}.xlsx'}, {izlaz / f'grafovi_{ime}.html'}")


if __name__ == "__main__":
    main()
