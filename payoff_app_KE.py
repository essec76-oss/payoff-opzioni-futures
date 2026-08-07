from datetime import date
from math import erf, pi
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Payoff Opzioni", layout="wide")
st.title("Payoff Opzioni")
try: catalog = pd.read_csv("sottostanti.csv")
except FileNotFoundError: st.error("Manca il file sottostanti.csv."); st.stop()
EXP = date(2026,11,20)
DEFAULT = pd.DataFrame([
 {"Escludi":False,"Acquisto/Vendita":"Vendita","Call/Put":"Put","Numero opzioni":1,"Strike":600.,"Vol opz (%)":26.5,"Premio":3.9396,"Scadenza":EXP},
 {"Escludi":False,"Acquisto/Vendita":"Vendita","Call/Put":"Call","Numero opzioni":1,"Strike":1200.,"Vol opz (%)":48.1,"Premio":2.6898,"Scadenza":EXP}])
labels=(catalog.Ticker+" - "+catalog.Nome).tolist(); default="KE - Wheat Kansas" if "KE - Wheat Kansas" in labels else labels[0]
if "legs_source" not in st.session_state: st.session_state.legs_source=DEFAULT.copy()
for k,v in {"name":"Strategia opzioni","product":default,"spot":721.75,"start":date(2026,8,7),"analysis":EXP,"showa":True,"shows":True,"rf":4.,"comm":0.,"pmin":450.,"pmax":1350.}.items(): st.session_state.setdefault(k,v)

with st.sidebar:
 st.header("Salva / Carica strategia")
 up=st.file_uploader("File strategia (.json)",type="json")
 c1,c2=st.columns(2)
 load=c1.button("Carica strategia",use_container_width=True)
 if load:
  if up is None: st.warning("Scegli prima un file JSON.")
  else:
   try:
    x=json.load(up); st.session_state.legs_source=pd.DataFrame(x["opzioni"]); st.session_state.legs_source.Scadenza=pd.to_datetime(st.session_state.legs_source.Scadenza).dt.date
    for k,v in x["parametri"].items(): st.session_state[k]=pd.to_datetime(v).date() if k in ["start","analysis"] else v
    st.session_state.pop("editor",None); st.rerun()
   except Exception as e: st.error(f"File non valido: {e}")
 st.divider(); st.header("Parametri strategia")
 name=st.text_input("Nome strategia",key="name"); sel=st.selectbox("Sottostante",labels,key="product"); prod=catalog.iloc[labels.index(sel)]; ticker,mult=prod.Ticker,float(prod.PL_Multiplier)
 spot=st.number_input("Prezzo sottostante corrente",step=.25,format="%.4f",key="spot")
 st.subheader("Date e time decay"); start=st.date_input("Data di partenza delle operazioni",key="start"); analysis=st.date_input("Data di analisi",key="analysis")
 st.subheader("Curve da mostrare"); showa=st.checkbox("Mostra P/L alla data di analisi",key="showa"); shows=st.checkbox("Mostra P/L alla data di partenza",key="shows")
 rf=st.number_input("Tasso risk-free (%)",min_value=0.,step=.1,key="rf"); comm=st.number_input("Commissioni totali",step=.01,key="comm"); pmin=st.number_input("Range minimo",step=1.,key="pmin"); pmax=st.number_input("Range massimo",step=1.,key="pmax")
 if st.button("Ripristina esempio KE"): st.session_state.legs_source=DEFAULT.copy();st.session_state.pop("editor",None);st.rerun()
if analysis<start or pmax<=pmin: st.error("Controlla date e range prezzi.");st.stop()
def cdf(x): return .5*(1+np.vectorize(erf)(x/np.sqrt(2)))
def pdf(x): return np.exp(-x*x/2)/np.sqrt(2*pi)
def b76(f,k,t,s,r,typ):
 intr=np.maximum(f-k,0) if typ=="Call" else np.maximum(k-f,0)
 if t<=0:return intr
 f=np.maximum(f,1e-12);v=s*np.sqrt(t);d1=(np.log(f/k)+.5*s*s*t)/v;d2=d1-v;d=np.exp(-r*t)
 return d*(f*cdf(d1)-k*cdf(d2)) if typ=="Call" else d*(k*cdf(-d2)-f*cdf(-d1))
def greeks(row):
 t=max((pd.to_datetime(row.Scadenza).date()-start).days,0)/365;s=float(row["Vol opz (%)"])/100;k=float(row.Strike);q=float(row["Numero opzioni"])*(1 if row["Acquisto/Vendita"]=="Acquisto" else -1)*mult
 if t<=0:return pd.Series({"Delta":0.,"Gamma":0.,"Vega (per 1%)":0.,"Theta (al giorno)":0.})
 v=s*np.sqrt(t);d1=(np.log(spot/k)+.5*s*s*t)/v;disc=np.exp(-(rf/100)*t);delta=disc*(cdf(d1) if row["Call/Put"]=="Call" else -cdf(-d1));gamma=disc*pdf(d1)/(spot*v);vega=disc*spot*pdf(d1)*np.sqrt(t)*.01
 now=b76(np.array([spot]),k,t,s,rf/100,row["Call/Put"])[0];tomorrow=b76(np.array([spot]),k,max(t-1/365,0),s,rf/100,row["Call/Put"])[0]
 return pd.Series({"Delta":q*delta,"Gamma":q*gamma,"Vega (per 1%)":q*vega,"Theta (al giorno)":q*(tomorrow-now)})

st.subheader("Opzioni"); st.caption("Spunta Escludi per disattivare una riga. Delta, Gamma, Vega e Theta sono calcolati automaticamente.")
ed=st.session_state.legs_source.copy();ed["DTE mancanti"]=ed.Scadenza.apply(lambda d:max((pd.to_datetime(d).date()-start).days,0) if pd.notna(d) else None)
ed[["Delta","Gamma","Vega (per 1%)","Theta (al giorno)"]]=ed.apply(greeks,axis=1)
legs=st.data_editor(ed,num_rows="dynamic",use_container_width=True,key="editor",disabled=["DTE mancanti","Delta","Gamma","Vega (per 1%)","Theta (al giorno)"],column_config={"Escludi":st.column_config.CheckboxColumn("Escludi",default=False),"Acquisto/Vendita":st.column_config.SelectboxColumn(options=["Acquisto","Vendita"],required=True),"Call/Put":st.column_config.SelectboxColumn(options=["Call","Put"],required=True),"Numero opzioni":st.column_config.NumberColumn(min_value=0.,step=1.),"Strike":st.column_config.NumberColumn(step=.25),"Vol opz (%)":st.column_config.NumberColumn(min_value=.01,step=.1),"Premio":st.column_config.NumberColumn(step=.0001,format="%.4f"),"Scadenza":st.column_config.DateColumn(format="DD/MM/YYYY"),"DTE mancanti":st.column_config.NumberColumn(format="%d"),"Delta":st.column_config.NumberColumn(format="%.2f"),"Gamma":st.column_config.NumberColumn(format="%.4f"),"Vega (per 1%)":st.column_config.NumberColumn(format="%.2f"),"Theta (al giorno)":st.column_config.NumberColumn(format="%.2f")})
legs=legs.drop(columns=["DTE mancanti","Delta","Gamma","Vega (per 1%)","Theta (al giorno)"],errors="ignore")
req=["Escludi","Acquisto/Vendita","Call/Put","Numero opzioni","Strike","Vol opz (%)","Premio","Scadenza"]
if legs.empty or legs[req].isnull().any().any():st.error("Completa tutte le righe.");st.stop()
active=legs[~legs.Escludi].copy()
if active.empty:st.warning("Tutte le opzioni sono escluse.");st.stop()
def pnl(p,row,target):
 sign=1 if row["Acquisto/Vendita"]=="Acquisto" else -1;t=max((pd.to_datetime(row.Scadenza).date()-target).days,0)/365
 return sign*float(row["Numero opzioni"])*(b76(p,float(row.Strike),t,float(row["Vol opz (%)"])/100,rf/100,row["Call/Put"])-float(row.Premio))*mult
def tot(p,target):return sum((pnl(p,r,target) for _,r in active.iterrows()),np.zeros_like(p,dtype=float))-comm
def bes(x,y):return sorted(set(round(x[i]+(x[i+1]-x[i])*(-y[i])/(y[i+1]-y[i]),4) for i in range(len(x)-1) if y[i]*y[i+1]<0))
def txt(v):return "Nessun break-even nel range selezionato" if not v else " • ".join(f"{z:,.2f}" for z in v)
greek_table=active.apply(greeks,axis=1); sums=greek_table.sum()
st.subheader("Totali greche")
a,b,c,d=st.columns(4);a.metric("Delta totale",f"{sums['Delta']:,.2f}");b.metric("Gamma totale",f"{sums['Gamma']:,.4f}");c.metric("Vega totale (+1% IV)",f"{sums['Vega (per 1%)']:,.2f}");d.metric("Theta totale (1 giorno)",f"{sums['Theta (al giorno)']:,.2f}")
x=np.linspace(pmin,pmax,2000);ys,ya=tot(x,start),tot(x,analysis);bs,ba=bes(x,ys),bes(x,ya)
left,right=st.columns([3,1])
with left:
 fig=go.Figure()
 if showa:fig.add_trace(go.Scatter(x=x,y=ya,mode="lines",line={"width":4,"color":"#00a878"},name="P/L data analisi"))
 if shows:fig.add_trace(go.Scatter(x=x,y=ys,mode="lines",line={"width":2,"dash":"dash","color":"#3b82f6"},name="P/L data partenza"))
 fig.add_hline(y=0,line_color="gray");fig.add_vline(x=spot,line_dash="dash",line_color="#e69f00",annotation_text=f"{ticker} {spot:.2f}");fig.update_layout(title=f"{name} - {sel}",xaxis_title=f"Prezzo {ticker}",yaxis_title="P/L",hovermode="x unified");st.plotly_chart(fig,use_container_width=True)
with right:
 st.subheader("Metriche");st.metric("Sottostante",ticker);st.metric("Opzioni incluse",f"{len(active)} / {len(legs)}");st.metric("P/L data analisi",f"{tot(np.array([spot]),analysis)[0]:,.2f}");st.metric("P/L data partenza",f"{tot(np.array([spot]),start)[0]:,.2f}")
 st.divider();st.subheader("Break-even")
 if showa:st.info(f"**Alla data di analisi**\n\n{txt(ba)}")
 if shows:st.info(f"**Alla data di partenza**\n\n{txt(bs)}")
out=legs.copy();out.Scadenza=out.Scadenza.apply(lambda z:pd.to_datetime(z).date().isoformat());data={"opzioni":out.to_dict("records"),"parametri":{"name":name,"product":sel,"spot":spot,"start":start.isoformat(),"analysis":analysis.isoformat(),"showa":showa,"shows":shows,"rf":rf,"comm":comm,"pmin":pmin,"pmax":pmax}}
with st.sidebar:
 c1,c2=st.columns(2);c2.download_button("Salva strategia",json.dumps(data,ensure_ascii=False,indent=2).encode(),"strategia_opzioni.json","application/json",use_container_width=True)
