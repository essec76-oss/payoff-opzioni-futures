from datetime import date
from math import erf
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Payoff Opzioni e Futures", layout="wide")
st.title("Payoff Opzioni e Futures")
try:
    catalog = pd.read_csv("sottostanti.csv")
except FileNotFoundError:
    st.error("Manca il file sottostanti.csv nella stessa cartella dell'app.")
    st.stop()

EXPIRY = date(2026, 11, 20)
DEFAULT = pd.DataFrame([
    {"Escludi": False, "Strumento": "Opzione", "Lato": "Short", "Tipo": "Put", "Quantita": 1, "Strike": 600.0, "Scadenza opzione": EXPIRY, "Premio/Ingresso": 3.9396, "IV %": 26.5},
    {"Escludi": False, "Strumento": "Opzione", "Lato": "Short", "Tipo": "Call", "Quantita": 1, "Strike": 1200.0, "Scadenza opzione": EXPIRY, "Premio/Ingresso": 2.6898, "IV %": 48.1},
])
if "legs_source" not in st.session_state:
    st.session_state.legs_source = DEFAULT.copy()

labels = (catalog["Ticker"] + " - " + catalog["Nome"]).tolist()
with st.sidebar:
    st.header("Parametri strategia")
    name = st.text_input("Nome strategia", "KE Dec 2026 - Short Strangle")
    default_index = labels.index("KE - Wheat Kansas") if "KE - Wheat Kansas" in labels else 0
    selected = st.selectbox("Sottostante", labels, index=default_index)
    prod = catalog.iloc[labels.index(selected)]
    ticker = prod["Ticker"]
    multiplier = float(prod["PL_Multiplier"])
    future_price = st.number_input("Prezzo sottostante corrente", value=721.75, step=0.25, format="%.4f")
    st.subheader("Curve da mostrare")
    show_analysis = st.checkbox("Mostra P/L alla data di analisi", True)
    show_now = st.checkbox("Mostra P/L teorico At Now", True)
    show_components = st.checkbox("Mostra payoff singole gambe", False)
    st.divider()
    valuation_date = st.date_input("Data di valutazione", date(2026, 8, 7))
    analysis_date = st.date_input("Data di analisi", EXPIRY)
    atm_iv = st.number_input("ATM IV globale (%)", value=30.7, min_value=0.01, step=0.1)
    risk_free = st.number_input("Tasso risk-free (%)", value=4.0, min_value=0.0, step=0.1)
    commissions = st.number_input("Commissioni totali", value=0.0, step=0.01)
    price_min = st.number_input("Range minimo", value=450.0, step=1.0)
    price_max = st.number_input("Range massimo", value=1350.0, step=1.0)
    if st.button("Ripristina esempio KE"):
        st.session_state.legs_source = DEFAULT.copy()
        if "editor" in st.session_state:
            del st.session_state["editor"]
        st.rerun()

st.caption("Multiplier e specifiche contrattuali sono caricati dal catalogo e non appaiono nel grafico.")
st.subheader("Gambe")
legs = st.data_editor(
    st.session_state.legs_source,
    num_rows="dynamic",
    use_container_width=True,
    key="editor",
    column_config={
        "Escludi": st.column_config.CheckboxColumn("Escludi", default=False),
        "Strumento": st.column_config.SelectboxColumn(options=["Opzione", "Future"], required=True),
        "Lato": st.column_config.SelectboxColumn(options=["Long", "Short"], required=True),
        "Tipo": st.column_config.SelectboxColumn(options=["Call", "Put", "Future"], required=True),
        "Quantita": st.column_config.NumberColumn(min_value=0.0, step=1.0, required=True),
        "Strike": st.column_config.NumberColumn(step=0.25),
        "Scadenza opzione": st.column_config.DateColumn(format="DD/MM/YYYY", required=True),
        "Premio/Ingresso": st.column_config.NumberColumn(step=0.0001, format="%.4f", required=True),
        "IV %": st.column_config.NumberColumn(step=0.1),
    },
)

required = ["Escludi", "Strumento", "Lato", "Tipo", "Quantita", "Strike", "Scadenza opzione", "Premio/Ingresso"]
if price_max <= price_min or legs.empty or legs[required].isnull().any().any() or analysis_date < valuation_date or not (show_analysis or show_now):
    st.error("Controlla range, date e dati obbligatori.")
    st.stop()
active = legs[~legs["Escludi"]].copy()
if active.empty:
    st.warning("Tutte le gambe sono escluse.")
    st.stop()

def expiry(row):
    return pd.to_datetime(row["Scadenza opzione"]).date()

def cdf(x):
    return 0.5 * (1 + np.vectorize(erf)(x / np.sqrt(2)))

def black76(f, k, t, s, r, typ):
    intrinsic = np.maximum(f - k, 0) if typ == "Call" else np.maximum(k - f, 0)
    if t <= 0:
        return intrinsic
    f = np.maximum(f, 1e-12)
    vs = s * np.sqrt(t)
    d1 = (np.log(f / k) + 0.5 * s * s * t) / vs
    d2 = d1 - vs
    disc = np.exp(-r * t)
    if typ == "Call":
        return disc * (f * cdf(d1) - k * cdf(d2))
    return disc * (k * cdf(-d2) - f * cdf(-d1))

def leg_pnl(p, row, target):
    sign = 1 if row["Lato"] == "Long" else -1
    q = sign * float(row["Quantita"])
    entry = float(row["Premio/Ingresso"])
    if row["Strumento"] == "Future":
        return q * (p - entry) * multiplier
    t = max((expiry(row) - target).days, 0) / 365
    value = black76(p, float(row["Strike"]), t, atm_iv / 100, risk_free / 100, row["Tipo"])
    return q * (value - entry) * multiplier

def total(p, target):
    result = np.zeros_like(p, dtype=float)
    for _, row in active.iterrows():
        result += leg_pnl(p, row, target)
    return result - commissions

def break_evens(x, y):
    values = []
    for i in range(len(x) - 1):
        if y[i] == 0:
            values.append(x[i])
        elif y[i] * y[i + 1] < 0:
            values.append(x[i] + (x[i + 1] - x[i]) * (-y[i]) / (y[i + 1] - y[i]))
    return sorted(set(round(v, 4) for v in values))

def testo_break_even(valori):
    if not valori:
        return "Nessun break-even nel range selezionato"
    return " • ".join(f"{valore:,.2f}" for valore in valori)

def pop():
    t = (analysis_date - valuation_date).days / 365
    if t <= 0:
        return 100.0 if total(np.array([future_price]), analysis_date)[0] > 0 else 0.0
    sigma = atm_iv / 100
    spread = max(12 * sigma * np.sqrt(t), 0.25)
    low = max(future_price * np.exp(-spread), 1e-8)
    high = future_price * np.exp(spread)
    edges = np.concatenate(([0], np.geomspace(low, high, 12000), [np.inf]))
    z = (np.log(edges[1:-1] / future_price) + 0.5 * sigma * sigma * t) / (sigma * np.sqrt(t))
    mass = np.diff(np.concatenate(([0], cdf(z), [1])))
    mid = np.empty(len(mass))
    mid[0], mid[-1] = low / 2, high * 2
    mid[1:-1] = np.sqrt(edges[1:-2] * edges[2:-1])
    return float(np.sum(mass[total(mid, analysis_date) > 0]) * 100)

prices = np.linspace(price_min, price_max, 2000)
now = total(prices, valuation_date)
analysis = total(prices, analysis_date)
nowbe = break_evens(prices, now)
anabe = break_evens(prices, analysis)

left, right = st.columns([3, 1])
with left:
    fig = go.Figure()
    if show_components:
        for _, row in active.iterrows():
            fig.add_trace(go.Scatter(x=prices, y=leg_pnl(prices, row, analysis_date), mode="lines", opacity=0.3, line={"dash": "dot"}, name=f"{row['Lato']} {row['Tipo']} {row['Strike']}"))
    if show_analysis:
        fig.add_trace(go.Scatter(x=prices, y=analysis, mode="lines", line={"width": 4, "color": "#00a878"}, name="P/L data analisi"))
    if show_now:
        fig.add_trace(go.Scatter(x=prices, y=now, mode="lines", line={"width": 2, "dash": "dash", "color": "#3b82f6"}, name="P/L At Now"))
    fig.add_hline(y=0, line_color="gray")
    fig.add_vline(x=future_price, line_dash="dash", line_color="#e69f00", annotation_text=f"{ticker} {future_price:.2f}")
    fig.update_layout(title=f"{name} - {selected}", xaxis_title=f"Prezzo {ticker}", yaxis_title="P/L", hovermode="x unified", margin={"l": 10, "r": 10, "t": 50, "b": 10})
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("Metriche")
    st.metric("Sottostante", ticker)
    st.metric("Gambe incluse", f"{len(active)} / {len(legs)}")
    st.metric("PoP teorica data analisi", f"{pop():.1f}%")
    if show_analysis:
        st.metric("P/L data analisi", f"{total(np.array([future_price]), analysis_date)[0]:,.2f}")
    if show_now:
        st.metric("P/L At Now", f"{total(np.array([future_price]), valuation_date)[0]:,.2f}")
    st.divider()
    st.subheader("Break-even")
    if show_analysis:
        st.info(f"**Alla data di analisi**\n\n{testo_break_even(anabe)}")
    if show_now:
        st.info(f"**At Now**\n\n{testo_break_even(nowbe)}")

levels = sorted(set([price_min, future_price, price_max] + active.loc[active["Strumento"] == "Opzione", "Strike"].astype(float).tolist() + nowbe + anabe))
scenarios = pd.DataFrame({"Prezzo": levels})
if show_analysis:
    scenarios["P/L data analisi"] = total(np.array(levels), analysis_date)
if show_now:
    scenarios["P/L At Now"] = total(np.array(levels), valuation_date)
st.subheader("Scenari")
st.dataframe(scenarios.style.format({column: "{:.2f}" for column in scenarios.columns}), use_container_width=True)
st.download_button("Scarica le gambe in CSV", legs.to_csv(index=False).encode(), "gambe_strategia.csv", "text/csv")
