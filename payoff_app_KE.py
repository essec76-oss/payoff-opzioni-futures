from datetime import date
from math import erf, pi
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Payoff Opzioni", layout="wide")
st.title("Payoff Opzioni")
try:
    catalog = pd.read_csv("sottostanti.csv")
except FileNotFoundError:
    st.error("Manca il file sottostanti.csv.")
    st.stop()

EXP = date(2026, 11, 20)
DEFAULT = pd.DataFrame([
    {"Escludi": False, "Del": False, "Acquisto/Vendita": "Vendita", "Call/Put": "Put", "Numero opzioni": 1, "Strike": 600.0, "Vol opz (%)": 26.5, "Premio": 3.9396, "Scadenza": EXP},
    {"Escludi": False, "Del": False, "Acquisto/Vendita": "Vendita", "Call/Put": "Call", "Numero opzioni": 1, "Strike": 1200.0, "Vol opz (%)": 48.1, "Premio": 2.6898, "Scadenza": EXP},
])
labels = (catalog["Ticker"] + " - " + catalog["Nome"]).tolist()
default_product = "KE - Wheat Kansas" if "KE - Wheat Kansas" in labels else labels[0]
if "legs_source" not in st.session_state:
    st.session_state.legs_source = DEFAULT.copy()
for key, value in {"name":"Strategia opzioni", "product":default_product, "spot":721.75, "start":date(2026,8,7), "analysis":EXP, "showa":True, "shows":True, "rf":4.0, "comm":0.0, "pmin":450.0, "pmax":1350.0}.items():
    st.session_state.setdefault(key, value)

with st.sidebar:
    st.header("Salva / Carica strategia")
    uploaded = st.file_uploader("File strategia (.json)", type="json")
    load_col, save_col = st.columns(2)
    load_clicked = load_col.button("Carica strategia", use_container_width=True)
    save_area = save_col.empty()
    if load_clicked:
        if uploaded is None:
            st.warning("Scegli prima un file JSON.")
        else:
            try:
                saved = json.load(uploaded)
                st.session_state.legs_source = pd.DataFrame(saved["opzioni"])
                st.session_state.legs_source["Scadenza"] = pd.to_datetime(st.session_state.legs_source["Scadenza"]).dt.date
                if "Del" not in st.session_state.legs_source:
                    st.session_state.legs_source["Del"] = False
                for key, value in saved["parametri"].items():
                    st.session_state[key] = pd.to_datetime(value).date() if key in ["start", "analysis"] else value
                st.session_state.pop("editor", None)
                st.rerun()
            except Exception as exc:
                st.error(f"File non valido: {exc}")
    st.divider()
    st.header("Parametri strategia")
    name = st.text_input("Nome strategia", key="name")
    selected = st.selectbox("Sottostante", labels, key="product")
    product = catalog.iloc[labels.index(selected)]
    ticker, multiplier = product["Ticker"], float(product["PL_Multiplier"])
    spot = st.number_input("Prezzo sottostante corrente", step=0.25, format="%.4f", key="spot")
    st.subheader("Date e time decay")
    start = st.date_input("Data di partenza delle operazioni", key="start")
    analysis = st.date_input("Data di analisi", key="analysis")
    st.subheader("Curve da mostrare")
    showa = st.checkbox("Mostra P/L alla data di analisi", key="showa")
    shows = st.checkbox("Mostra P/L alla data di partenza", key="shows")
    rf = st.number_input("Tasso risk-free (%)", min_value=0.0, step=0.1, key="rf")
    comm = st.number_input("Commissioni totali", step=0.01, key="comm")
    pmin = st.number_input("Range minimo", step=1.0, key="pmin")
    pmax = st.number_input("Range massimo", step=1.0, key="pmax")
    if st.button("Ripristina esempio KE"):
        st.session_state.legs_source = DEFAULT.copy()
        st.session_state.pop("editor", None)
        st.rerun()

if analysis < start or pmax <= pmin:
    st.error("Controlla date e range prezzi.")
    st.stop()

def cdf(x): return 0.5 * (1 + np.vectorize(erf)(x / np.sqrt(2)))
def pdf(x): return np.exp(-x*x/2) / np.sqrt(2*pi)
def black76(f, k, t, sigma, rate, option_type):
    intrinsic = np.maximum(f-k, 0) if option_type == "Call" else np.maximum(k-f, 0)
    if t <= 0: return intrinsic
    f = np.maximum(f, 1e-12)
    vs = sigma * np.sqrt(t)
    d1 = (np.log(f/k) + 0.5*sigma*sigma*t) / vs
    d2 = d1 - vs
    disc = np.exp(-rate*t)
    return disc*(f*cdf(d1)-k*cdf(d2)) if option_type == "Call" else disc*(k*cdf(-d2)-f*cdf(-d1))
def calc_greeks(row):
    t = max((pd.to_datetime(row["Scadenza"]).date() - start).days, 0) / 365
    sigma, strike = float(row["Vol opz (%)"])/100, float(row["Strike"])
    quantity = float(row["Numero opzioni"]) * multiplier * (1 if row["Acquisto/Vendita"] == "Acquisto" else -1)
    if t <= 0: return pd.Series({"Delta":0.0,"Gamma":0.0,"Vega (per 1%)":0.0,"Theta (al giorno)":0.0})
    vs = sigma*np.sqrt(t)
    d1 = (np.log(spot/strike)+0.5*sigma*sigma*t)/vs
    disc = np.exp(-(rf/100)*t)
    delta = disc*(cdf(d1) if row["Call/Put"] == "Call" else -cdf(-d1))
    gamma = disc*pdf(d1)/(spot*vs)
    vega = disc*spot*pdf(d1)*np.sqrt(t)*0.01
    today = black76(np.array([spot]), strike, t, sigma, rf/100, row["Call/Put"])[0]
    tomorrow = black76(np.array([spot]), strike, max(t-1/365, 0), sigma, rf/100, row["Call/Put"])[0]
    return pd.Series({"Delta":quantity*delta,"Gamma":quantity*gamma,"Vega (per 1%)":quantity*vega,"Theta (al giorno)":quantity*(tomorrow-today)})

st.subheader("Opzioni")
st.caption("Spunta Escludi per disattivare una riga. Spunta Del e premi il pulsante per eliminarla definitivamente.")
editor_data = st.session_state.legs_source.copy()
if "Del" not in editor_data: editor_data["Del"] = False
editor_data["DTE mancanti"] = editor_data["Scadenza"].apply(lambda d: max((pd.to_datetime(d).date()-start).days, 0) if pd.notna(d) else None)
editor_data[["Delta","Gamma","Vega (per 1%)","Theta (al giorno)"]] = editor_data.apply(calc_greeks, axis=1)
legs = st.data_editor(editor_data, num_rows="dynamic", use_container_width=True, key="editor", disabled=["DTE mancanti","Delta","Gamma","Vega (per 1%)","Theta (al giorno)"], column_config={
    "Escludi":st.column_config.CheckboxColumn("Escludi", default=False),
    "Del":st.column_config.CheckboxColumn("Del", default=False, help="Seleziona questa riga da eliminare"),
    "Acquisto/Vendita":st.column_config.SelectboxColumn(options=["Acquisto","Vendita"], required=True),
    "Call/Put":st.column_config.SelectboxColumn(options=["Call","Put"], required=True),
    "Numero opzioni":st.column_config.NumberColumn(min_value=0.0, step=1.0),
    "Strike":st.column_config.NumberColumn(step=0.25),
    "Vol opz (%)":st.column_config.NumberColumn(min_value=0.01, step=0.1),
    "Premio":st.column_config.NumberColumn(step=0.0001, format="%.4f"),
    "Scadenza":st.column_config.DateColumn(format="DD/MM/YYYY"),
    "DTE mancanti":st.column_config.NumberColumn(format="%d"),
    "Delta":st.column_config.NumberColumn(format="%.2f"),
    "Gamma":st.column_config.NumberColumn(format="%.4f"),
    "Vega (per 1%)":st.column_config.NumberColumn(format="%.2f"),
    "Theta (al giorno)":st.column_config.NumberColumn(format="%.2f"),
})
legs = legs.drop(columns=["DTE mancanti","Delta","Gamma","Vega (per 1%)","Theta (al giorno)"], errors="ignore")
if st.button("Elimina righe selezionate", type="primary"):
    if not legs["Del"].any():
        st.warning("Spunta Del su almeno una riga.")
    else:
        st.session_state.legs_source = legs[~legs["Del"]].drop(columns=["Del"], errors="ignore").reset_index(drop=True)
        st.session_state.pop("editor", None)
        st.rerun()

required=["Escludi","Del","Acquisto/Vendita","Call/Put","Numero opzioni","Strike","Vol opz (%)","Premio","Scadenza"]
if legs.empty or legs[required].isnull().any().any(): st.error("Completa tutte le righe."); st.stop()
active = legs[~legs["Escludi"]].drop(columns=["Del"], errors="ignore").copy()
if active.empty: st.warning("Tutte le opzioni sono escluse."); st.stop()
def pnl(prices, row, target):
    sign = 1 if row["Acquisto/Vendita"] == "Acquisto" else -1
    t = max((pd.to_datetime(row["Scadenza"]).date()-target).days, 0)/365
    return sign*float(row["Numero opzioni"])*(black76(prices,float(row["Strike"]),t,float(row["Vol opz (%)"])/100,rf/100,row["Call/Put"])-float(row["Premio"]))*multiplier
def total(prices, target): return sum((pnl(prices,row,target) for _,row in active.iterrows()),np.zeros_like(prices,dtype=float))-comm
def bes(prices, values): return sorted(set(round(prices[i]+(prices[i+1]-prices[i])*(-values[i])/(values[i+1]-values[i]),4) for i in range(len(prices)-1) if values[i]*values[i+1]<0))
def be_text(values): return "Nessun break-even nel range selezionato" if not values else " • ".join(f"{x:,.2f}" for x in values)
active_greeks = active.apply(calc_greeks, axis=1)
sums = active_greeks.sum()
st.subheader("Totali greche")
a,b,c,d = st.columns(4)
a.metric("Delta totale", f"{sums['Delta']:,.2f}")
b.metric("Gamma totale", f"{sums['Gamma']:,.4f}")
c.metric("Vega totale (+1% IV)", f"{sums['Vega (per 1%)']:,.2f}")
d.metric("Theta totale (1 giorno)", f"{sums['Theta (al giorno)']:,.2f}")
prices=np.linspace(pmin,pmax,2000); start_curve=total(prices,start); analysis_curve=total(prices,analysis); start_be=bes(prices,start_curve); analysis_be=bes(prices,analysis_curve)
left,right=st.columns([3,1])
with left:
    fig=go.Figure()
    if showa: fig.add_trace(go.Scatter(x=prices,y=analysis_curve,mode="lines",line={"width":4,"color":"#00a878"},name="P/L data analisi"))
    if shows: fig.add_trace(go.Scatter(x=prices,y=start_curve,mode="lines",line={"width":2,"dash":"dash","color":"#3b82f6"},name="P/L data partenza"))
    fig.add_hline(y=0,line_color="gray")
    fig.add_vline(x=spot,line_dash="dash",line_color="#e69f00",annotation_text=f"{ticker} {spot:.2f}")
    fig.update_layout(title=f"{name} - {selected}",xaxis_title=f"Prezzo {ticker}",yaxis_title="P/L",hovermode="x unified")
    st.plotly_chart(fig,use_container_width=True)
with right:
    st.subheader("Metriche")
    st.metric("Sottostante",ticker); st.metric("Opzioni incluse",f"{len(active)} / {len(legs)}")
    st.metric("P/L data analisi",f"{total(np.array([spot]),analysis)[0]:,.2f}")
    st.metric("P/L data partenza",f"{total(np.array([spot]),start)[0]:,.2f}")
    st.divider(); st.subheader("Break-even")
    if showa: st.info(f"**Alla data di analisi**\n\n{be_text(analysis_be)}")
    if shows: st.info(f"**Alla data di partenza**\n\n{be_text(start_be)}")

out=legs.drop(columns=["Del"],errors="ignore").copy()
out["Scadenza"]=out["Scadenza"].apply(lambda x:pd.to_datetime(x).date().isoformat())
save_data={"opzioni":out.to_dict("records"),"parametri":{"name":name,"product":selected,"spot":spot,"start":start.isoformat(),"analysis":analysis.isoformat(),"showa":showa,"shows":shows,"rf":rf,"comm":comm,"pmin":pmin,"pmax":pmax}}
save_area.download_button("Salva strategia",json.dumps(save_data,ensure_ascii=False,indent=2).encode(),"strategia_opzioni.json","application/json",use_container_width=True)

