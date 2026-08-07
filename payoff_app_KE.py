from datetime import date
from math import erf

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Payoff Opzioni e Futures", layout="wide")
st.title("Payoff Opzioni e Futures")
st.caption("Payoff a scadenza e P/L teorico At Now con Black-76 e ATM IV globale")

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
    mode = st.radio("Modalita grafico", ["Payoff a scadenza", "P/L teorico At Now"])
    st.divider()
    st.subheader("Valutazione Black-76")
    valuation_date = st.date_input("Data di valutazione", value=date(2026, 8, 7))
    option_expiry = st.date_input("Scadenza opzioni", value=date(2026, 11, 20))
    atm_iv = st.number_input("ATM IV globale (%)", value=30.7, step=0.1, min_value=0.01)
    risk_free = st.number_input("Tasso risk-free (%)", value=4.0, step=0.1, min_value=0.0)
    st.caption("At Now usa la sola ATM IV globale per tutte le opzioni. L'IV per riga resta informativa.")
    st.divider()
    commissions = st.number_input("Commissioni totali", value=0.0, step=0.01)
    price_min = st.number_input("Range minimo", value=450.0, step=1.0)
    price_max = st.number_input("Range massimo", value=1350.0, step=1.0)
    if st.button("Ripristina esempio KE"):
        st.session_state.legs = DEFAULT_LEGS.copy()
        st.rerun()

st.subheader("Gambe")
st.caption("Spunta Escludi per togliere una gamba da grafico, payoff, metriche e scenari senza cancellare la riga.")
legs = st.data_editor(
    st.session_state.legs,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Escludi": st.column_config.CheckboxColumn("Escludi", default=False, help="Esclude la gamba da tutti i calcoli"),
        "Strumento": st.column_config.SelectboxColumn(options=["Opzione", "Future"], required=True),
        "Lato": st.column_config.SelectboxColumn(options=["Long", "Short"], required=True),
        "Tipo": st.column_config.SelectboxColumn(options=["Call", "Put", "Future"], required=True),
        "Quantita": st.column_config.NumberColumn(min_value=0.0, step=1.0, required=True),
        "Strike": st.column_config.NumberColumn(step=0.25),
        "Premio/Ingresso": st.column_config.NumberColumn(step=0.0001, format="%.4f", required=True),
        "IV %": st.column_config.NumberColumn(step=0.1, help="Informativa: At Now usa ATM IV globale"),
        "Multiplier": st.column_config.NumberColumn(min_value=0.0001, step=1.0, required=True),
    },
    key="editor",
)
st.session_state.legs = legs

if price_max <= price_min:
    st.error("Il range massimo deve essere superiore al range minimo.")
    st.stop()

required = ["Escludi", "Strumento", "Lato", "Tipo", "Quantita", "Strike", "Premio/Ingresso", "Multiplier"]
if legs.empty or legs[required].isnull().any().any():
    st.warning("Completa tutti i dati obbligatori della tabella.")
    st.stop()

active_legs = legs[~legs["Escludi"]].copy()
if active_legs.empty:
    st.warning("Tutte le gambe sono escluse. Togli la spunta Escludi da almeno una riga.")
    st.stop()

if option_expiry < valuation_date:
    st.error("La scadenza deve essere uguale o successiva alla data di valutazione.")
    st.stop()

dte = (option_expiry - valuation_date).days
t = dte / 365.0


def norm_cdf(x):
    return 0.5 * (1.0 + np.vectorize(erf)(x / np.sqrt(2.0)))


def black76(prices, strike, time_years, sigma, rate, option_type):
    intrinsic = np.maximum(prices - strike, 0.0) if option_type == "Call" else np.maximum(strike - prices, 0.0)
    if time_years <= 0 or sigma <= 0:
        return intrinsic
    safe_prices = np.maximum(prices, 1e-12)
    vol_sqrt_t = sigma * np.sqrt(time_years)
    d1 = (np.log(safe_prices / strike) + 0.5 * sigma * sigma * time_years) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    discount = np.exp(-rate * time_years)
    if option_type == "Call":
        return discount * (prices * norm_cdf(d1) - strike * norm_cdf(d2))
    return discount * (strike * norm_cdf(-d2) - prices * norm_cdf(-d1))


def pnl_expiry(prices, row):
    sign = 1 if row["Lato"] == "Long" else -1
    q = sign * float(row["Quantita"])
    mult = float(row["Multiplier"])
    entry = float(row["Premio/Ingresso"])
    if row["Strumento"] == "Future":
        return q * (prices - entry) * mult
    intrinsic = np.maximum(prices - float(row["Strike"]), 0) if row["Tipo"] == "Call" else np.maximum(float(row["Strike"]) - prices, 0)
    return q * (intrinsic - entry) * mult


def pnl_at_now(prices, row):
    sign = 1 if row["Lato"] == "Long" else -1
    q = sign * float(row["Quantita"])
    mult = float(row["Multiplier"])
    entry = float(row["Premio/Ingresso"])
    if row["Strumento"] == "Future":
        return q * (prices - entry) * mult
    theoretical = black76(prices, float(row["Strike"]), t, atm_iv / 100.0, risk_free / 100.0, row["Tipo"])
    return q * (theoretical - entry) * mult


def breakevens(x, y):
    result = []
    for i in range(len(x) - 1):
        if y[i] == 0:
            result.append(x[i])
        elif y[i] * y[i + 1] < 0:
            result.append(x[i] + (x[i + 1] - x[i]) * (-y[i]) / (y[i + 1] - y[i]))
    return sorted(set(round(v, 4) for v in result))

pnl_function = pnl_expiry if mode == "Payoff a scadenza" else pnl_at_now
prices = np.linspace(price_min, price_max, 2000)
total = np.zeros_like(prices)
for _, row in active_legs.iterrows():
    total += pnl_function(prices, row)
total -= commissions
bes = breakevens(prices, total)
current_total = sum(pnl_function(np.array([future_price]), row)[0] for _, row in active_legs.iterrows()) - commissions

chart_col, metrics_col = st.columns([3, 1])
with chart_col:
    fig = go.Figure()
    for _, row in active_legs.iterrows():
        fig.add_trace(go.Scatter(
            x=prices, y=pnl_function(prices, row), mode="lines", opacity=0.35,
            line={"dash": "dot"}, name=f"{row['Lato']} {row['Tipo']} {row['Strike']}"
        ))
    fig.add_trace(go.Scatter(x=prices, y=total, mode="lines", line={"width": 4, "color": "#00a878"}, name="P/L totale"))
    fig.add_hline(y=0, line_color="gray")
    fig.add_vline(x=future_price, line_dash="dash", line_color="#e69f00", annotation_text=f"Future {future_price:.2f}")
    for be in bes:
        fig.add_vline(x=be, line_dash="dot", line_color="#d55e00", annotation_text=f"BE {be:.4f}")
    fig.update_layout(
        title=f"{name} - {mode}",
        xaxis_title=f"Prezzo {underlying}",
        yaxis_title="P/L (in base al multiplier)",
        hovermode="x unified",
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
    )
    st.plotly_chart(fig, use_container_width=True)

with metrics_col:
    st.subheader("Metriche")
    st.metric("Gambe incluse", f"{len(active_legs)} / {len(legs)}")
    st.metric("Future corrente", f"{future_price:.4f}")
    st.metric("DTE", dte)
    st.metric("ATM IV globale", f"{atm_iv:.1f}%")
    st.metric("P/L al future corrente", f"{current_total:,.2f}")
    st.metric("P/L max nel range", f"{total.max():,.2f}")
    st.metric("P/L min nel range", f"{total.min():,.2f}")
    st.write("**Breakeven del grafico**")
    st.write(", ".join(f"{x:.4f}" for x in bes) if bes else "Nessuno nel range")

scenario_levels = sorted(set([price_min, future_price, price_max] + active_legs.loc[active_legs["Strumento"] == "Opzione", "Strike"].astype(float).tolist() + bes))
scenarios = pd.DataFrame({"Prezzo": scenario_levels})
scenario_total = np.zeros(len(scenarios))
for _, row in active_legs.iterrows():
    scenario_total += pnl_function(scenarios["Prezzo"].to_numpy(), row)
scenarios["P/L totale"] = scenario_total - commissions

st.subheader("Scenari")
st.dataframe(scenarios.style.format({"Prezzo": "{:.4f}", "P/L totale": "{:.2f}"}), use_container_width=True)
st.download_button("Scarica le gambe in CSV", legs.to_csv(index=False).encode("utf-8"), "gambe_strategia.csv", "text/csv")
st.info("At Now e una valutazione teorica Black-76: tutte le opzioni usano ATM IV globale, tasso e DTE impostati nella barra laterale.")
