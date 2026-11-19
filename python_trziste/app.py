"""
ORES - vježba: tržište električne energije (dan unaprijed) - web aplikacija

Pokretanje na nastavnikovom računalu:  pokreni_aplikaciju.bat
Studenti otvore u pregledniku adresu koju skripta ispiše (npr. http://192.168.1.20:8501).
"""
import pandas as pd
import streamlit as st

import grafovi as G
import postavke as P
import spremiste as S
import trziste as T

st.set_page_config(page_title="ORES – tržište električne energije", page_icon="⚡", layout="wide")
ss = st.session_state
ss.setdefault("uloga", None)        # None | "nastavnik" | "A".."D"
ss.setdefault("ponude_ed", {})      # (scen, tim) -> početni DataFrame za editor
ss.setdefault("verzija", {})        # (scen, tim) -> int


def fmt_eur(v):
    return f"{v:,.0f} €".replace(",", " ")


# ---------------------------------------------------------------------------
# Prijava (bočna traka)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚡ ORES tržište")
    if ss.uloga is None:
        vrsta = st.radio("Prijava kao", ["Tim (student)", "Nastavnik"], horizontal=True)
        with st.form("prijava"):
            if vrsta == "Tim (student)":
                tim = st.selectbox("Elektrana / tim", P.ELEKTRANE)
                kod = st.text_input("Kod tima", type="password")
            else:
                lozinka = st.text_input("Lozinka", type="password")
            if st.form_submit_button("Prijava", type="primary", width="stretch"):
                if vrsta == "Nastavnik" and lozinka == P.LOZINKA_NASTAVNIKA:
                    ss.uloga = "nastavnik"
                    st.rerun()
                elif vrsta != "Nastavnik" and kod.strip().lower() == P.KODOVI_TIMOVA[tim].lower():
                    ss.uloga = tim
                    st.rerun()
                else:
                    st.error("Pogrešan kod / lozinka.")
    else:
        st.success("Prijavljeni: " + ("**nastavnik**" if ss.uloga == "nastavnik" else f"**tim {ss.uloga}**"))
        if st.button("Odjava", width="stretch"):
            ss.uloga = None
            st.rerun()
        st.divider()
        scen = st.radio("Scenarij", P.SCENARIJI)

if ss.uloga is None:
    st.title("ORES – vježba: tržište električne energije")
    st.markdown(
        """
Četiri elektrane (timovi **A–D**) natječu se na tržištu dan-unaprijed. Svaki tim za svaki
od **24 sata** predaje **3 ponude**: cijenu [€/MWh] i količinu [MW]. Zbroj količina u satu
mora biti jednak kapacitetu elektrane (350 MW).

Tržište prihvaća ponude od najjeftinije prema najskupljoj dok se ne pokrije potražnja.
Cijena koju dobivaju **sve** prihvaćene ponude je cijena posljednje prihvaćene (marginalne)
ponude. Profit = (tržišna cijena − vaš trošak) × prodana energija.

👈 **Prijavite se lijevo** kodom koji ste dobili za svoj tim.
"""
    )
    st.stop()

stanje = S.stanje()
trosak_df, potraznja_df, kapacitet = S.postavke_df(stanje)
potraznja = potraznja_df[scen].tolist()
trosak = trosak_df.loc[scen].to_dict()
predane = S.predane_ponude(stanje, scen)


# ---------------------------------------------------------------------------
# Zajednički dijelovi
# ---------------------------------------------------------------------------
def prikazi_rezultate(ponude: dict, kljuc: str):
    if not ponude:
        st.info("Još nema predanih ponuda za ovaj scenarij.")
        return
    elektrane = list(ponude)
    rez = T.ocisti_trziste(ponude, potraznja, {e: trosak[e] for e in elektrane}, P.BROJ_PONUDA)
    s = rez.satni
    if rez.nepokriveno:
        st.error("⚠️ Ponuda nije dovoljna za pokrivanje potražnje u satima: "
                 + ", ".join(f"t{h} ({v:.1f} MWh)" for h, v in rez.nepokriveno.items()))

    cols = st.columns(len(elektrane))
    for c, (_, r) in zip(cols, rez.sazetak.iterrows()):
        with c, st.container(border=True):
            moj = " (vi)" if r.Elektrana == ss.uloga else ""
            st.markdown(f"<span style='color:{G.boja(r.Elektrana)}'>■</span> **Elektrana {r.Elektrana}{moj}**",
                        unsafe_allow_html=True)
            st.metric("Profit", fmt_eur(r["Profit [EUR]"]))
            st.caption(f"Prodano {r['Energija [MWh]']:,.0f} MWh · prihod {fmt_eur(r['Prihod [EUR]'])} · "
                       f"trošak {fmt_eur(r['Trošak [EUR]'])}".replace(",", " "))

    g1, g2 = st.columns(2)
    g1.plotly_chart(G.cijena_po_satu(s), width="stretch", key=f"g1_{kljuc}")
    g2.plotly_chart(G.proizvodnja_po_satu(s, elektrane), width="stretch", key=f"g2_{kljuc}")
    g3, g4 = st.columns(2)
    g3.plotly_chart(G.profit_po_elektrani(rez.sazetak), width="stretch", key=f"g3_{kljuc}")
    with g4:
        sat = st.slider("Sat za krivulju ponude (merit order)", 1, 24, int(s["Potražnja"].idxmax()) + 1,
                        key=f"sat_{kljuc}")
        st.plotly_chart(G.krivulja_ponude(rez, sat, elektrane), width="stretch", key=f"g4_{kljuc}")

    st.markdown("#### Tablice")
    t1, t2 = st.tabs(["Sažetak po elektrani", "Po satu"])
    t1.dataframe(rez.sazetak.round(2), width="stretch", hide_index=True)
    t2.dataframe(s.round(2), width="stretch", hide_index=True)
    st.download_button("⬇️ Preuzmi rezultate (Excel)", T.rezultati_excel(rez, scen),
                       file_name=f"rezultati_{scen.replace(' ', '_')}.xlsx", key=f"dlr_{kljuc}")


def prikazi_ukupno(scenariji: list, kljuc: str):
    """Zbroj profita po elektrani kroz zadane scenarije + poredak."""
    if not scenariji:
        st.info("Još nema objavljenih rezultata.")
        return
    redovi, nepotpuni = {}, []
    for sc in scenariji:
        pon = S.predane_ponude(stanje, sc)
        if not pon:
            continue
        if len(pon) < len(P.ELEKTRANE):
            nepotpuni.append(sc)
        rez = T.ocisti_trziste(pon, potraznja_df[sc].tolist(), trosak_df.loc[sc].to_dict(), P.BROJ_PONUDA)
        redovi[sc] = rez.sazetak.set_index("Elektrana")["Profit [EUR]"]
    if not redovi:
        st.info("Još nema predanih ponuda.")
        return
    tab = pd.DataFrame(redovi).reindex(P.ELEKTRANE).fillna(0.0)
    sc_ok = list(tab.columns)
    tab["Ukupno"] = tab[sc_ok].sum(axis=1)
    tab = tab.sort_values("Ukupno", ascending=False)
    if nepotpuni:
        st.warning("U scenarijima " + ", ".join(nepotpuni) + " nisu predali svi timovi.")
    st.caption("Uključeni scenariji: " + ", ".join(sc_ok))

    medalje = ["🥇", "🥈", "🥉"]
    cols = st.columns(len(tab))
    for i, (c, (el, r)) in enumerate(zip(cols, tab.iterrows())):
        with c, st.container(border=True):
            moj = " (vi)" if el == ss.uloga else ""
            st.markdown(f"{medalje[i] if i < 3 else f'{i + 1}.'} <span style='color:{G.boja(el)}'>■</span> "
                        f"**Elektrana {el}{moj}**", unsafe_allow_html=True)
            st.metric("Ukupni profit", fmt_eur(r["Ukupno"]))

    st.plotly_chart(G.ukupni_profit(tab, sc_ok), width="stretch", key=f"guk_{kljuc}")
    prikaz = tab.copy()
    prikaz.insert(0, "Mjesto", range(1, len(tab) + 1))
    st.dataframe(prikaz.round(0), width="stretch",
                 column_config={c: st.column_config.NumberColumn(c, format="%.0f €") for c in sc_ok + ["Ukupno"]})


@st.fragment(run_every=5)
def status_predaja(scen):
    """Osvježava se sam svakih 5 s."""
    pred = S.stanje()["ponude"][scen]
    cols = st.columns(len(P.ELEKTRANE))
    for c, el in zip(cols, P.ELEKTRANE):
        if el in pred:
            c.success(f"**{el}** ✅ predano\n\n{pred[el]['vrijeme']}")
        else:
            c.warning(f"**{el}** ⏳ čeka se")


def urednik_ponude(tim: str, pocetna: pd.DataFrame, zakljucano: bool):
    """Tablica za unos ponude + brzi unos + Excel. Vraća (DataFrame, greške)."""
    kljuc = (scen, tim)
    if kljuc not in ss.ponude_ed:
        ss.ponude_ed[kljuc] = pocetna
        ss.verzija[kljuc] = 0
    baza, ver = ss.ponude_ed[kljuc], ss.verzija[kljuc]
    zadnja_k = f"zadnja_{scen}_{tim}"

    def zamijeni(df):
        ss.ponude_ed[kljuc] = df
        ss.verzija[kljuc] = ss.verzija[kljuc] + 1

    lijevo, desno = st.columns([3, 1.3], gap="large")
    with desno:
        with st.expander("⚡ Brzi unos (iste ponude za više sati)"):
            with st.form(f"brzo_{scen}_{tim}"):
                vr = []
                prvi = ss.get(zadnja_k, baza).iloc[0].fillna(0.0)
                for b in range(1, P.BROJ_PONUDA + 1):
                    c1, c2 = st.columns(2)
                    vr.append(c1.number_input(f"Cijena {b}", value=float(prvi[f"Cijena {b}"]), step=1.0,
                                              key=f"qc{b}_{scen}_{tim}"))
                    vr.append(c2.number_input(f"Količina {b}", value=float(prvi[f"Količina {b}"]), min_value=0.0,
                                              step=5.0, key=f"qk{b}_{scen}_{tim}"))
                sati = st.slider("Za sate", 1, 24, (1, 24), key=f"qs_{scen}_{tim}")
                if st.form_submit_button("Primijeni na tablicu", disabled=zakljucano):
                    novi = ss.get(zadnja_k, baza).copy()
                    novi.loc[sati[0]:sati[1], :] = vr
                    zamijeni(novi)
                    st.rerun()

        with st.expander("📂 Excel"):
            up = st.file_uploader("Učitaj ponudu iz Excela (.xlsx / .csv)", type=["xlsx", "csv"],
                                  key=f"up_{scen}_{tim}_{ver}", disabled=zakljucano)
            if up is not None:
                try:
                    df_up, _ = T.citaj_ponudu_excel(up, P.BROJ_PONUDA)
                    zamijeni(df_up)
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"Datoteka nije učitana: {e}")
            st.download_button(
                "⬇️ Preuzmi Excel predložak", key=f"dl_{scen}_{tim}",
                data=T.predlozak_excel(tim, ss.get(zadnja_k, baza), kapacitet[tim], trosak[tim],
                                       potraznja, scen, P.BROJ_PONUDA),
                file_name=f"{tim}_{scen.replace(' ', '_')}.xlsx",
            )

    with lijevo:
        cfg = {"Potražnja": st.column_config.NumberColumn(
            "Potražnja [MWh]", format="%.0f", help="Ukupna potražnja tržišta u tom satu (samo za informaciju)")}
        for b in range(1, P.BROJ_PONUDA + 1):
            cfg[f"Cijena {b}"] = st.column_config.NumberColumn(f"Cijena {b} [€/MWh]", format="%.2f", step=0.5)
            cfg[f"Količina {b}"] = st.column_config.NumberColumn(f"Količina {b} [MW]", min_value=0,
                                                                 format="%.1f", step=1)
        prikaz = baza.copy()
        prikaz.insert(0, "Potražnja", potraznja)
        ured = st.data_editor(prikaz, column_config=cfg, width="stretch", height=36 * 25 + 3,
                              key=f"ed_{scen}_{tim}_{ver}", num_rows="fixed",
                              disabled=True if zakljucano else ["Potražnja"])
        ured = ured.drop(columns="Potražnja")
        ss[zadnja_k] = ured

    with desno:
        greske, upoz = T.provjeri_ponudu(ured, kapacitet[tim], P.BROJ_PONUDA)
        if not greske and not upoz:
            st.success(f"✅ Ponuda ispravna (zbroj = {kapacitet[tim]:g} MW u svim satima)")
        for g in greske:
            st.error(g)
        for u in upoz:
            st.warning(u)
        if st.button("↺ Očisti tablicu", key=f"reset_{scen}_{tim}", disabled=zakljucano):
            zamijeni(T.ponuda_iz_liste(P.POCETNA_TABLICA, P.BROJ_PONUDA))
            st.rerun()
    return ured, greske, desno


# ---------------------------------------------------------------------------
# STUDENT (tim)
# ---------------------------------------------------------------------------
if ss.uloga != "nastavnik":
    tim = ss.uloga
    zakljucano = stanje["zakljucano"][scen]
    st.title(f"Elektrana {tim} – {scen}")

    tab_pon, tab_rez, tab_uk = st.tabs(["📝 Moja ponuda", "📊 Rezultati", "🏆 Ukupno"])
    with tab_pon:
        with st.expander("ℹ️ Podaci za ponudu – pročitajte prije unosa", expanded=True):
            ukupno = sum(kapacitet.values())
            m = st.columns(4)
            m[0].metric("Vaš varijabilni trošak", f"{trosak[tim]:g} €/MWh")
            m[1].metric("Kapacitet vaše elektrane", f"{kapacitet[tim]:g} MW")
            m[2].metric("Potražnja (min – max)", f"{min(potraznja):.0f} – {max(potraznja):.0f} MWh")
            m[3].metric("Ukupni kapacitet tržišta", f"{ukupno:g} MW", help=f"{len(P.ELEKTRANE)} elektrane")
            if P.PRIKAZI_TUDE_TROSKOVE:
                st.caption("Troškovi svih elektrana: " + " · ".join(f"{e}: {trosak[e]:g} €/MWh" for e in P.ELEKTRANE))
            g, tekst = st.columns([1.6, 1], gap="large")
            g.plotly_chart(G.potraznja_graf(potraznja, kapacitet[tim], len(P.ELEKTRANE), scen),
                           width="stretch", key="g_pot")
            tekst.markdown(
                f"""
**Kako tržište radi**
- Za svaki sat predajete **3 ponude** (cijena + količina). Zbroj količina = **{kapacitet[tim]:g} MW**.
- Tržište slaže ponude **svih {len(P.ELEKTRANE)} elektrana** od najjeftinije prema najskupljoj
  dok se ne pokrije potražnja.
- **Sve** prihvaćene ponude dobivaju istu cijenu – cijenu **posljednje prihvaćene** ponude (MCP).
- Vaš profit u satu = (MCP − {trosak[tim]:g} €/MWh) × prodana količina.

**Razmislite:** koliko je potražnje u odnosu na kapacitet svih elektrana? Kad je potražnja
mala, konkurencija je jaka; kad je velika, potrebne su gotovo sve elektrane.
"""
            )

        if zakljucano:
            st.warning("🔒 Predaja ponuda za ovaj scenarij je zatvorena.")
        pred = stanje["ponude"][scen].get(tim)
        if pred:
            st.info(f"Vaša ponuda je predana **{pred['vrijeme']}**. Možete je izmijeniti i ponovno predati "
                    "dok je predaja otvorena – vrijedi zadnja predana.")
        pocetna = predane.get(tim, T.ponuda_iz_liste(P.POCETNA_TABLICA, P.BROJ_PONUDA))
        ured, greske, desno = urednik_ponude(tim, pocetna, zakljucano)
        with desno:
            st.divider()
            if st.button("📤 PREDAJ PONUDU", type="primary", width="stretch",
                         disabled=bool(greske) or zakljucano):
                if S.stanje()["zakljucano"][scen]:
                    st.error("Predaja je upravo zatvorena.")
                else:
                    S.predaj_ponudu(scen, tim, ured)
                    st.toast("Ponuda predana ✅")
                    st.rerun()
            if greske:
                st.caption("Ispravite greške da biste mogli predati ponudu.")

        st.markdown("##### Status predaja")
        status_predaja(scen)

    with tab_rez:
        if stanje["objavljeno"][scen]:
            prikazi_rezultate(predane, f"s_{scen}")
        else:
            st.info("⏳ Nastavnik još nije objavio rezultate za ovaj scenarij. "
                    "Kliknite **Osvježi** kad vam kaže.")
            if st.button("🔄 Osvježi"):
                st.rerun()
    with tab_uk:
        prikazi_ukupno([s for s in P.SCENARIJI if stanje["objavljeno"][s]], "s")
    st.stop()

# ---------------------------------------------------------------------------
# NASTAVNIK
# ---------------------------------------------------------------------------
st.title(f"Nastavnik – {scen}")
tab_pre, tab_rez, tab_uk, tab_unos, tab_post = st.tabs(
    ["📋 Predaje", "📊 Rezultati", "🏆 Ukupno", "✏️ Unos ponude za tim", "⚙️ Postavke scenarija"])

with tab_uk:
    st.caption("Zbroj profita svih scenarija (nastavnik vidi sve; studenti samo objavljene scenarije).")
    prikazi_ukupno(P.SCENARIJI, "n")

with tab_pre:
    status_predaja(scen)
    c1, c2, c3 = st.columns(3)
    zak = c1.toggle("🔒 Zatvori predaju ponuda", value=stanje["zakljucano"][scen])
    obj = c2.toggle("📢 Objavi rezultate studentima", value=stanje["objavljeno"][scen])
    if zak != stanje["zakljucano"][scen] or obj != stanje["objavljeno"][scen]:
        def _f(st_):
            st_["zakljucano"][scen] = zak
            st_["objavljeno"][scen] = obj
        S.izmijeni(_f)
        st.rerun()
    with c3:
        with st.popover("🗑️ Obriši ponude ovog scenarija"):
            st.write("Brišu se sve predane ponude za **" + scen + "**.")
            if st.button("Da, obriši", type="primary"):
                S.izmijeni(lambda st_: st_["ponude"][scen].clear())
                st.rerun()

    if predane:
        st.markdown("##### Predane ponude")
        for el, df in predane.items():
            with st.expander(f"Elektrana {el}"):
                st.dataframe(df, width="stretch")
        # GAMS format (market_input_with_bids.csv), za usporedbu s originalnim modelom
        gams = pd.DataFrame({"time": [f"t{h}" for h in range(1, 25)]})
        for el, df in predane.items():
            for b in range(1, P.BROJ_PONUDA + 1):
                gams[f"{el}_price{b}"] = df[f"Cijena {b}"].values
                gams[f"{el}_cap{b}"] = df[f"Količina {b}"].values
            gams[f"{el}_cost"] = trosak[el]
        gams["demand"] = potraznja
        st.download_button("⬇️ Sve ponude u GAMS formatu (market_input_with_bids.csv)",
                           gams.to_csv(index=False).encode("utf-8"), file_name="market_input_with_bids.csv")

with tab_rez:
    nedostaju = [e for e in P.ELEKTRANE if e not in predane]
    if nedostaju and predane:
        st.warning("Nedostaju ponude timova: " + ", ".join(nedostaju) + ". Rezultat je izračunat bez njih.")
    prikazi_rezultate(predane, f"n_{scen}")

with tab_unos:
    st.caption("Ovdje nastavnik može upisati ili ispraviti ponudu za bilo koji tim (npr. ako tim nije predao).")
    tim = st.selectbox("Tim", P.ELEKTRANE, key="n_tim")
    pocetna = predane.get(tim, T.ponuda_iz_liste(P.POCETNA_TABLICA, P.BROJ_PONUDA))
    ured, greske, desno = urednik_ponude(tim, pocetna, False)
    with desno:
        if st.button(f"📤 Spremi kao ponudu tima {tim}", type="primary", disabled=bool(greske), width="stretch"):
            S.predaj_ponudu(scen, tim, ured)
            st.toast(f"Ponuda tima {tim} spremljena ✅")
            st.rerun()

with tab_post:
    st.caption("Promjene vrijede za sve korisnike nakon klika na **Spremi postavke**. "
               "Početne vrijednosti su u postavke.py.")
    c1, c2 = st.columns([1, 1.4], gap="large")
    with c1:
        st.markdown("**Varijabilni trošak [€/MWh]** (redak = scenarij)")
        t_ed = st.data_editor(trosak_df, key="ed_trosak", width="stretch")
        st.markdown("**Kapacitet [MW]**")
        k_ed = st.data_editor(pd.DataFrame({"Kapacitet [MW]": kapacitet}), key="ed_kap", width="stretch")
    with c2:
        st.markdown("**Potražnja po satu [MWh]**")
        p_ed = st.data_editor(potraznja_df, key="ed_pot", width="stretch", height=36 * 25 + 3)
    b1, b2 = st.columns(2)
    if b1.button("💾 Spremi postavke", type="primary"):
        S.spremi_postavke(t_ed, p_ed, k_ed["Kapacitet [MW]"].to_dict())
        st.toast("Postavke spremljene ✅")
        st.rerun()
    if b2.button("↺ Vrati na vrijednosti iz postavke.py"):
        S.spremi_postavke(pd.DataFrame(P.TROSAK).T, pd.DataFrame(P.POTRAZNJA), P.KAPACITET)
        for k in ("ed_trosak", "ed_kap", "ed_pot"):
            ss.pop(k, None)
        st.rerun()
