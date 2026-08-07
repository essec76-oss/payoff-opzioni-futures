from datetime import date
from math import erf
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Payoff Opzioni", layout="wide")
st.title("Payoff Opzioni")
try:
    catalog = pd.read_csv("sottostanti.csv")
except FileNotFoundError:
    st.error("Manca il file sottostanti.csv nella stessa cartella dell'app.")
    st.stop()

EXPIRY = date(2026, 11, 20)
DEFAULT = pd.DataFrame([
    {"Acquisto/Vendita": "Vendita", "Call/Put": "Put", "Numero opzioni": 1, "Strike": 600.0, "Vol opz (%)": 26.5, "Premio": 3.9396, "Scadenza": EXPIRY},
    {"Acquisto/Vendita": "Vendita", "Call/Put": "Call", "Numero opzioni": 1, "Strike": 1200.0, "Vol opz (%)": 48.1, "Premio": 2.6898, "Scadenza": EXPIRY},
])
if "legs_source" not in st.session_state:
    st.session_state.legs_source = DEFAULT.copy()

labels = (catalog["Ticker"] + " - " + catalog["Nome"]).tolist()
with st.sidebar:
    st.header("Parametri strategia")
    name = st.text_input("Nome strategia", "Strategia opzioni")
    selected = st.selectbox("Sottostante", labels, index=labels.index("KE - Wheat Kansas") if "KE - Wheat Kansas" in labels else 0)
    prod = catalog.iloc[labels.index(selected)]
    ticker, multiplier = prod["Ticker"], float(prod["PL_Multiplier"])
    future_price = st.number_input("Prezzo sottostante corrente", value=721.75, step=0.25, format="%.4f")
    st.divider()
    st.subheader("Date e time decay")
    start_date = st.date_input("Data di partenza delle operazioni", date(2026, 8, 7), help="Data da cui viene valorizzata la curva iniziale e calcolato il DTE.")
    analysis_date = st.date_input("Data di analisi", EXPIRY, help="Data futura a cui vuoi simulare il P/L.")
    st.divider()
    st.subheader("Curve da mostrare")
    show_analysis = st.checkbox("Mostra P/L alla data di analisi", True)
    show_start = st.checkbox("Mostra P/L alla data di partenza", True)
    show_components = st.checkbox("Mostra payoff singole opzioni", False)
    risk_free = st.number_input("Tasso risk-free (%)", value=4.0, min_value=0.0, step=0.1)
    commissions = st.number_input("Commissioni totali", value=0.0, step=0.01)
    price_min = st.number_input("Range minimo", value=450.0, step=1.0)
    price_max = st.number_input("Range massimo", value=1350.0, step=1.0)
    if st.button("Ripristina esempio KE"):
        st.session_state.legs_source = DEFAULT.copy()
        st.session_state.pop("editor", None)
        st.rerun()

if analysis_date < start_date:
    st.error("La data di analisi non può essere precedente alla data di partenza.")
    st.stop()

st.subheader("Opzioni")
st.caption("Tutte le righe sono opzioni finanziarie. Il DTE è calcolato automaticamente dalla data di partenza alla scadenza della singola riga.")
editor_data = st.session_state.legs_source.copy()
if "Scadenza" in editor_data:
    editor_data["DTE mancanti"] = editor_data["Scadenza"].apply(lambda d: max((pd.to_datetime(d).date() - start_date).days, 0) if pd.notna(d) else None)
else:
    editor_data["DTE mancanti"] = None
legs = st.data_editor(
    editor_data, num_rows="dynamic", use_container_width=True, key="editor",
    disabled=["DTE mancanti"],
    column_config={
        "Acquisto/Vendita": st.column_config.SelectboxColumn(options=["Acquisto", "Vendita"], required=True),
        "Call/Put": st.column_config.SelectboxColumn(options=["Call", "Put"], required=True),
        "Numero opzioni": st.column_config.NumberColumn(min_value=0.0, step=1.0, required=True),
        "Strike": st.column_config.NumberColumn(step=0.25, required=True),
        "Vol opz (%)": st.column_config.NumberColumn(min_value=0.01, step=0.1, format="%.1f", required=True),
        "Premio": st.column_config.NumberColumn(step=0.0001, format="%.4f", required=True),
        "Scadenza": st.column_config.DateColumn(format="DD/MM/YYYY", required=True),
        "DTE mancanti": st.column_config.NumberColumn(format="%d"),
    },
)
legs = legs.drop(columns=["DTE mancanti"], errors="ignore")
required = ["Acquisto/Vendita", "Call/Put", "Numero opzioni", "Strike", "Vol opz (%)", "Premio", "Scadenza"]
if price_max <= price_min or legs.empty or legs[required].isnull().any().any() or not (show_analysis or show_start):
    st.error("Controlla range, date e dati obbligatori di ogni opzione.")
    st.stop()

def expiry(row): return pd.to_datetime(row["Scadenza"]).date()
def cdf(x): return 0.5 * (1 + np.vectorize(erf)(x / np.sqrt(2)))
def black76(f, k, t, sigma, r, typ):
    intrinsic = np.maximum(f-k, 0) if typ == "Call" else np.maximum(k-f, 0)
    if t <= 0: return intrinsic
    f = np.maximum(f, 1e-12)
    vs = sigma * np.sqrt(t)
    d1 = (np.log(f/k) + 0.5*sigma*sigma*t) / vs
    d2 = d1 - vs
    disc = np.exp(-r*t)
    return disc*(f*cdf(d1)-k*cdf(d2)) if typ == "Call" else disc*(k*cdf(-d2)-f*cdf(-d1))
def leg_pnl(p, row, target):
    sign = 1 if row["Acquisto/Vendita"] == "Acquisto" else -1
    t = max((expiry(row)-target).days, 0) / 365
    theoretical = black76(p, float(row["Strike"]), t, float(row["Vol opz (%)"])/100, risk_free/100, row["Call/Put"])
    return sign * float(row["Numero opzioni"]) * (theoretical-float(row["Premio"])) * multiplier
def total(p, target):
    result = np.zeros_like(p, dtype=float)
    for _, row in legs.iterrows(): result += leg_pnl(p, row, target)
    return result - commissions
def break_evens(x, y):
    out=[]
    for i in range(len(x)-1):
        if y[i] == 0: out.append(x[i])
        elif y[i]*y[i+1] < 0: out.append(x[i]+(x[i+1]-x[i])*(-y[i])/(y[i+1]-y[i]))
    return sorted(set(round(v,4) for v in out))
def be_text(values): return "Nessun break-even nel range selezionato" if not values else " • ".join(f"{v:,.2f}" for v in values)
def pop():
    t = (analysis_date-start_date).days/365
    if t <= 0: return 100.0 if total(np.array([future_price]),analysis_date)[0] > 0 else 0.0
    sigma = float(np.average(legs["Vol opz (%)"])) / 100
    spread=max(12*sigma*np.sqrt(t),.25); low=max(future_price*np.exp(-spread),1e-8); high=future_price*np.exp(spread)
    edges=np.concatenate(([0],np.geomspace(low,high,12000),[np.inf]))
    z=(np.log(edges[1:-1]/future_price)+.5*sigma*sigma*t)/(sigma*np.sqrt(t))
    mass=np.diff(np.concatenate(([0],cdf(z),[1])))
    mid=np.empty(len(mass)); mid[0]=low/2; mid[-1]=high*2; mid[1:-1]=np.sqrt(edges[1:-2]*edges[2:-1])
    return float(np.sum(mass[total(mid,analysis_date)>0])*100)

prices=np.linspace(price_min,price_max,2000)
start_curve=total(prices,start_date)
analysis_curve=total(prices,analysis_date)
start_be=break_evens(prices,start_curve)
analysis_be=break_evens(prices,analysis_curve)
left,right=st.columns([3,1])
with left:
    fig=go.Figure()
    if show_components:
        for _,row in legs.iterrows(): fig.add_trace(go.Scatter(x=prices,y=leg_pnl(prices,row,analysis_date),mode="lines",opacity=.3,line={"dash":"dot"},name=f"{row['Acquisto/Vendita']} {row['Call/Put']} {row['Strike']}"))
    if show_analysis: fig.add_trace(go.Scatter(x=prices,y=analysis_curve,mode="lines",line={"width":4,"color":"#00a878"},name="P/L data analisi"))
    if show_start: fig.add_trace(go.Scatter(x=prices,y=start_curve,mode="lines",line={"width":2,"dash":"dash","color":"#3b82f6"},name="P/L data partenza"))
    fig.add_hline(y=0,line_color="gray")
    fig.add_vline(x=future_price,line_dash="dash",line_color="#e69f00",annotation_text=f"{ticker} {future_price:.2f}")
    fig.update_layout(title=f"{name} - {selected}",xaxis_title=f"Prezzo {ticker}",yaxis_title="P/L",hovermode="x unified",margin={"l":10,"r":10,"t":50,"b":10})
    st.plotly_chart(fig,use_container_width=True)
with right:
    st.subheader("Metriche")
    st.metric("Sottostante",ticker)
    st.metric("Numero opzioni",f"{len(legs)}")
    st.metric("PoP teorica data analisi",f"{pop():.1f}%")
    if show_analysis: st.metric("P/L data analisi",f"{total(np.array([future_price]),analysis_date)[0]:,.2f}")
    if show_start: st.metric("P/L data partenza",f"{total(np.array([future_price]),start_date)[0]:,.2f}")
    st.divider(); st.subheader("Break-even")
    if show_analysis: st.info(f"**Alla data di analisi**\n\n{be_text(analysis_be)}")
    if show_start: st.info(f"**Alla data di partenza**\n\n{be_text(start_be)}")
levels=sorted(set([price_min,future_price,price_max]+legs["Strike"].astype(float).tolist()+start_be+analysis_be))
scenarios=pd.DataFrame({"Prezzo":levels})
if show_analysis: scenarios["P/L data analisi"]=total(np.array(levels),analysis_date)
if show_start: scenarios["P/L data partenza"]=total(np.array(levels),start_date)
st.subheader("Scenari")
st.dataframe(scenarios.style.format({c:"{:.2f}" for c in scenarios.columns}),use_container_width=True)
st.download_button("Scarica le opzioni in CSV",legs.to_csv(index=False).encode(),"opzioni_strategia.csv","text/csv")
