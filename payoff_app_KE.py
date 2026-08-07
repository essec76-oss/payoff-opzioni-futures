import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Payoff Opzioni e Futures", layout="wide")
st.title("Payoff Opzioni e Futures")
st.caption("Calcolo del payoff a scadenza con tabella modificabile")

DEFAULT_LEGS = pd.DataFrame([
    {"Strumento": "Opzione", "Lato": "Short", "Tipo": "Put", "Quantita": 1, "Strike": 600.0, "Premio/Ingresso": 3.9396, "IV %": 26.5, "Multiplier": 50.0},
    {"Strumento": "Opzione", "Lato": "Short", "Tipo": "Call", "Quantita": 1, "Strike": 1200.0, "Premio/Ingresso": 2.6898, "IV %": 48.1, "Multiplier": 50.0},
])

if "legs" not in st.session_state:
    st.session_state.legs = DEFAULT_LEGS.copy()

with st.sidebar:
    st.header("Parametri strategia")
    name = st.text_input("Nome strategia", "KE Dec 2026 - Short Strangle")
    underlying = st.text_input("Future sottostante", "KE Dec 2026")
    future_price = st.number_input("Prezzo future corrente", value=721.75, step=0.25, format="%.4f")
    atm_iv = st.number_input("ATM IV (%)", value=30.7, step=0.1)
    commissions = st.number_input("Commissioni totali", value=0.0, step=0.01)
    price_min = st.number_input("Range minimo", value=450.0, step=1.0)
    price_max = st.number_input("Range massimo", value=1350.0, step=1.0)
    if st.button("Ripristina esempio KE"):
        st.session_state.legs = DEFAULT_LEGS.copy()
        st.rerun()

st.subheader("Gambe")
legs = st.data_editor(
    st.session_state.legs,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Strumento": st.column_config.SelectboxColumn(options=["Opzione", "Future"], required=True),
        "Lato": st.column_config.SelectboxColumn(options=["Long", "Short"], required=True),
        "Tipo": st.column_config.SelectboxColumn(options=["Call", "Put", "Future"], required=True),
        "Quantita": st.column_config.NumberColumn(min_value=0.0, step=1.0, required=True),
        "Strike": st.column_config.NumberColumn(step=0.25),
        "Premio/Ingresso": st.column_config.NumberColumn(step=0.0001, format="%.4f", required=True),
        "IV %": st.column_config.NumberColumn(step=0.1),
        "Multiplier": st.column_config.NumberColumn(min_value=0.0001, step=1.0, required=True),
    },
    key="editor",
)
st.session_state.legs = legs

if price_max <= price_min:
    st.error("Il range massimo deve essere superiore al range minimo.")
    st.stop()

required = ["Strumento", "Lato", "Tipo", "Quantita", "Strike", "Premio/Ingresso", "Multiplier"]
if legs.empty or legs[required].isnull().any().any():
    st.warning("Completa tutti i dati obbligatori della tabella.")
    st.stop()

def pnl_leg(prices, row):
    sign = 1 if row["Lato"] == "Long" else -1
    q = sign * float(row["Quantita"])
    mult = float(row["Multiplier"])
    entry = float(row["Premio/Ingresso"])
    if row["Strumento"] == "Future":
        return q * (prices - entry) * mult
    if row["Tipo"] == "Call":
        intrinsic = np.maximum(prices - float(row["Strike"]), 0)
    else:
        intrinsic = np.maximum(float(row["Strike"]) - prices, 0)
    return q * (intrinsic - entry) * mult

def breakevens(x, y):
    result = []
    for i in range(len(x) - 1):
        if y[i] == 0:
            result.append(x[i])
        elif y[i] * y[i + 1] < 0:
            result.append(x[i] + (x[i + 1] - x[i]) * (-y[i]) / (y[i + 1] - y[i]))
    return sorted(set(round(v, 4) for v in result))

prices = np.linspace(price_min, price_max, 2000)
total = np.zeros_like(prices)
for _, row in legs.iterrows():
    total += pnl_leg(prices, row)
total -= commissions
bes = breakevens(prices, total)

chart_col, metrics_col = st.columns([3, 1])
with chart_col:
    fig = go.Figure()
    for _, row in legs.iterrows():
        fig.add_trace(go.Scatter(
            x=prices, y=pnl_leg(prices, row), mode="lines", opacity=0.35,
            line={"dash": "dot"}, name=f"{row['Lato']} {row['Tipo']} {row['Strike']}"
        ))
    fig.add_trace(go.Scatter(x=prices, y=total, mode="lines", line={"width": 4, "color": "#00a878"}, name="P/L totale"))
    fig.add_hline(y=0, line_color="gray")
    fig.add_vline(x=future_price, line_dash="dash", line_color="#e69f00", annotation_text=f"Future {future_price:.2f}")
    for be in bes:
        fig.add_vline(x=be, line_dash="dot", line_color="#d55e00", annotation_text=f"BE {be:.4f}")
    fig.update_layout(
        title=f"{name} - Payoff a scadenza",
        xaxis_title=f"Prezzo {underlying} a scadenza",
        yaxis_title="P/L (in base al multiplier)",
        hovermode="x unified",
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
    )
    st.plotly_chart(fig, use_container_width=True)

with metrics_col:
    st.subheader("Metriche")
    st.metric("Future corrente", f"{future_price:.4f}")
    st.metric("ATM IV", f"{atm_iv:.1f}%")
    st.metric("P/L max nel range", f"{total.max():,.2f}")
    st.metric("P/L min nel range", f"{total.min():,.2f}")
    st.write("**Breakeven**")
    st.write(", ".join(f"{x:.4f}" for x in bes) if bes else "Nessuno nel range")

scenario_levels = sorted(set([price_min, future_price, price_max] + legs.loc[legs["Strumento"] == "Opzione", "Strike"].astype(float).tolist() + bes))
scenarios = pd.DataFrame({"Prezzo a scadenza": scenario_levels})
scenario_total = np.zeros(len(scenarios))
for _, row in legs.iterrows():
    scenario_total += pnl_leg(scenarios["Prezzo a scadenza"].to_numpy(), row)
scenarios["P/L totale"] = scenario_total - commissions

st.subheader("Scenari")
st.dataframe(scenarios.style.format({"Prezzo a scadenza": "{:.4f}", "P/L totale": "{:.2f}"}), use_container_width=True)
st.download_button("Scarica le gambe in CSV", legs.to_csv(index=False).encode("utf-8"), "gambe_strategia.csv", "text/csv")
st.info("Questa versione calcola il payoff a scadenza. Nel prossimo step possiamo aggiungere Black-76, P/L a T+N e greche.")
