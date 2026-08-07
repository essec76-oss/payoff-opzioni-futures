# Versione V12: aggiunge il salvataggio/caricamento completo in JSON.
# Per mantenere tutte le funzionalita della V11, sostituisci interamente
# payoff_app_KE.py con questo file.

from datetime import date
from math import erf
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
    st.error("Manca il file sottostanti.csv nella stessa cartella dell'app.")
    st.stop()

EXPIRY = date(2026, 11, 20)
DEFAULT = pd.DataFrame([
    {"Acquisto/Vendita":"Vendita","Call/Put":"Put","Numero opzioni":1,"Strike":600.0,"Vol opz (%)":26.5,"Premio":3.9396,"Scadenza":EXPIRY},
    {"Acquisto/Vendita":"Vendita","Call/Put":"Call","Numero opzioni":1,"Strike":1200.0,"Vol opz (%)":48.1,"Premio":2.6898,"Scadenza":EXPIRY},
])
labels = (catalog["Ticker"] + " - " + catalog["Nome"]).tolist()
default_product = "KE - Wheat Kansas" if "KE - Wheat Kansas" in labels else labels[0]

if "legs_source" not in st.session_state:
    st.session_state.legs_source = DEFAULT.copy()
for key, value in {
    "strategy_name":"Strategia opzioni", "selected_product":default_product,
    "future_price":721.75, "start_date":date(2026,8,7), "analysis_date":EXPIRY,
    "show_analysis":True, "show_start":True, "show_components":False,
    "risk_free":4.0, "commissions":0.0, "price_min":450.0, "price_max":1350.0,
}.items():
    if key not in st.session_state: st.session_state[key] = value

# Caricamento: viene eseguito prima di creare i widget.
with st.sidebar:
    st.header("Salva / Carica strategia")
    uploaded = st.file_uploader("Carica file strategia (.json)", type=["json"])
    if uploaded is not None and st.button("Carica strategia", key="load_button"):
        try:
            saved = json.load(uploaded)
            st.session_state.legs_source = pd.DataFrame(saved["opzioni"])
            st.session_state.legs_source["Scadenza"] = pd.to_datetime(st.session_state.legs_source["Scadenza"]).dt.date
            settings = saved["parametri"]
            for key in ["strategy_name","selected_product","future_price","show_analysis","show_start","show_components","risk_free","commissions","price_min","price_max"]:
                if key in settings: st.session_state[key] = settings[key]
            st.session_state["start_date"] = pd.to_datetime(settings["start_date"]).date()
            st.session_state["analysis_date"] = pd.to_datetime(settings["analysis_date"]).date()
            st.session_state.pop("editor", None)
            st.rerun()
        except Exception as exc:
            st.error(f"File non valido: {exc}")
    st.divider()
    st.header("Parametri strategia")
    name = st.text_input("Nome strategia", key="strategy_name")
    selected = st.selectbox("Sottostante", labels, key="selected_product")
    prod = catalog.iloc[labels.index(selected)]
    ticker, multiplier = prod["Ticker"], float(prod["PL_Multiplier"])
    future_price = st.number_input("Prezzo sottostante corrente", step=0.25, format="%.4f", key="future_price")
    st.divider()
    st.subheader("Date e time decay")
    start_date = st.date_input("Data di partenza delle operazioni", key="start_date")
    analysis_date = st.date_input("Data di analisi", key="analysis_date")
    st.divider()
    st.subheader("Curve da mostrare")
    show_analysis = st.checkbox("Mostra P/L alla data di analisi", key="show_analysis")
    show_start = st.checkbox("Mostra P/L alla data di partenza", key="show_start")
    show_components = st.checkbox("Mostra payoff singole opzioni", key="show_components")
    risk_free = st.number_input("Tasso risk-free (%)", min_value=0.0, step=0.1, key="risk_free")
    commissions = st.number_input("Commissioni totali", step=0.01, key="commissions")
    price_min = st.number_input("Range minimo", step=1.0, key="price_min")
    price_max = st.number_input("Range massimo", step=1.0, key="price_max")
    if st.button("Ripristina esempio KE"):
        st.session_state.legs_source = DEFAULT.copy()
        st.session_state.pop("editor", None)
        st.rerun()

if analysis_date < start_date:
    st.error("La data di analisi non può essere precedente alla data di partenza.")
    st.stop()
st.subheader("Opzioni")
st.caption("Tutte le righe sono opzioni. Il DTE è calcolato automaticamente dalla data di partenza alla scadenza della singola riga.")
editor_data = st.session_state.legs_source.copy()
editor_data["DTE mancanti"] = editor_data["Scadenza"].apply(lambda d: max((pd.to_datetime(d).date()-start_date).days,0) if pd.notna(d) else None)
legs = st.data_editor(editor_data, num_rows="dynamic", use_container_width=True, key="editor", disabled=["DTE mancanti"], column_config={
    "Acquisto/Vendita":st.column_config.SelectboxColumn(options=["Acquisto","Vendita"],required=True),
    "Call/Put":st.column_config.SelectboxColumn(options=["Call","Put"],required=True),
    "Numero opzioni":st.column_config.NumberColumn(min_value=0.0,step=1.0,required=True),
    "Strike":st.column_config.NumberColumn(step=0.25,required=True),
    "Vol opz (%)":st.column_config.NumberColumn(min_value=0.01,step=0.1,format="%.1f",required=True),
    "Premio":st.column_config.NumberColumn(step=0.0001,format="%.4f",required=True),
    "Scadenza":st.column_config.DateColumn(format="DD/MM/YYYY",required=True),
    "DTE mancanti":st.column_config.NumberColumn(format="%d"),
})
legs = legs.drop(columns=["DTE mancanti"], errors="ignore")
required=["Acquisto/Vendita","Call/Put","Numero opzioni","Strike","Vol opz (%)","Premio","Scadenza"]
if price_max<=price_min or legs.empty or legs[required].isnull().any().any() or not(show_analysis or show_start):
    st.error("Controlla range, date e dati obbligatori di ogni opzione.")
    st.stop()

def expiry(row): return pd.to_datetime(row["Scadenza"]).date()
def cdf(x): return .5*(1+np.vectorize(erf)(x/np.sqrt(2)))
def black76(f,k,t,sigma,r,typ):
    intrinsic=np.maximum(f-k,0) if typ=="Call" else np.maximum(k-f,0)
    if t<=0:return intrinsic
    f=np.maximum(f,1e-12); vs=sigma*np.sqrt(t); d1=(np.log(f/k)+.5*sigma*sigma*t)/vs; d2=d1-vs; d=np.exp(-r*t)
    return d*(f*cdf(d1)-k*cdf(d2)) if typ=="Call" else d*(k*cdf(-d2)-f*cdf(-d1))
def leg_pnl(p,row,target):
    sign=1 if row["Acquisto/Vendita"]=="Acquisto" else -1
    t=max((expiry(row)-target).days,0)/365
    value=black76(p,float(row["Strike"]),t,float(row["Vol opz (%)"])/100,risk_free/100,row["Call/Put"])
    return sign*float(row["Numero opzioni"])*(value-float(row["Premio"]))*multiplier
def total(p,target):
    result=np.zeros_like(p,dtype=float)
    for _,row in legs.iterrows(): result+=leg_pnl(p,row,target)
    return result-commissions
def bes(x,y):
    vals=[]
    for i in range(len(x)-1):
        if y[i]*y[i+1]<0: vals.append(x[i]+(x[i+1]-x[i])*(-y[i])/(y[i+1]-y[i]))
    return sorted(set(round(v,4) for v in vals))
def be_text(v): return "Nessun break-even nel range selezionato" if not v else " • ".join(f"{x:,.2f}" for x in v)
def pop():
    t=(analysis_date-start_date).days/365
    if t<=0:return 100. if total(np.array([future_price]),analysis_date)[0]>0 else 0.
    sigma=float(np.average(legs["Vol opz (%)"]))/100; spread=max(12*sigma*np.sqrt(t),.25); lo=max(future_price*np.exp(-spread),1e-8); hi=future_price*np.exp(spread)
    edges=np.concatenate(([0],np.geomspace(lo,hi,12000),[np.inf])); z=(np.log(edges[1:-1]/future_price)+.5*sigma*sigma*t)/(sigma*np.sqrt(t)); mass=np.diff(np.concatenate(([0],cdf(z),[1])))
    mid=np.empty(len(mass)); mid[0]=lo/2;mid[-1]=hi*2;mid[1:-1]=np.sqrt(edges[1:-2]*edges[2:-1])
    return float(np.sum(mass[total(mid,analysis_date)>0])*100)

prices=np.linspace(price_min,price_max,2000); start_curve=total(prices,start_date); analysis_curve=total(prices,analysis_date); start_be=bes(prices,start_curve); analysis_be=bes(prices,analysis_curve)
left,right=st.columns([3,1])
with left:
    fig=go.Figure()
    if show_components:
        for _,row in legs.iterrows():fig.add_trace(go.Scatter(x=prices,y=leg_pnl(prices,row,analysis_date),mode="lines",opacity=.3,line={"dash":"dot"},name=f"{row['Acquisto/Vendita']} {row['Call/Put']} {row['Strike']}"))
    if show_analysis:fig.add_trace(go.Scatter(x=prices,y=analysis_curve,mode="lines",line={"width":4,"color":"#00a878"},name="P/L data analisi"))
    if show_start:fig.add_trace(go.Scatter(x=prices,y=start_curve,mode="lines",line={"width":2,"dash":"dash","color":"#3b82f6"},name="P/L data partenza"))
    fig.add_hline(y=0,line_color="gray");fig.add_vline(x=future_price,line_dash="dash",line_color="#e69f00",annotation_text=f"{ticker} {future_price:.2f}")
    fig.update_layout(title=f"{name} - {selected}",xaxis_title=f"Prezzo {ticker}",yaxis_title="P/L",hovermode="x unified",margin={"l":10,"r":10,"t":50,"b":10});st.plotly_chart(fig,use_container_width=True)
with right:
    st.subheader("Metriche");st.metric("Sottostante",ticker);st.metric("Numero opzioni",str(len(legs)));st.metric("PoP teorica data analisi",f"{pop():.1f}%")
    if show_analysis:st.metric("P/L data analisi",f"{total(np.array([future_price]),analysis_date)[0]:,.2f}")
    if show_start:st.metric("P/L data partenza",f"{total(np.array([future_price]),start_date)[0]:,.2f}")
    st.divider();st.subheader("Break-even")
    if show_analysis:st.info(f"**Alla data di analisi**\n\n{be_text(analysis_be)}")
    if show_start:st.info(f"**Alla data di partenza**\n\n{be_text(start_be)}")

saved_legs=legs.copy();saved_legs["Scadenza"]=saved_legs["Scadenza"].apply(lambda x: pd.to_datetime(x).date().isoformat())
save_data={"versione":12,"opzioni":saved_legs.to_dict(orient="records"),"parametri":{"strategy_name":name,"selected_product":selected,"future_price":future_price,"start_date":start_date.isoformat(),"analysis_date":analysis_date.isoformat(),"show_analysis":show_analysis,"show_start":show_start,"show_components":show_components,"risk_free":risk_free,"commissions":commissions,"price_min":price_min,"price_max":price_max}}
st.download_button("Salva strategia completa (.json)",json.dumps(save_data,ensure_ascii=False,indent=2).encode("utf-8"),"strategia_opzioni.json","application/json")
st.download_button("Scarica solo le opzioni (.csv)",legs.to_csv(index=False).encode(),"opzioni_strategia.csv","text/csv")
