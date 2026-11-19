"""
Arhiviranje vježbe: sprema predane ponude i rezultate u novu mapu arhiva/<datum_vrijeme>/.
Podatke web-aplikacije samo čita (ništa ne mijenja). Pokretanje:

    ..\\python_trziste\\.venv\\Scripts\\python.exe arhiviraj.py
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

OVDJE = Path(__file__).parent
APP = OVDJE.parent / "python_trziste"
sys.path.insert(0, str(APP))
import trziste as T  # noqa: E402

izvor = APP / "podaci" / "stanje.json"
with open(izvor, encoding="utf-8") as f:
    st = json.load(f)

mapa = OVDJE / datetime.now().strftime("%Y-%m-%d_%H-%M")
mapa.mkdir(parents=True, exist_ok=True)
shutil.copy2(izvor, mapa / "stanje.json")          # sirova kopija (može se vratiti u aplikaciju)

post = st["postavke"]
sazetak_svi, predaje = [], []
with pd.ExcelWriter(mapa / "ponude_i_rezultati.xlsx", engine="openpyxl") as w:
    # postavke
    pd.DataFrame(post["trosak"]).T.to_excel(w, sheet_name="Troskovi")
    pd.DataFrame(post["potraznja"], index=[f"t{h}" for h in range(1, 25)]).to_excel(w, sheet_name="Potraznja")

    for sc, pon in st["ponude"].items():
        if not pon:
            continue
        kratko = sc.replace("Scenarij ", "S")
        ponude = {t: T.ponuda_iz_liste(v["ponuda"]) for t, v in sorted(pon.items())}
        for t, v in sorted(pon.items()):
            predaje.append({"Scenarij": sc, "Tim": t, "Vrijeme predaje": v["vrijeme"]})

        # ponude (GAMS format) -> Excel list + CSV
        gams = pd.DataFrame({"time": [f"t{h}" for h in range(1, 25)]})
        for t, df in ponude.items():
            for b in (1, 2, 3):
                gams[f"{t}_price{b}"] = df[f"Cijena {b}"].values
                gams[f"{t}_cap{b}"] = df[f"Količina {b}"].values
            gams[f"{t}_cost"] = post["trosak"][sc][t]
        gams["demand"] = post["potraznja"][sc]
        gams.to_excel(w, sheet_name=f"{kratko} ponude", index=False)
        gams.to_csv(mapa / f"market_input_with_bids_{sc.replace(' ', '_')}.csv", index=False)

        # rezultati (isti izračun kao u aplikaciji)
        rez = T.ocisti_trziste(ponude, post["potraznja"][sc], post["trosak"][sc])
        rez.satni.round(3).to_excel(w, sheet_name=f"{kratko} po satu", index=False)
        rez.sazetak.round(2).to_excel(w, sheet_name=f"{kratko} sazetak", index=False)
        sazetak_svi.append(rez.sazetak.set_index("Elektrana")["Profit [EUR]"].rename(sc))

    if sazetak_svi:
        uk = pd.concat(sazetak_svi, axis=1).fillna(0)
        uk["Ukupno"] = uk.sum(axis=1)
        uk.sort_values("Ukupno", ascending=False).round(2).to_excel(w, sheet_name="Ukupni profit")
    pd.DataFrame(predaje).to_excel(w, sheet_name="Predaje", index=False)

    for ws in w.book.worksheets:
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = max(
                9, min(26, max(len(str(c.value or "")) for c in col) + 2))

print(f"Arhivirano u: {mapa}")
for p in sorted(mapa.iterdir()):
    print("  ", p.name)
