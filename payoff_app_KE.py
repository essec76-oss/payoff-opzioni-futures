import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st
from scipy.stats import norm

st.set_page_config(page_title="Options Calculator V23", layout="wide")
st.title("Options Calculator V23")
st.caption("Black–Scholes · Theta ricalcolato a un giorno · Risk-free predefinito 0%")


def bs_price(spot, strike, years, rate, sigma, option_type):
    if spot <= 0 or strike <= 0:
        return 0.0
    if years <= 0 or sigma <= 0:
        return max(0.0, spot - strike) if option_type == "Call" else max(0.0, strike - spot)
    root_t = math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma**2) * years) / (sigma * root_t)
    d2 = d1 - sigma * root_t
    if option_type == "Call":
        return spot * norm.cdf(d1) - strike * math.exp(-rate * years) * norm.cdf(d2)
    return strike * math.exp(-rate * years) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def greeks(spot, strike, dte, rate, iv_pct, option_type):
    years = max(float(dte), 0.0) / 365.0
    sigma = max(float(iv_pct), 0.0) / 100.0
    if spot <= 0 or strike <= 0 or sigma <= 0 or years <= 0:
        return {"Delta": 0.0, "Gamma": 0.0, "Vega": 0.0, "THETA": 0.0, "Teorico": bs_price(spot, strike, years, rate, sigma, option_type)}

    root_t = math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma**2) * years) / (sigma * root_t)
    delta = norm.cdf(d1) if option_type == "Call" else norm.cdf(d1) - 1
    gamma = norm.pdf(d1) / (spot * sigma * root_t)
    vega = spot * norm.pdf(d1) * root_t / 100.0
    today = bs_price(spot, strike, years, rate, sigma, option_type)
    tomorrow = bs_price(spot, strike, max(float(dte) - 1.0, 0.0) / 365.0, rate, sigma, option_type)
    return {"Delta": delta, "Gamma": gamma, "Vega": vega, "THETA": tomorrow - today, "Teorico": today}


if "positions" not in st.session_state:
    st.session_state.positions = pd.DataFrame([
        {"Buy/Sell": "Buy", "Tipo": "Call", "Strike": 100.0, "Scadenza": date.today() + timedelta(days=30), "N° opz": 1, "IV (%)": 25.0, "Premio": 0.0}
    ])

with st.sidebar:
    st.header("Parametri")
    spot = st.number_input("Prezzo sottostante", min_value=0.01, value=100.0, step=0.01)
    risk_free_pct = st.number_input("Risk-free (%)", value=0.0, step=0.1, format="%.3f")
    multiplier = st.number_input("Moltiplicatore", min_value=1.0, value=100.0, step=1.0)
    st.caption("Il tasso risk-free parte sempre da 0%, ma può essere modificato.")

left, right = st.columns([1, 5])
with left:
    if st.button("+ Aggiungi riga", use_container_width=True):
        st.session_state.positions = pd.concat([st.session_state.positions, pd.DataFrame([{
            "Buy/Sell": "Buy", "Tipo": "Call", "Strike": spot, "Scadenza": date.today() + timedelta(days=30), "N° opz": 1, "IV (%)": 25.0, "Premio": 0.0
        }])], ignore_index=True)
        st.rerun()
    if st.button("Rimuovi ultima", use_container_width=True) and len(st.session_state.positions) > 1:
        st.session_state.positions = st.session_state.positions.iloc[:-1].reset_index(drop=True)
        st.rerun()
with right:
    st.write("Inserisci le posizioni. Buy ha segno positivo, Sell ha segno negativo.")

edited = st.data_editor(
    st.session_state.positions,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "Buy/Sell": st.column_config.SelectboxColumn("Buy/Sell", options=["Buy", "Sell"], required=True),
        "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Call", "Put"], required=True),
        "Strike": st.column_config.NumberColumn("Strike", min_value=0.01, format="%.2f"),
        "Scadenza": st.column_config.DateColumn("Scadenza", min_value=date.today()),
        "N° opz": st.column_config.NumberColumn("N° opz", min_value=1, step=1, format="%d"),
        "IV (%)": st.column_config.NumberColumn("IV (%)", min_value=0.01, format="%.2f"),
        "Premio": st.column_config.NumberColumn("Premio", format="%.2f"),
    },
    key="positions_editor",
)
st.session_state.positions = edited

rate = risk_free_pct / 100.0
rows = []
for _, p in edited.iterrows():
    expiry = pd.to_datetime(p["Scadenza"]).date()
    dte = max((expiry - date.today()).days, 0)
    values = greeks(float(spot), float(p["Strike"]), dte, rate, float(p["IV (%)"]), p["Tipo"])
    sign = 1 if p["Buy/Sell"] == "Buy" else -1
    quantity = float(p["N° opz"])
    premium_pnl = sign * (values["Teorico"] - float(p["Premio"])) * quantity * multiplier
    rows.append({
        "Buy/Sell": p["Buy/Sell"], "Tipo": p["Tipo"], "Strike": p["Strike"], "DTE": dte,
        "N° opz": quantity, "IV (%)": p["IV (%)"], "Premio": p["Premio"],
        "Teorico": values["Teorico"], "P/L teorico": premium_pnl,
        "Delta": sign * values["Delta"] * quantity * multiplier,
        "Gamma": sign * values["Gamma"] * quantity * multiplier,
        "Vega": sign * values["Vega"] * quantity * multiplier,
        "THETA": sign * values["THETA"] * quantity * multiplier,
    })

result = pd.DataFrame(rows)
st.subheader("Calcolo opzioni")
st.dataframe(result, hide_index=True, use_container_width=True, column_config={
    "Strike": st.column_config.NumberColumn(format="%.2f"),
    "Teorico": st.column_config.NumberColumn(format="%.4f"),
    "P/L teorico": st.column_config.NumberColumn(format="%.2f"),
    "Delta": st.column_config.NumberColumn(format="%.3f"),
    "Gamma": st.column_config.NumberColumn(format="%.5f"),
    "Vega": st.column_config.NumberColumn(format="%.3f"),
    "THETA": st.column_config.NumberColumn(format="%.3f"),
})

if not result.empty:
    st.subheader("Totale strategia")
    totals = result[["P/L teorico", "Delta", "Gamma", "Vega", "THETA"]].sum()
    metrics = st.columns(5)
    for col, label in zip(metrics, totals.index):
        col.metric(label, f"{totals[label]:,.3f}")
    st.caption("THETA = valore teorico con un giorno in meno alla scadenza − valore teorico odierno. È espresso al giorno e include quantità, Buy/Sell e moltiplicatore.")
