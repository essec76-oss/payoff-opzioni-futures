from datetime import date
from math import erf

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Payoff Opzioni e Futures", layout="wide")
st.title("Payoff Opzioni e Futures")
st.caption("Payoff a scadenza, P/L teorico At Now e PoP teorica")

DEFAULT_LEGS = pd.DataFrame([
    {"Escludi": False, "Strumento": "Opzione", "Lato": "Short", "Tipo": "Put", "Quantita": 1, "Strike": 600.0, "Premio/Ingresso": 3.9396, "IV %": 26.5, "Multiplier": 50.0},
    {"Escludi": False, "Strumento": "Opzione", "Lato": "Short", "Tipo": "Call", "Quantita": 1, "Strike": 1200.0, "Premio/Ingresso": 2.6898, "IV %": 48.1, "Multiplier": 50.0},
])
if "legs" not in st.session_state:
    st.session_state.legs = DEFAULT_LEGS.copy()

with st.sidebar:
    st.header("Parametri strategia")
    name = st.text_input("Nome strategia", "KE Dec 2026 - Short Strangle")
    underlying = st.text_input("Future sottostante", "KE Dec 2026")
    future_price = st.number_input("Prezzo future corrente", value=721.75, step=0.25, format="%.4f")
    st.subheader("Curve da mostrare")
    show_expiry = st.checkbox("Mostra payoff a scadenza", True)
    show_now = st.checkbox("Mostra P/L teorico At Now", True)
    show_components = st.checkbox("Mostra payoff singole gambe", False)
    st.divider()
    st.subheader("Valutazione Black-76")
    valuation_date = st.date_input("Data di valutazione", date(2026, 8, 7))
    option_expiry = st.date_input("Scadenza opzioni", date(2026, 11, 20))
    atm_iv = st.number_input("ATM IV globale (%)", value=30.7, step=0.1, min_value=0.01)
    risk_free = st.number_input("Tasso risk-free (%)", value=4.0, step=0.1, min_value=0.0)
    st.caption("At Now e PoP usano la sola ATM IV globale.")
    st.divider()
    commissions = st.number_input("Commissioni totali", value=0.0, step=0.01)
    price_min = st.number_input("Range minimo", value=450.0, step=1.0)
    price_max = st.number_input("Range massimo", value=1350.0, step=1.0)
    if st.button("Ripristina esempio KE"):
        st.session_state.legs = DEFAULT_LEGS.copy()
        st.rerun()

st.subheader("Gambe")
st.caption("Spunta Escludi per togliere una gamba da grafico, payoff, metriche, scenari e PoP senza cancellare la riga.")
legs = st.data_editor(
    st.session_state.legs, num_rows="dynamic", use_container_width=True,
    column_config={
        "Escludi": st.column_config.CheckboxColumn("Escludi", default=False),
        "Strumento": st.column_config.SelectboxColumn(options=["Opzione", "Future"], required=True),
        "Lato": st.column_config.SelectboxColumn(options=["Long", "Short"], required=True),
        "Tipo": st.column_config.SelectboxColumn(options=["Call", "Put", "Future"], required=True),
        "Quantita": st.column_config.NumberColumn(min_value=0.0, step=1.0, required=True),
        "Strike": st.column_config.NumberColumn(step=0.25),
        "Premio/Ingresso": st.column_config.NumberColumn(step=0.0001, format="%.4f", required=True),
        "IV %": st.column_config.NumberColumn(step=0.1, help="Informativa: At Now e PoP usano ATM IV globale"),
        "Multiplier": st.column_config.NumberColumn(min_value=0.0001, step=1.0, required=True),
    }, key="editor")
st.session_state.legs = legs

required = ["Escludi", "Strumento", "Lato", "Tipo", "Quantita", "Strike", "Premio/Ingresso", "Multiplier"]
if price_max <= price_min or legs.empty or legs[required].isnull().any().any():
    st.error("Controlla range grafico e dati obbligatori della tabella.")
    st.stop()
if option_expiry < valuation_date:
    st.error("La scadenza deve essere uguale o successiva alla data di valutazione.")
    st.stop()
if not show_expiry and not show_now:
    st.warning("Seleziona almeno una curva da mostrare.")
    st.stop()
active = legs[~legs["Escludi"]].copy()
if active.empty:
    st.warning("Tutte le gambe sono escluse. Togli Escludi da almeno una riga.")
    st.stop()

dte = (option_expiry - valuation_date).days
t = dte / 365.0


def ncdf(x):
    return 0.5 * (1.0 + np.vectorize(erf)(x / np.sqrt(2.0)))


def black76(f, k, ty, sigma, rate, typ):
    intrinsic = np.maximum(f-k, 0.0) if typ == "Call" else np.maximum(k-f, 0.0)
    if ty <= 0 or sigma <= 0:
        return intrinsic
    f = np.maximum(f, 1e-12)
    vs = sigma * np.sqrt(ty)
    d1 = (np.log(f/k) + .5*sigma*sigma*ty) / vs
    d2 = d1 - vs
    disc = np.exp(-rate*ty)
    return disc*(f*ncdf(d1)-k*ncdf(d2)) if typ == "Call" else disc*(k*ncdf(-d2)-f*ncdf(-d1))


def pnl_expiry(p, row):
    q = (1 if row["Lato"] == "Long" else -1) * float(row["Quantita"])
    m, entry = float(row["Multiplier"]), float(row["Premio/Ingresso"])
    if row["Strumento"] == "Future":
        return q*(p-entry)*m
    intrinsic = np.maximum(p-float(row["Strike"]), 0) if row["Tipo"] == "Call" else np.maximum(float(row["Strike"])-p, 0)
    return q*(intrinsic-entry)*m


def pnl_now(p, row):
    q = (1 if row["Lato"] == "Long" else -1) * float(row["Quantita"])
    m, entry = float(row["Multiplier"]), float(row["Premio/Ingresso"])
    if row["Strumento"] == "Future":
        return q*(p-entry)*m
    theoretical = black76(p, float(row["Strike"]), t, atm_iv/100, risk_free/100, row["Tipo"])
    return q*(theoretical-entry)*m


def total(p, fn):
    return sum((fn(p, row) for _, row in active.iterrows()), np.zeros_like(p, dtype=float)) - commissions


def crossings(x, y):
    out = []
    for i in range(len(x)-1):
        if y[i] == 0: out.append(x[i])
        elif y[i]*y[i+1] < 0: out.append(x[i]+(x[i+1]-x[i])*(-y[i])/(y[i+1]-y[i]))
    return sorted(set(round(v, 4) for v in out))


def pop_expiry():
    if t <= 0:
        return 100.0 if total(np.array([future_price]), pnl_expiry)[0] > 0 else 0.0
    sigma = atm_iv/100
    spread = max(12*sigma*np.sqrt(t), 0.25)
    low, high = max(future_price*np.exp(-spread), 1e-8), future_price*np.exp(spread)
    strikes = active.loc[active["Strumento"] == "Opzione", "Strike"].astype(float)
    if not strikes.empty:
        low = min(low, max(strikes.min()*0.05, 1e-8))
        high = max(high, strikes.max()*5)
    edges = np.concatenate(([0.0], np.geomspace(low, high, 12000), [np.inf]))
    finite_edges = edges[1:-1]
    z = (np.log(finite_edges/future_price) + .5*sigma*sigma*t) / (sigma*np.sqrt(t))
    cdf = np.concatenate(([0.0], ncdf(z), [1.0]))
    masses = np.diff(cdf)
    mids = np.empty(len(masses))
    mids[0] = low/2
    mids[-1] = high*2
    mids[1:-1] = np.sqrt(edges[1:-2]*edges[2:-1])
    return float(np.sum(masses[total(mids, pnl_expiry) > 0]) * 100)

prices = np.linspace(price_min, price_max, 2000)
exp_total, now_total = total(prices, pnl_expiry), total(prices, pnl_now)
exp_be, now_be = crossings(prices, exp_total), crossings(prices, now_total)
exp_current = total(np.array([future_price]), pnl_expiry)[0]
now_current = total(np.array([future_price]), pnl_now)[0]
pop = pop_expiry()

left, right = st.columns([3, 1])
with left:
    fig = go.Figure()
    if show_components:
        for _, row in active.iterrows():
            fig.add_trace(go.Scatter(x=prices, y=pnl_expiry(prices,row), mode="lines", opacity=.3, line={"dash":"dot"}, name=f"Scad. {row['Lato']} {row['Tipo']} {row['Strike']}"))
    if show_expiry:
        fig.add_trace(go.Scatter(x=prices, y=exp_total, mode="lines", line={"width":4,"color":"#00a878"}, name="Payoff a scadenza"))
        for be in exp_be: fig.add_vline(x=be, line_dash="dot", line_color="#d55e00", annotation_text=f"BE scad. {be:.4f}")
    if show_now:
        fig.add_trace(go.Scatter(x=prices, y=now_total, mode="lines", line={"width":2,"dash":"dash","color":"#3b82f6"}, name="P/L teorico At Now"))
        for be in now_be: fig.add_vline(x=be, line_dash="dash", line_color="#3b82f6", annotation_text=f"BE now {be:.4f}")
    fig.add_hline(y=0, line_color="gray")
    fig.add_vline(x=future_price, line_dash="dash", line_color="#e69f00", annotation_text=f"Future {future_price:.2f}")
    fig.update_layout(title=f"{name} - curve P/L", xaxis_title=f"Prezzo {underlying}", yaxis_title="P/L (in base al multiplier)", hovermode="x unified", margin={"l":10,"r":10,"t":50,"b":10})
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("Metriche")
    st.metric("Gambe incluse", f"{len(active)} / {len(legs)}")
    st.metric("Future corrente", f"{future_price:.4f}")
    st.metric("DTE", dte)
    st.metric("ATM IV globale", f"{atm_iv:.1f}%")
    st.metric("PoP teorica a scadenza", f"{pop:.1f}%")
    if show_expiry: st.metric("P/L scadenza al prezzo attuale", f"{exp_current:,.2f}")
    if show_now: st.metric("P/L At Now al prezzo attuale", f"{now_current:,.2f}")

levels = sorted(set([price_min, future_price, price_max] + active.loc[active["Strumento"] == "Opzione", "Strike"].astype(float).tolist() + exp_be + now_be))
scenarios = pd.DataFrame({"Prezzo": levels})
if show_expiry: scenarios["P/L a scadenza"] = total(np.array(levels), pnl_expiry)
if show_now: scenarios["P/L At Now"] = total(np.array(levels), pnl_now)
st.subheader("Scenari")
st.dataframe(scenarios.style.format({c:"{:.2f}" for c in scenarios.columns}), use_container_width=True)
st.download_button("Scarica le gambe in CSV", legs.to_csv(index=False).encode("utf-8"), "gambe_strategia.csv", "text/csv")
st.info("PoP teorica a scadenza: probabilita modellistica di P/L > 0, basata su future corrente, DTE, ATM IV globale e sole gambe incluse.")
