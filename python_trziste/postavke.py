"""
Postavke vježbe - OVDJE nastavnik mijenja podatke scenarija.

Sve se ovo može mijenjati i u samoj aplikaciji (kartica "Postavke scenarija"),
ali vrijednosti ovdje su početne (default) vrijednosti.
"""

ELEKTRANE = ["A", "B", "C", "D"]   # timovi / elektrane

# Pristup preko weba: svaki tim dobiva svoj kod (da ne može mijenjati tuđe ponude),
# a nastavnik lozinku. PROMIJENITE PRIJE NASTAVE!
KODOVI_TIMOVA = {"A": "sunce", "B": "vjetar", "C": "voda", "D": "plin"}
LOZINKA_NASTAVNIKA = "ores2026"

# Vide li studenti troškove konkurentskih elektrana (False = vide samo svoj trošak)
PRIKAZI_TUDE_TROSKOVE = False
BROJ_PONUDA = 3                     # broj blokova ponude po satu (b = 1..3)
SATI = [f"t{h}" for h in range(1, 25)]

# Ukupni kapacitet svake elektrane [MW] - zbroj količina u 3 ponude mora biti jednak ovome
KAPACITET = {"A": 350, "B": 350, "C": 350, "D": 350}

SCENARIJI = ["Scenarij 1", "Scenarij 2", "Scenarij 3"]

# Varijabilni (operativni) trošak elektrane [EUR/MWh] po scenariju.
# Preuzeto iz predloška "A_Scenarij 1.xlsx" (stupci "Trošak scenarij 1/2/3").
# Ako elektrane B, C, D imaju drugačije troškove, promijenite ih ovdje.
TROSAK = {
    "Scenarij 1": {"A": 45.0, "B": 45.0, "C": 45.0, "D": 45.0},
    "Scenarij 2": {"A": 55.0, "B": 55.0, "C": 55.0, "D": 55.0},
    "Scenarij 3": {"A": 60.0, "B": 60.0, "C": 60.0, "D": 60.0},
}

# Potražnja [MWh] po satu t1..t24 za svaki scenarij (iz predloška "Demand sc 1/2/3").
POTRAZNJA = {
    "Scenarij 1": [140, 128, 117, 117, 128, 151, 186, 221, 233, 221, 210, 198,
                   210, 233, 256, 280, 291, 280, 256, 233, 210, 186, 163, 151],
    "Scenarij 2": [210, 192, 175, 175, 192, 227, 280, 332, 350, 332, 315, 297,
                   315, 350, 384, 419, 437, 419, 384, 350, 315, 280, 245, 227],
    "Scenarij 3": [419, 384, 350, 350, 384, 454, 559, 664, 699, 664, 629, 594,
                   629, 699, 769, 839, 874, 839, 769, 699, 629, 559, 489, 454],
}

# Primjer ponude iz predloška (tim A, scenarij 1) - koristi se kao početna ponuda
# za sve timove, da aplikacija odmah ima nešto za prikazati.
# Format po satu: (cijena1, kol1, cijena2, kol2, cijena3, kol3)
_P1 = [62] * 16 + [70, 65, 68, 71] + [62] * 4
_P2 = [85] * 16 + [95] * 5 + [85] * 3
_P3 = [140] * 16 + [180] * 4 + [140] * 4
PRIMJER_PONUDE = [(_P1[h], 150, _P2[h], 75, _P3[h], 125) for h in range(24)]

# Ono što studenti vide kad otvore praznu tablicu: samo sat 1 popunjen kao primjer.
POCETNA_TABLICA = [PRIMJER_PONUDE[0]] + [(None,) * 6] * 23
