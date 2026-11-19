# LP model tržišta – 1:1 s GAMS kodom

`market_lp.py` je doslovni prijevod `gams kod.txt` u Python: **Pyomo** za modeliranje
(Set, Param, Var, Constraint – kao GAMS) i **HiGHS** kao LP solver. Svaki blok koda
ima komentar `GAMS:` s odgovarajućom linijom iz originala.

| GAMS | Python (Pyomo) |
|---|---|
| `Sets t, i, b` | `m.t, m.i, m.b = pyo.Set(...)` |
| `Table raw(t,*) $include market_input_with_bids.csv` | `pd.read_csv(...)` |
| `price(i,b,t), capacity(i,b,t), cost(i,t), demand(t)` | `pyo.Param(...)` |
| `Positive Variables gen(i,b,t)` | `pyo.Var(..., within=NonNegativeReals)` |
| `obj, balance(t), cap_limit(i,b,t)` | `pyo.Constraint(...)` |
| `Solve market using LP minimizing total_cost` | `SolverFactory("appsi_highs").solve(m)` |
| `mcp(t) = balance.m(t)` | `m.dual[m.balance[t]]` |
| `display total_profit, ...` | ispis u terminalu |
| `execute_unload` + `gdxxrw` → `results.xlsx` | `results_*.xlsx` (Summary, Hourly) |

Ima vlastito Python okruženje (`.venv`), potpuno odvojeno od web-aplikacije.

## Pokretanje (u ovoj mapi)

Iz CSV-a, isto kao GAMS (CSV se preuzima u aplikaciji: Nastavnik → 📋 Predaje →
"Sve ponude u GAMS formatu"):

```
.venv\Scripts\python.exe market_lp.py market_input_with_bids.csv
```

Izravno iz predanih ponuda u web-aplikaciji (podaci se samo čitaju):

```
.venv\Scripts\python.exe market_lp.py --scenarij 1
.venv\Scripts\python.exe market_lp.py --scenarij 1 --usporedi
```

`--usporedi` ispisuje razliku prema merit-order izračunu web-aplikacije.

## Odnos prema web-aplikaciji

Web-aplikacija ne koristi solver nego merit order, jer je to analitičko rješenje istog LP-a.
Cijene (MCP) su identične. Razlika se može pojaviti samo u **raspodjeli proizvodnje kad dvije
ponude imaju istu cijenu na margini**: LP (i GAMS) proizvoljno odabere jednu, a aplikacija
dijeli proporcionalno. Ni HiGHS i CPLEX ne moraju u tom slučaju odabrati istu ponudu.
