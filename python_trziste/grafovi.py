"""Grafovi rezultata (plotly) - koriste ih app.py i izracun.py."""
import plotly.graph_objects as go

import trziste as T

# Boje elektrana (fiksni redoslijed, provjereno za daltonizam)
BOJE = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a", "D": "#eda100"}
SIVA = "#52514e"


def boja(el):
    return BOJE.get(el, SIVA)


def _layout(fig, naslov, y, x="Sat", visina=400):
    fig.update_layout(
        title=dict(text=naslov, x=0, font=dict(size=16)),
        height=visina, margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified", legend=dict(orientation="h", y=-0.2),
        plot_bgcolor="rgba(0,0,0,0)", bargap=0.15,
        xaxis=dict(title=x, showgrid=False),
        yaxis=dict(title=y, gridcolor="rgba(128,128,128,0.2)", zeroline=False),
    )
    return fig


def cijena_po_satu(s):
    fig = go.Figure(go.Scatter(
        x=s["Sat"], y=s["MCP"], mode="lines+markers", name="Cijena (MCP)",
        line=dict(color=BOJE["A"], width=2), marker=dict(size=8),
        hovertemplate="MCP %{y:.2f} €/MWh<extra></extra>"))
    fig = _layout(fig, "Tržišna cijena (MCP) po satu", "€/MWh")
    fig.update_xaxes(dtick=1)
    return fig


def potraznja_graf(potraznja, kapacitet_jedne, broj_elektrana, scen):
    """Potražnja po satu s oznakama koliko elektrana je potrebno za njeno pokrivanje."""
    sati = list(range(1, len(potraznja) + 1))
    fig = go.Figure(go.Bar(x=sati, y=potraznja, name="Potražnja", marker=dict(color=BOJE["A"], line=dict(width=0)),
                           hovertemplate="Sat %{x}: %{y:.0f} MWh<extra></extra>"))
    vrh = max(potraznja)
    for n in range(1, broj_elektrana + 1):
        y = n * kapacitet_jedne
        if y > vrh * 1.25 and n > 1:
            break
        fig.add_hline(y=y, line=dict(color=SIVA, width=1, dash="dot"),
                      annotation_text=f"{n} {'elektrana' if n == 1 else 'elektrane'} ({y:g} MW)",
                      annotation_position="top left", annotation_font_size=11)
    fig = _layout(fig, f"Ukupna potražnja tržišta – {scen}", "MWh", visina=330)
    fig.update_layout(showlegend=False, hovermode="closest")
    fig.update_xaxes(dtick=1)
    return fig


def proizvodnja_po_satu(s, elektrane):
    fig = go.Figure()
    for el in elektrane:
        fig.add_bar(x=s["Sat"], y=s[el], name=el, marker=dict(color=boja(el), line=dict(width=0)),
                    hovertemplate=f"{el}: %{{y:.1f}} MWh<extra></extra>")
    fig.add_scatter(x=s["Sat"], y=s["Potražnja"], name="Potražnja", mode="lines",
                    line=dict(color=SIVA, width=2, dash="dot", shape="hvh"),
                    hovertemplate="Potražnja: %{y:.0f} MWh<extra></extra>")
    fig = _layout(fig, "Proizvodnja elektrana po satu", "MWh")
    fig.update_layout(barmode="stack")
    fig.update_xaxes(dtick=1)
    return fig


def profit_po_elektrani(sz):
    fig = go.Figure(go.Bar(
        x=sz["Elektrana"], y=sz["Profit [EUR]"], marker_color=[boja(e) for e in sz["Elektrana"]],
        text=sz["Profit [EUR]"].map(lambda v: f"{v:,.0f} €".replace(",", " ")), textposition="outside",
        cliponaxis=False,
        customdata=sz[["Prihod [EUR]", "Trošak [EUR]", "Energija [MWh]"]].to_numpy(),
        hovertemplate=("Profit %{y:,.0f} €<br>Prihod %{customdata[0]:,.0f} €<br>"
                       "Trošak %{customdata[1]:,.0f} €<br>Energija %{customdata[2]:,.0f} MWh<extra></extra>"),
    ))
    fig = _layout(fig, "Profit po elektrani (cijeli dan)", "€", x="Elektrana")
    fig.update_layout(hovermode="closest", showlegend=False, bargap=0.45)
    return fig


def ukupni_profit(tab, scenariji):
    """Složeni stupci: profit po elektrani, segment = scenarij (nijanse jedne boje, scenariji su poredani)."""
    nijanse = ["#86b6ef", "#2a78d6", "#104281", "#0d366b"]
    fig = go.Figure()
    for i, sc in enumerate(scenariji):
        fig.add_bar(x=tab.index, y=tab[sc], name=sc, marker=dict(color=nijanse[i % len(nijanse)],
                                                                   line=dict(color="white", width=2)),
                    hovertemplate=f"{sc}: %{{y:,.0f}} €<extra></extra>")
    fig.add_scatter(x=tab.index, y=tab["Ukupno"], mode="text", showlegend=False, hoverinfo="skip",
                    text=[f"{v:,.0f} €".replace(",", " ") for v in tab["Ukupno"]], textposition="top center")
    fig = _layout(fig, "Ukupni profit po elektrani (zbroj scenarija)", "€", x="Elektrana", visina=420)
    fig.update_layout(barmode="relative", bargap=0.45)
    return fig


def krivulja_ponude(rez, sat, elektrane):
    kr = T.krivulja_ponude(rez.ponude, sat)
    s = rez.satni
    d, mcp = s.loc[sat - 1, "Potražnja"], s.loc[sat - 1, "MCP"]
    fig = go.Figure()
    for el in elektrane:
        k = kr[kr["Elektrana"] == el]
        fig.add_bar(
            x=(k["Od"] + k["Do"]) / 2, y=k["Cijena"], width=k["Količina"], name=el,
            marker=dict(color=boja(el), line=dict(color="white", width=1)),
            customdata=k[["Blok", "Količina", "Prihvaćeno"]].to_numpy(),
            hovertemplate=(f"{el}, blok %{{customdata[0]}}<br>Cijena %{{y:.2f}} €/MWh<br>"
                           "Ponuđeno %{customdata[1]:.0f} MW, prihvaćeno %{customdata[2]:.1f} MW"
                           "<extra></extra>"))
    fig.add_vline(x=d, line=dict(color=SIVA, width=2, dash="dot"),
                  annotation_text=f"Potražnja {d:.0f} MWh", annotation_position="top left")
    fig.add_hline(y=mcp, line=dict(color=SIVA, width=1),
                  annotation_text=f"MCP {mcp:.2f} €/MWh", annotation_position="bottom right")
    fig = _layout(fig, f"Krivulja ponude (merit order) – sat t{sat}", "€/MWh", x="Kumulativna količina [MW]")
    fig.update_layout(barmode="overlay", hovermode="closest", bargap=0)
    return fig
