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
    st.error("File sottostanti.csv non trovato nella cartella dell'app.")
    st.stop()

DEFAULT_EXPIRY = date(2026, 11, 20)
DEFAULT_LEGS = pd.DataFrame([
    {"Escludi": False, "Strumento": "Opzione", "Lato": "Short", "Tipo": "Put", "Quantita": 1, "Strike": 600.0, "Scadenza opzione": DEFAULT_EXPIRY, "Premio/Ingresso": 3.9396, "IV %": 26.5},
    {"Escludi": False, "Strumento": "Opzione", "Lato": "Short", "Tipo": "Call", "Quantita": 1, "Strike": 1200.0, "Scadenza opzione": DEFAULT_EXPIRY, "Premio/Ingresso": 2.6898, "IV %": 48.1},
])
if "legs" not in st.session_state:
    st.session_state.legs = DEFAULT_LEGS.copy()

labels = (catalog["Ticker"] + " - " + catalog["Nome"]).tolist()
with st.sidebar:
    st.header("Parametri strategia")
    name = st.text_input("Nome strategia", "KE Dec 2026 - Short Strangle")
    selected = st.selectbox("Sottostante", labels, index=labels.index("KE - Wheat Kansas") if "KE - Wheat Kansas" in labels else 0)
    product = catalog.iloc[labels.index(selected)]
    ticker, multiplier = product["Ticker"], float(product["PL_Multiplier"])
    future_price = st.number_input("Prezzo sottostante corrente", value=721.75, step=0.25, format="%.4f")
    st.subheader("Curve da mostrare")
    show_analysis = st.checkbox("Mostra P/L alla data di analisi", True)
    show_now = st.checkbox("Mostra P/L teorico At Now", True)
    show_components = st.checkbox("Mostra payoff singole gambe", False)
    st.divider()
    st.subheader("Date e Black-76")
    valuation_date = st.date_input("Data di valutazione", date(2026, 8, 7))
    analysis_date = st.date_input("Data di analisi", DEFAULT_EXPIRY)
    atm_iv = st.number_input("ATM IV globale (%)", value=30.7, step=0.1, min_value=0.01)
    risk_free = st.number_input("Tasso risk-free (%)", value=4.0, step=0.1, min_value=0.0)
    st.divider()
    commissions = st.number_input("Commissioni totali", value=0.0, step=0.01)
    price_min = st.number_input("Range minimo", value=450.0, step=1.0)
    price_max = st.number_input("Range massimo", value=1350.0, step=1.0)
    if st.button("Ripristina esempio KE"):
        st.session_state.legs = DEFAULT_LEGS.copy(); st.rerun()

st.caption("Il multiplier e le specifiche del contratto sono caricati automaticamente dal catalogo del sottostante e restano fuori dal grafico.")
st.subheader("Gambe")
legs = st.data_editor(st.session_state.legs, num_rows="dynamic", use_container_width=True, column_config={
    "Escludi": st.column_config.CheckboxColumn("Escludi", default=False),
    "Strumento": st.column_config.SelectboxColumn(options=["Opzione", "Future"], required=True),
    "Lato": st.column_config.SelectboxColumn(options=["Long", "Short"], required=True),
    "Tipo": st.column_config.SelectboxColumn(options=["Call", "Put", "Future"], required=True),
    "Quantita": st.column_config.NumberColumn(min_value=0.0, step=1.0, required=True),
    "Strike": st.column_config.NumberColumn(step=0.25),
    "Scadenza opzione": st.column_config.DateColumn(format="DD/MM/YYYY", required=True),
    "Premio/Ingresso": st.column_config.NumberColumn(step=0.0001, format="%.4f", required=True),
    "IV %": st.column_config.NumberColumn(step=0.1),
}, key="editor")
st.session_state.legs = legs
required = ["Escludi","Strumento","Lato","Tipo","Quantita","Strike","Scadenza opzione","Premio/Ingresso"]
if price_max <= price_min or legs.empty or legs[required].isnull().any().any() or analysis_date < valuation_date or (not show_analysis and not show_now):
    st.error("Controlla parametri, date e dati obbligatori."); st.stop()
active = legs[~legs["Escludi"]].copy()
if active.empty: st.warning("Tutte le gambe sono escluse."); st.stop()

def exp(row): return pd.to_datetime(row["Scadenza opzione"]).date()
def ncdf(x): return .5*(1+np.vectorize(erf)(x/np.sqrt(2)))
def black76(f,k,t,s,r,typ):
    intrinsic=np.maximum(f-k,0) if typ=="Call" else np.maximum(k-f,0)
    if t<=0:return intrinsic
    f=np.maximum(f,1e-12); vs=s*np.sqrt(t); d1=(np.log(f/k)+.5*s*s*t)/vs; d2=d1-vs; disc=np.exp(-r*t)
    return disc*(f*ncdf(d1)-k*ncdf(d2)) if typ=="Call" else disc*(k*ncdf(-d2)-f*ncdf(-d1))
def pnl(p,row,target):
    q=(1 if row["Lato"]=="Long" else -1)*float(row["Quantita"]); entry=float(row["Premio/Ingresso"])
    if row["Strumento"]=="Future": return q*(p-entry)*multiplier
    rem=max((exp(row)-target).days,0)/365
    return q*(black76(p,float(row["Strike"]),rem,atm_iv/100,risk_free/100,row["Tipo"])-entry)*multiplier
def total(p,target): return sum((pnl(p,row,target) for _,row in active.iterrows()),np.zeros_like(p,dtype=float))-commissions
def crossings(x,y):
    return sorted(set(round(x[i]+(x[i+1]-x[i])*(-y[i])/(y[i+1]-y[i]),4) for i in range(len(x)-1) if y[i]*y[i+1]<0))
def pop():
    t=(analysis_date-valuation_date).days/365
    if t<=0:return 100. if total(np.array([future_price]),analysis_date)[0]>0 else 0.
    s=atm_iv/100; low=max(future_price*np.exp(-max(12*s*np.sqrt(t),.25)),1e-8); high=future_price*np.exp(max(12*s*np.sqrt(t),.25))
    edges=np.concatenate(([0],np.geomspace(low,high,12000),[np.inf])); z=(np.log(edges[1:-1]/future_price)+.5*s*s*t)/(s*np.sqrt(t)); masses=np.diff(np.concatenate(([0],ncdf(z),[1])))
    mids=np.empty(len(masses)); mids[0]=low/2; mids[-1]=high*2; mids[1:-1]=np.sqrt(edges[1:-2]*edges[2:-1])
    return float(np.sum(masses[total(mids,analysis_date)>0])*100)

prices=np.linspace(price_min,price_max,2000); now=total(prices,valuation_date); ana=total(prices,analysis_date); nowbe=crossings(prices,now); anabe=crossings(prices,ana); popv=pop()
left,right=st.columns([3,1])
with left:
    fig=go.Figure()
    if show_components:
        for _,row in active.iterrows(): fig.add_trace(go.Scatter(x=prices,y=pnl(prices,row,analysis_date),mode="lines",opacity=.3,line={"dash":"dot"},name=f"{row['Lato']} {row['Tipo']} {row['Strike']}"))
    if show_analysis: fig.add_trace(go.Scatter(x=prices,y=ana,mode="lines",line={"width":4,"color":"#00a878"},name="P/L data analisi"))
    if show_now: fig.add_trace(go.Scatter(x=prices,y=now,mode="lines",line={"width":2,"dash":"dash","color":"#3b82f6"},name="P/L At Now"))
    fig.add_hline(y=0,line_color="gray"); fig.add_vline(x=future_price,line_dash="dash",line_color="#e69f00",annotation_text=f"{ticker} {future_price:.2f}")
    fig.update_layout(title=f"{name} - {selected}",xaxis_title=f"Prezzo {ticker}",yaxis_title="P/L",hovermode="x unified",margin={"l":10,"r":10,"t":50,"b":10}); st.plotly_chart(fig,use_container_width=True)
with right:
    st.subheader("Metriche"); st.metric("Sottostante",ticker); st.metric("Gambe incluse",f"{len(active)} / {len(legs)}"); st.metric("PoP teorica data analisi",f"{popv:.1f}%")
    if show_analysis: st.metric("P/L data analisi",f"{total(np.array([future_price]),analysis_date)[0]:,.2f}")
    if show_now: st.metric("P/L At Now",f"{total(np.array([future_price]),valuation_date)[0]:,.2f}")
levels=sorted(set([price_min,future_price,price_max]+active.loc[active["Strumento"]=="Opzione","Strike"].astype(float).tolist()+anabe+nowbe)); scenarios=pd.DataFrame({"Prezzo":levels})
if show_analysis:scenarios["P/L data analisi"]=total(np.array(levels),analysis_date)
if show_now:scenarios["P/L At Now"]=total(np.array(levels),valuation_date)
st.subheader("Scenari"); st.dataframe(scenarios.style.format({c:"{:.2f}" for c in scenarios.columns}),use_container_width=True)
st.download_button("Scarica le gambe in CSV",legs.to_csv(index=False).encode(),"gambe_strategia.csv","text/csv")
