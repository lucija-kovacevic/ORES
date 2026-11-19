"""
ORES - tržište električne energije: LP model 1:1 prema GAMS kodu ("gams kod.txt").

Pyomo (modeliranje, kao GAMS) + HiGHS (LP solver, kao CPLEX/CONOPT u GAMS-u).
Svaki blok GAMS koda ima svoj odgovarajući blok ovdje, označen komentarom "GAMS:".

Pokretanje (iz mape optimizacija_lp):

  1) isto kao GAMS - iz CSV datoteke s ponudama:
       .venv\\Scripts\\python.exe market_lp.py market_input_with_bids.csv

  2) izravno iz web-aplikacije (podaci se samo ČITAJU, aplikacija se ne dira):
       .venv\\Scripts\\python.exe market_lp.py --scenarij 1

  dodatno:  --usporedi   usporedi rezultat s merit-order izračunom iz aplikacije
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import pyomo.environ as pyo

OVDJE = Path(__file__).parent
APLIKACIJA = OVDJE.parent / "python_trziste"


# =============================================================================
# Ulazni podaci  ->  tablica raw(t, *) u istom formatu kao market_input_with_bids.csv
# =============================================================================
def raw_iz_csv(putanja) -> pd.DataFrame:
    # GAMS:  Table raw(t,*)  $ondelim  $include market_input_with_bids.csv  $offdelim
    raw = pd.read_csv(putanja, index_col=0)
    raw.index = raw.index.astype(str).str.strip()
    raw.columns = raw.columns.str.strip()
    return raw


def raw_iz_aplikacije(scen_br: int) -> pd.DataFrame:
    """Složi raw tablicu iz podaci/stanje.json web-aplikacije (samo čitanje)."""
    datoteka = APLIKACIJA / "podaci" / "stanje.json"
    with open(datoteka, encoding="utf-8") as f:
        stanje = json.load(f)
    scen = f"Scenarij {scen_br}"
    ponude = stanje["ponude"][scen]
    if not ponude:
        sys.exit(f"Za {scen} nema predanih ponuda.")
    post = stanje["postavke"]
    raw = pd.DataFrame(index=[f"t{h}" for h in range(1, 25)])
    for i in sorted(ponude):
        p = ponude[i]["ponuda"]                      # 24 x [c1, k1, c2, k2, c3, k3]
        for b in range(1, 4):
            raw[f"{i}_price{b}"] = [r[2 * (b - 1)] for r in p]
            raw[f"{i}_cap{b}"] = [r[2 * (b - 1) + 1] for r in p]
        raw[f"{i}_cost"] = post["trosak"][scen][i]
    raw["demand"] = post["potraznja"][scen]
    return raw


# =============================================================================
# Model
# =============================================================================
def izgradi_model(raw: pd.DataFrame) -> pyo.ConcreteModel:
    m = pyo.ConcreteModel("market")

    # GAMS:  Sets  t /t1*t24/,  i /A, B, C, D/,  b /1*3/;
    m.t = pyo.Set(initialize=list(raw.index), ordered=True)
    m.i = pyo.Set(initialize=["A", "B", "C", "D"], ordered=True)
    m.b = pyo.Set(initialize=["1", "2", "3"], ordered=True)

    # GAMS:  "Manual column mapping"  price('A','1',t) = raw(t,'A_price1'); ...
    #        (stupac koji ne postoji u GAMS-u ima vrijednost 0)
    def kol(t, ime):
        return float(raw.at[t, ime]) if ime in raw.columns else 0.0

    # GAMS:  Parameters price(i,b,t), capacity(i,b,t), cost(i,t), demand(t);
    m.price = pyo.Param(m.i, m.b, m.t, initialize=lambda m, i, b, t: kol(t, f"{i}_price{b}"))
    m.capacity = pyo.Param(m.i, m.b, m.t, initialize=lambda m, i, b, t: kol(t, f"{i}_cap{b}"))
    m.cost = pyo.Param(m.i, m.t, initialize=lambda m, i, t: kol(t, f"{i}_cost"))
    m.demand = pyo.Param(m.t, initialize=lambda m, t: kol(t, "demand"))

    # GAMS:  Positive Variables gen(i,b,t);   Variable total_cost;
    m.gen = pyo.Var(m.i, m.b, m.t, within=pyo.NonNegativeReals)
    m.total_cost = pyo.Var(within=pyo.Reals)

    # GAMS:  obj..  total_cost =e= sum((i,b,t), gen(i,b,t) * price(i,b,t));
    m.obj = pyo.Constraint(expr=m.total_cost == sum(m.gen[i, b, t] * m.price[i, b, t]
                                                    for i in m.i for b in m.b for t in m.t))

    # GAMS:  balance(t)..  sum((i,b), gen(i,b,t)) =e= demand(t);
    m.balance = pyo.Constraint(m.t, rule=lambda m, t: sum(m.gen[i, b, t] for i in m.i for b in m.b)
                               == m.demand[t])

    # GAMS:  cap_limit(i,b,t)..  gen(i,b,t) =l= capacity(i,b,t);
    m.cap_limit = pyo.Constraint(m.i, m.b, m.t, rule=lambda m, i, b, t: m.gen[i, b, t] <= m.capacity[i, b, t])

    # GAMS:  Model market /all/;  Solve market using LP minimizing total_cost;
    m.cilj = pyo.Objective(expr=m.total_cost, sense=pyo.minimize)

    # GAMS sprema marginale (.m) automatski; u Pyomu se traže preko "dual" sufiksa
    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    return m


def rijesi(m):
    solver = pyo.SolverFactory("appsi_highs")
    rez = solver.solve(m, load_solutions=True)
    status = rez.solver.termination_condition
    if status != pyo.TerminationCondition.optimal:
        sys.exit(f"Model nije riješen optimalno: {status} (GAMS bi javio 'infeasible' ako ponuda ne pokriva potražnju)")
    return rez


# =============================================================================
# Rezultati - isti parametri kao u GAMS-u
# =============================================================================
def rezultati(m):
    T, I = list(m.t), list(m.i)
    # GAMS:  gen_sum(i,t) = sum(b, gen.l(i,b,t));
    gen_sum = pd.DataFrame({i: [sum(pyo.value(m.gen[i, b, t]) for b in m.b) for t in T] for i in I}, index=T)
    # GAMS:  mcp(t) = balance.m(t);
    mcp = pd.Series([m.dual[m.balance[t]] for t in T], index=T)
    # GAMS:  revenue(i,t) = mcp(t) * gen_sum(i,t);   operational_cost(i,t) = cost(i,t) * gen_sum(i,t);
    revenue = gen_sum.mul(mcp, axis=0)
    cost = pd.DataFrame({i: [pyo.value(m.cost[i, t]) for t in T] for i in I}, index=T)
    operational_cost = cost * gen_sum
    # GAMS:  total_rev_i(i), total_cost_i(i), total_profit(i), energy_total(i)
    total_rev_i = revenue.sum()
    total_cost_i = operational_cost.sum()
    total_profit = total_rev_i - total_cost_i
    energy_total = gen_sum.sum()
    # GAMS:  hourly_summary(t,'Hour'|'A_MWh'..'D_MWh'|'Demand'|'MCP_EUR')
    hourly_summary = pd.DataFrame({"Hour": range(1, len(T) + 1)}, index=T)
    for i in I:
        hourly_summary[f"{i}_MWh"] = gen_sum[i]
    hourly_summary["Demand"] = [pyo.value(m.demand[t]) for t in T]
    hourly_summary["MCP_EUR"] = mcp
    return dict(gen_sum=gen_sum, mcp=mcp, total_profit=total_profit, energy_total=energy_total,
                total_rev_i=total_rev_i, total_cost_i=total_cost_i, hourly_summary=hourly_summary,
                objective=pyo.value(m.total_cost))


def display(ime, s: pd.Series):
    """GAMS:  display total_profit, energy_total, total_rev_i, total_cost_i;"""
    print(f"\n----  PARAMETER {ime}\n")
    for k, v in s.items():
        print(f"{k:>4} {v:14,.3f}")


def izvoz_excel(r, putanja):
    """GAMS: execute_unload results.gdx + gdxxrw -> results.xlsx (Summary, Hourly)."""
    with pd.ExcelWriter(putanja, engine="openpyxl") as w:
        r["total_profit"].rename("total_profit").to_frame().to_excel(w, sheet_name="Summary", startrow=1, startcol=1)
        r["energy_total"].rename("energy_total").to_frame().to_excel(w, sheet_name="Summary", startrow=1, startcol=4)
        r["hourly_summary"].to_excel(w, sheet_name="Hourly", startrow=1)


def usporedi_s_aplikacijom(raw, r):
    sys.path.insert(0, str(APLIKACIJA))
    import trziste as T  # samo funkcija izračuna, ništa se ne zapisuje

    timovi = [i for i in "ABCD" if f"{i}_price1" in raw.columns]
    ponude = {}
    for i in timovi:
        df = pd.DataFrame({f"{x} {b}": raw[f"{i}_{y}{b}"].values for b in (1, 2, 3)
                           for x, y in (("Cijena", "price"), ("Količina", "cap"))})
        df.index = range(1, len(raw) + 1)
        ponude[i] = df
    app = T.ocisti_trziste(ponude, raw["demand"].tolist(), {i: float(raw[f"{i}_cost"].iloc[0]) for i in timovi})

    d_mcp = (app.satni["MCP"].values - r["mcp"].values)
    print("\n================ USPOREDBA: LP (GAMS način) vs. merit order (aplikacija) ================")
    print(f"MCP: najveća razlika po satu = {abs(d_mcp).max():.6f} €/MWh")
    tab = pd.DataFrame({"LP profit": r["total_profit"][timovi].values,
                        "Aplikacija profit": app.sazetak.set_index("Elektrana")["Profit [EUR]"][timovi].values},
                       index=timovi)
    tab["Razlika"] = tab["LP profit"] - tab["Aplikacija profit"]
    print(tab.round(2).to_string())
    razl = [f"t{h}" for h, x in enumerate(d_mcp, 1) if abs(x) > 1e-6]
    if razl:
        print("Sati s različitim MCP-om:", ", ".join(razl),
              "\n(potražnja točno na granici bloka -> dual nije jednoznačan, i GAMS može dati bilo koju od cijena)")
    if abs(tab["Razlika"]).max() > 1e-3 and not razl:
        print("Razlika u profitu bez razlike u MCP-u = iste cijene na margini; LP (i GAMS) proizvoljno bira koju "
              "ponudu prihvaća, aplikacija dijeli proporcionalno.")


def main():
    ap = argparse.ArgumentParser(description="ORES tržište - LP model 1:1 s GAMS-om (Pyomo + HiGHS)")
    ap.add_argument("csv", nargs="?", help="market_input_with_bids.csv (format kao za GAMS)")
    ap.add_argument("--scenarij", type=int, choices=[1, 2, 3], help="čitaj predane ponude iz web-aplikacije")
    ap.add_argument("--usporedi", action="store_true", help="usporedi s merit-order izračunom aplikacije")
    a = ap.parse_args()
    if not a.csv and not a.scenarij:
        ap.error("zadajte CSV datoteku ili --scenarij N")

    if a.scenarij:
        raw = raw_iz_aplikacije(a.scenarij)
        ime = f"Scenarij_{a.scenarij}"
        raw.to_csv(OVDJE / f"market_input_with_bids_{ime}.csv", index_label="time")
    else:
        raw = raw_iz_csv(a.csv)
        ime = Path(a.csv).stem

    m = izgradi_model(raw)
    rijesi(m)
    r = rezultati(m)

    print(f"\nSOLVE SUMMARY   MODEL market   TYPE LP   SOLVER HiGHS   OBJECTIVE total_cost = {r['objective']:,.4f}")
    for ime_p in ("total_profit", "energy_total", "total_rev_i", "total_cost_i"):
        display(ime_p, r[ime_p])
    print("\nhourly_summary:\n" + r["hourly_summary"].round(3).to_string())

    izlaz = OVDJE / f"results_{ime}.xlsx"
    izvoz_excel(r, izlaz)
    print(f"\nSpremljeno: {izlaz}")

    if a.usporedi:
        usporedi_s_aplikacijom(raw, r)


if __name__ == "__main__":
    main()
