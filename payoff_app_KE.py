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
COLUMNS = ["Escludi", "Del", "Acquisto/Vendita", "Call/Put", "Numero opzioni", "Strike", "Vol opz (%)", "Premio", "Scadenza"]
DEFAULT = pd.DataFrame([
    [False, False, "Vendita", "Put", 1, 600.0, 26.5, 3.9396, EXP],
    [False, False, "Vendita", "Call", 1, 1200.0, 48.1, 2.6898, EXP],
], columns=COLUMNS)
labels = (catalog["Ticker"] + " - " + catalog["Nome"]).tolist()
default_product = "KE - Wheat Kansas" if "KE - Wheat Kansas" in labels else labels[0]

if "legs" not in st.session_state:
    st.session_state.legs = DEFAULT.copy()
for key, value in {
    "name":"Strategia opzioni", "product":default_product, "spot":721.75,
    "atmiv":30.0, "start":date(2026,8,7), "analysis":EXP,
    "rf":4.0, "comm":0.0, "pmin":450.0, "pmax":1350.0,
    "show_analysis":True, "show_start":True,
}.items():
    st.session_state.setdefault(key, value)

with st.sidebar:
    st.header("Salva / Carica strategia")
    upload = st.file_uploader("File strategia (.json)", type="json")
    load_col, save_col = st.columns(2)
    load = load_col.button("Carica", use_container_width=True)
    save_slot = save_col.empty()
    if load:
        if upload is None:
            st.warning("Scegli prima un file JSON.")
        else:
            try:
                saved = json.load(upload)
                df = pd.DataFrame(saved["opzioni"])
                for col in COLUMNS:
                    if col not in df:
                        df[col] = False if col in ["Escludi", "Del"] else None
                df["Scadenza"] = pd.to_datetime(df["Scadenza"], errors="coerce").dt.date
                st.session_state.legs = df[COLUMNS]
                for key, value in saved["parametri"].items():
                    st.session_state[key] = pd.to_datetime(value).date() if key in ["start", "analysis"] else value
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
    atmiv = st.number_input("ATM IV globale (%)", min_value=0.01, step=0.1, key="atmiv")
    start = st.date_input("Data di partenza delle operazioni", key="start")
    analysis = st.date_input("Data di analisi", key="analysis")
    show_analysis = st.checkbox("Mostra P/L alla data di analisi", key="show_analysis")
    show_start = st.checkbox("Mostra P/L alla data di partenza", key="show_start")
    rf = st.number_input("Tasso risk-free (%)", min_value=0.0, step=0.1, key="rf")
    comm = st.number_input("Commissioni totali", step=0.01, key="comm")
    pmin = st.number_input("Range minimo", step=1.0, key="pmin")
    pmax = st.number_input("Range massimo", step=1.0, key="pmax")
    if st.button("Ripristina esempio KE"):
        st.session_state.legs = DEFAULT.copy()
        st.rerun()

if analysis < start or pmax <= pmin:
    st.error("Controlla date e range prezzi.")
    st.stop()

def cdf(x): return 0.5 * (1 + np.vectorize(erf)(x / np.sqrt(2)))
def pdf(x): return np.exp(-x*x/2) / np.sqrt(2*pi)
def valid(row):
    try:
        return pd.notna(row["Scadenza"]) and float(row["Strike"]) > 0 and float(row["Vol opz (%)"]) > 0 and float(row["Numero opzioni"]) > 0 and float(row["Premio"]) >= 0
    except Exception:
        return False
def black76(f,k,t,s,r,typ):
    intrinsic = np.maximum(f-k,0) if typ=="Call" else np.maximum(k-f,0)
    if t <= 0: return intrinsic
    f=np.maximum(f,1e-12); v=s*np.sqrt(t); d1=(np.log(f/k)+0.5*s*s*t)/v; d2=d1-v; disc=np.exp(-r*t)
    return disc*(f*cdf(d1)-k*cdf(d2)) if typ=="Call" else disc*(k*cdf(-d2)-f*cdf(-d1))
def calc_greeks(row):
    if not valid(row): return pd.Series({"Delta":np.nan,"Gamma":np.nan,"Vega (per 1%)":np.nan,"Theta (al giorno)":np.nan})
    t=max((pd.to_datetime(row["Scadenza"]).date()-start).days,0)/365
    if t<=0: return pd.Series({"Delta":0.0,"Gamma":0.0,"Vega (per 1%)":0.0,"Theta (al giorno)":0.0})
    s=float(row["Vol opz (%)"])/100; k=float(row["Strike"]); q=float(row["Numero opzioni"])*multiplier*(1 if row["Acquisto/Vendita"]=="Acquisto" else -1)
    v=s*np.sqrt(t); d1=(np.log(spot/k)+0.5*s*s*t)/v; disc=np.exp(-(rf/100)*t)
    delta=disc*(cdf(d1) if row["Call/Put"]=="Call" else -cdf(-d1)); gamma=disc*pdf(d1)/(spot*v); vega=disc*spot*pdf(d1)*np.sqrt(t)*0.01
    today=black76(np.array([spot]),k,t,s,rf/100,row["Call/Put"])[0]
    tomorrow=black76(np.array([spot]),k,max(t-1/365,0),s,rf/100,row["Call/Put"])[0]
    return pd.Series({"Delta":q*delta,"Gamma":q*gamma,"Vega (per 1%)":q*vega,"Theta (al giorno)":q*(tomorrow-today)})

st.subheader("Opzioni")
st.caption("Compila o modifica le righe, poi premi Aggiorna calcoli. Le righe incomplete non causano errori e mostrano celle vuote nelle greche.")
display = st.session_state.legs.copy()
display["DTE mancanti"] = display["Scadenza"].apply(lambda x:max((pd.to_datetime(x).date()-start).days,0) if pd.notna(x) else np.nan)
display[["Delta","Gamma","Vega (per 1%)","Theta (al giorno)"]] = display.apply(calc_greeks, axis=1)
with st.form("editor_form"):
    edited = st.data_editor(display, num_rows="dynamic", use_container_width=True, disabled=["DTE mancanti","Delta","Gamma","Vega (per 1%)","Theta (al giorno)"], column_config={
        "Escludi":st.column_config.CheckboxColumn("Escludi"), "Del":st.column_config.CheckboxColumn("Del"),
        "Acquisto/Vendita":st.column_config.SelectboxColumn(options=["Acquisto","Vendita"]), "Call/Put":st.column_config.SelectboxColumn(options=["Call","Put"]),
        "Scadenza":st.column_config.DateColumn(format="DD/MM/YYYY"), "DTE mancanti":st.column_config.NumberColumn(format="%d"),
        "Delta":st.column_config.NumberColumn(format="%.2f"), "Gamma":st.column_config.NumberColumn(format="%.4f"),
        "Vega (per 1%)":st.column_config.NumberColumn(format="%.2f"), "Theta (al giorno)":st.column_config.NumberColumn(format="%.2f"),
    })
    update = st.form_submit_button("Aggiorna calcoli")
if update:
    st.session_state.legs = edited[COLUMNS].copy()
    st.rerun()
if st.button("Elimina righe selezionate", type="primary"):
    if not st.session_state.legs["Del"].any(): st.warning("Spunta Del su almeno una riga.")
    else:
        st.session_state.legs = st.session_state.legs[~st.session_state.legs["Del"]].drop(columns="Del").assign(Del=False).reset_index(drop=True)
        st.rerun()

legs=st.session_state.legs.copy(); active=legs[(~legs["Escludi"]) & legs.apply(valid,axis=1)].drop(columns="Del")
def pnl(x,row,target):
    t=max((pd.to_datetime(row["Scadenza"]).date()-target).days,0)/365; sign=1 if row["Acquisto/Vendita"]=="Acquisto" else -1
    return sign*float(row["Numero opzioni"])*(black76(x,float(row["Strike"]),t,float(row["Vol opz (%)"])/100,rf/100,row["Call/Put"])-float(row["Premio"]))*multiplier
def total(x,target): return sum((pnl(x,row,target) for _,row in active.iterrows()),np.zeros_like(x,dtype=float))-comm
def pop():
    t=(analysis-start).days/365
    if t<=0:return 100.0 if total(np.array([spot]),analysis)[0]>0 else 0.0
    s=atmiv/100; z=max(12*s*np.sqrt(t),.25); lo=max(spot*np.exp(-z),1e-8); hi=spot*np.exp(z)
    edges=np.concatenate(([0],np.geomspace(lo,hi,12000),[np.inf])); q=(np.log(edges[1:-1]/spot)+.5*s*s*t)/(s*np.sqrt(t)); mass=np.diff(np.r_[0,cdf(q),1]); mids=np.r_[lo/2,np.sqrt(edges[1:-2]*edges[2:-1]),hi*2]
    return float(mass[total(mids,analysis)>0].sum()*100)

if active.empty: st.warning("Inserisci almeno un'opzione valida e non esclusa."); st.stop()
greeks=active.apply(calc_greeks,axis=1).sum()
st.subheader("Totali greche")
a,b,c,d=st.columns(4);a.metric("Delta totale",f"{greeks['Delta']:,.2f}");b.metric("Gamma totale",f"{greeks['Gamma']:,.4f}");c.metric("Vega totale (+1% IV)",f"{greeks['Vega (per 1%)']:,.2f}");d.metric("Theta totale (1 giorno)",f"{greeks['Theta (al giorno)']:,.2f}")
x=np.linspace(pmin,pmax,2000); ys=total(x,start); ya=total(x,analysis)
fig=go.Figure()
if show_analysis:fig.add_trace(go.Scatter(x=x,y=ya,name="P/L data analisi",line={"width":4,"color":"#00a878"}))
if show_start:fig.add_trace(go.Scatter(x=x,y=ys,name="P/L data partenza",line={"dash":"dash","color":"#3b82f6"}))
fig.add_hline(y=0,line_color="gray");fig.add_vline(x=spot,line_dash="dash",line_color="#e69f00",annotation_text=f"{ticker} {spot:.2f}");fig.update_layout(hovermode="x unified",xaxis_title=f"Prezzo {ticker}",yaxis_title="P/L")
st.plotly_chart(fig,use_container_width=True)
st.metric("PoP data analisi",f"{pop():.1f}%",help=f"Calcolata con ATM IV globale {atmiv:.1f}%")
out=legs.drop(columns="Del").copy();out["Scadenza"]=out["Scadenza"].apply(lambda x:pd.to_datetime(x).date().isoformat() if pd.notna(x) else None)
saved={"opzioni":out.to_dict("records"),"parametri":{"name":name,"product":selected,"spot":spot,"atmiv":atmiv,"start":start.isoformat(),"analysis":analysis.isoformat(),"rf":rf,"comm":comm,"pmin":pmin,"pmax":pmax,"show_analysis":show_analysis,"show_start":show_start}}
save_slot.download_button("Salva",json.dumps(saved,ensure_ascii=False,indent=2).encode(),"strategia_opzioni.json","application/json",use_container_width=True)
