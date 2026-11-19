# ORES – vježba tržišta električne energije (web aplikacija)

Python zamjena za GAMS model (`gams kod.txt`). Četiri tima (elektrane A–D) predaju
po 3 ponude (cijena + količina) za svaki od 24 sata, svaki sa svog laptopa.
Tržište se čisti po merit-orderu (isti rezultat kao LP u GAMS-u); cijena (MCP) je
cijena marginalne ponude. Za svaku elektranu računaju se energija, prihod, trošak i profit.

## Pokretanje (nastavnik)

1. **Prije nastave** promijenite kodove timova i lozinku u `postavke.py`
   (`KODOVI_TIMOVA`, `LOZINKA_NASTAVNIKA`).
2. Dvoklik na **`pokreni_aplikaciju.bat`**. Prozor ispiše adresu za studente,
   npr. `http://192.168.1.82:8501`. Prvi put Windows pita za vatrozid → **Dopusti**
   (barem za privatne mreže).
3. Studenti u **istoj mreži** otvore tu adresu u pregledniku. Instalacija im nije potrebna.

**Pristup s različitih mreža (preporučeno):** umjesto gornjeg, dvoklik na **`javni_link.bat`**.
Pokrene aplikaciju i javni link oblika `https://….trycloudflare.com` koji radi s bilo koje
mreže (eduroam, kućni internet, mobilni podaci). Link se ispiše krupno i automatski kopira.
Prozor mora ostati otvoren cijelo vrijeme; link je svaki put novi. (Preduvjet, jednom:
`winget install Cloudflare.cloudflared` – već instalirano.)

Python okruženje je u mapi `.venv` (Python 3.12 i paketi iz `requirements.txt`).
Ako mapa nedostaje, `.bat` je sam napravi.

## Tijek vježbe

| Tko | Što |
|---|---|
| Studenti | Prijava: odaberu tim i upišu kod tima. Na **📝 Moja ponuda** upišu ponude u tablicu (ili brzim unosom, ili iz Excela) pa kliknu **📤 PREDAJ PONUDU**. Do zatvaranja predaje mogu je mijenjati; vrijedi zadnja predana. Tuđe ponude ne vide. |
| Nastavnik | Prijava lozinkom. Na **📋 Predaje** vidi tko je predao (osvježava se samo), može **🔒 zatvoriti predaju** i **📢 objaviti rezultate**. Rezultate vidi uvijek. |
| Svi | Nakon objave na **📊 Rezultati** grafovi se izrade sami: cijena po satu, proizvodnja po satu, profit po elektrani i krivulja ponude za odabrani sat. Rezultati se mogu preuzeti kao Excel. |

Nastavnik još može:
- upisati ili ispraviti ponudu za bilo koji tim (**✏️ Unos ponude za tim**),
- mijenjati troškove, potražnju i kapacitete (**⚙️ Postavke scenarija** → Spremi),
- preuzeti sve ponude u GAMS formatu (`market_input_with_bids.csv`) za usporedbu s originalnim modelom,
- obrisati ponude scenarija za novu grupu studenata.

Predane ponude i postavke spremaju se u `podaci/stanje.json`. Za potpuno novi početak
zatvorite aplikaciju i obrišite tu datoteku.

## Skupni izračun bez web-sučelja

```
.venv\Scripts\python.exe izracun.py ponude --scenarij 1
```

Čita Excel ponude timova iz mape `ponude/` u formatu starog predloška (`time, A_price1, A_cap1, …`).
Nastaje `rezultati_Scenarij_1.xlsx` i `grafovi_Scenarij_1.html`.

## Datoteke

| Datoteka | Sadržaj |
|---|---|
| `app.py` | web-aplikacija (Streamlit) |
| `trziste.py` | čišćenje tržišta, provjera ponuda, Excel ulaz/izlaz |
| `spremiste.py` | zajedničko spremanje ponuda na serveru |
| `grafovi.py` | grafovi (plotly) |
| `postavke.py` | podaci scenarija, kodovi timova, lozinka |
| `izracun.py` | skupni izračun iz mape s Excel ponudama |

## Razlike u odnosu na GAMS (samo rubni slučajevi)

- Ako više ponuda ima **istu marginalnu cijenu**, GAMS proizvoljno odabere jednu;
  ovdje se preostala potražnja dijeli **proporcionalno** među njima.
- Ako potražnja točno završi na kraju bloka, MCP je cijena tog zadnjeg prihvaćenog bloka.
- Ako ponuda ne pokriva potražnju, GAMS javlja "infeasible"; ovdje se ispiše upozorenje.
