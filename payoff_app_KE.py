from datetime import date
from math import erf, pi
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Payoff Opzioni", layout="wide")
st.title("Payoff Opzioni")
try: catalog=pd.read_csv("sottostanti.csv")
except FileNotFoundError: st.error("Manca il file sottostanti.csv.");st.stop()
EXP=date(2026,11,20)
DEFAULT=pd.DataFrame([
 {"Escludi":False,"Del":False,"Acquisto/Vendita":"Vendita","Call/Put":"Put","Numero opzioni":1,"Strike":600.,"Vol opz (%)":26.5,"Premio":3.9396,"Scadenza":EXP},
 {"Escludi":False,"Del":False,"Acquisto/Vendita":"Vendita","Call/Put":"Call","Numero opzioni":1,"Strike":1200.,"Vol opz (%)":48.1,"Premio":2.6898,"Scadenza":EXP}])
labels=(catalog.Ticker+" - "+catalog.Nome).tolist();default="KE - Wheat Kansas" if "KE - Wheat Kansas" in labels else labels[0]
if "legs_source" not in st.session_state:st.session_state.legs_source=DEFAULT.copy()
for k,v in {"name":"Strategia opzioni","product":default,"spot":721.75,"atmiv":30.0,"start":date(2026,8,7),"analysis":EXP,"showa":True,"shows":True,"rf":4.,"comm":0.,"pmin":450.,"pmax":1350.}.items():st.session_state.setdefault(k,v)
with st.sidebar:
 st.header("Salva / Carica strategia")
 up=st.file_uploader("File strategia (.json)",type="json");lc,sc=st.columns(2);load=lc.button("Carica strategia",use_container_width=True);save_area=sc.empty()
 if load:
  if up is None:st.warning("Scegli prima un file JSON.")
  else:
   try:
    z=json.load(up);st.session_state.legs_source=pd.DataFrame(z["opzioni"]);st.session_state.legs_source.Scadenza=pd.to_datetime(st.session_state.legs_source.Scadenza).dt.date
    for k,v in z["parametri"].items():st.session_state[k]=pd.to_datetime(v).date() if k in ["start","analysis"] else v
    st.session_state.pop("editor",None);st.rerun()
   except Exception as e:st.error(f"File non valido: {e}")
 st.divider();st.header("Parametri strategia")
 name=st.text_input("Nome strategia",key="name");sel=st.selectbox("Sottostante",labels,key="product");prod=catalog.iloc[labels.index(sel)];ticker,mult=prod.Ticker,float(prod.PL_Multiplier)
 spot=st.number_input("Prezzo sottostante corrente",step=.25,format="%.4f",key="spot")
 atmiv=st.number_input("ATM IV globale (%)",min_value=.01,step=.1,key="atmiv",help="Usata esclusivamente nel calcolo probabilistico della PoP.")
 st.subheader("Date e time decay");start=st.date_input("Data di partenza delle operazioni",key="start");analysis=st.date_input("Data di analisi",key="analysis")
 st.subheader("Curve da mostrare");showa=st.checkbox("Mostra P/L alla data di analisi",key="showa");shows=st.checkbox("Mostra P/L alla data di partenza",key="shows")
 rf=st.number_input("Tasso risk-free (%)",min_value=0.,step=.1,key="rf");comm=st.number_input("Commissioni totali",step=.01,key="comm");pmin=st.number_input("Range minimo",step=1.,key="pmin");pmax=st.number_input("Range massimo",step=1.,key="pmax")
 if st.button("Ripristina esempio KE"):st.session_state.legs_source=DEFAULT.copy();st.session_state.pop("editor",None);st.rerun()
if analysis<start or pmax<=pmin:st.error("Controlla date e range prezzi.");st.stop()
def cdf(x):return .5*(1+np.vectorize(erf)(x/np.sqrt(2)))
def pdf(x):return np.exp(-x*x/2)/np.sqrt(2*pi)
def b76(f,k,t,s,r,typ):
 intr=np.maximum(f-k,0) if typ=="Call" else np.maximum(k-f,0)
 if t<=0:return intr
 f=np.maximum(f,1e-12);v=s*np.sqrt(t);d1=(np.log(f/k)+.5*s*s*t)/v;d2=d1-v;d=np.exp(-r*t)
 return d*(f*cdf(d1)-k*cdf(d2)) if typ=="Call" else d*(k*cdf(-d2)-f*cdf(-d1))
def greeks(r):
 t=max((pd.to_datetime(r.Scadenza).date()-start).days,0)/365;s=float(r["Vol opz (%)"])/100;k=float(r.Strike);q=float(r["Numero opzioni"])*mult*(1 if r["Acquisto/Vendita"]=="Acquisto" else -1)
 if t<=0:return pd.Series({"Delta":0.,"Gamma":0.,"Vega (per 1%)":0.,"Theta (al giorno)":0.})
 v=s*np.sqrt(t);d1=(np.log(spot/k)+.5*s*s*t)/v;disc=np.exp(-(rf/100)*t);delta=disc*(cdf(d1) if r["Call/Put"]=="Call" else -cdf(-d1));gamma=disc*pdf(d1)/(spot*v);vega=disc*spot*pdf(d1)*np.sqrt(t)*.01
 a=b76(np.array([spot]),k,t,s,rf/100,r["Call/Put"])[0];b=b76(np.array([spot]),k,max(t-1/365,0),s,rf/100,r["Call/Put"])[0]
 return pd.Series({"Delta":q*delta,"Gamma":q*gamma,"Vega (per 1%)":q*vega,"Theta (al giorno)":q*(b-a)})
st.subheader("Opzioni");st.caption("Escludi disattiva una riga; Del la elimina definitivamente dopo conferma.")
ed=st.session_state.legs_source.copy();ed.setdefault if False else None
if "Del" not in ed:ed["Del"]=False
ed["DTE mancanti"]=ed.Scadenza.apply(lambda d:max((pd.to_datetime(d).date()-start).days,0) if pd.notna(d) else None)
ed[["Delta","Gamma","Vega (per 1%)","Theta (al giorno)"]]=ed.apply(greeks,axis=1)
legs=st.data_editor(ed,num_rows="dynamic",use_container_width=True,key="editor",disabled=["DTE mancanti","Delta","Gamma","Vega (per 1%)","Theta (al giorno)"],column_config={"Escludi":st.column_config.CheckboxColumn("Escludi",default=False),"Del":st.column_config.CheckboxColumn("Del",default=False),"Acquisto/Vendita":st.column_config.SelectboxColumn(options=["Acquisto","Vendita"]),"Call/Put":st.column_config.SelectboxColumn(options=["Call","Put"]),"Numero opzioni":st.column_config.NumberColumn(min_value=0.,step=1.),"Strike":st.column_config.NumberColumn(step=.25),"Vol opz (%)":st.column_config.NumberColumn(min_value=.01,step=.1),"Premio":st.column_config.NumberColumn(step=.0001,format="%.4f"),"Scadenza":st.column_config.DateColumn(format="DD/MM/YYYY"),"DTE mancanti":st.column_config.NumberColumn(format="%d"),"Delta":st.column_config.NumberColumn(format="%.2f"),"Gamma":st.column_config.NumberColumn(format="%.4f"),"Vega (per 1%)":st.column_config.NumberColumn(format="%.2f"),"Theta (al giorno)":st.column_config.NumberColumn(format="%.2f")}).drop(columns=["DTE mancanti","Delta","Gamma","Vega (per 1%)","Theta (al giorno)"],errors="ignore")
if st.button("Elimina righe selezionate",type="primary"):
 if not legs["Del"].any():st.warning("Spunta Del su almeno una riga.")
 else:st.session_state.legs_source=legs[~legs.Del].drop(columns="Del",errors="ignore").reset_index(drop=True);st.session_state.pop("editor",None);st.rerun()
req=["Escludi","Del","Acquisto/Vendita","Call/Put","Numero opzioni","Strike","Vol opz (%)","Premio","Scadenza"]
if legs.empty or legs[req].isnull().any().any():st.error("Completa tutte le righe.");st.stop()
active=legs[~legs.Escludi].drop(columns="Del",errors="ignore").copy()
if active.empty:st.warning("Tutte le opzioni sono escluse.");st.stop()
def pnl(p,r,target):
 sign=1 if r["Acquisto/Vendita"]=="Acquisto" else -1;t=max((pd.to_datetime(r.Scadenza).date()-target).days,0)/365
 return sign*float(r["Numero opzioni"])*(b76(p,float(r.Strike),t,float(r["Vol opz (%)"])/100,rf/100,r["Call/Put"])-float(r.Premio))*mult
def total(p,target):return sum((pnl(p,r,target) for _,r in active.iterrows()),np.zeros_like(p,dtype=float))-comm
def bes(x,y):return sorted(set(round(x[i]+(x[i+1]-x[i])*(-y[i])/(y[i+1]-y[i]),4) for i in range(len(x)-1) if y[i]*y[i+1]<0))
def text(v):return "Nessun break-even nel range selezionato" if not v else " • ".join(f"{i:,.2f}" for i in v)
def pop_expiry():
 t=(analysis-start).days/365
 if t<=0:return 100. if total(np.array([spot]),analysis)[0]>0 else 0.
 s=atmiv/100;z=max(12*s*np.sqrt(t),.25);lo=max(spot*np.exp(-z),1e-8);hi=spot*np.exp(z);edges=np.concatenate(([0],np.geomspace(lo,hi,16000),[np.inf]))
 q=(np.log(edges[1:-1]/spot)+.5*s*s*t)/(s*np.sqrt(t));mass=np.diff(np.concatenate(([0],cdf(q),[1])));mid=np.empty(len(mass));mid[0]=lo/2;mid[-1]=hi*2;mid[1:-1]=np.sqrt(edges[1:-2]*edges[2:-1])
 return float(np.sum(mass[total(mid,analysis)>0])*100)
g=active.apply(greeks,axis=1).sum();st.subheader("Totali greche");a,b,c,d=st.columns(4);a.metric("Delta totale",f"{g['Delta']:,.2f}");b.metric("Gamma totale",f"{g['Gamma']:,.4f}");c.metric("Vega totale (+1% IV)",f"{g['Vega (per 1%)']:,.2f}");d.metric("Theta totale (1 giorno)",f"{g['Theta (al giorno)']:,.2f}")
x=np.linspace(pmin,pmax,2000);ys,ya=total(x,start),total(x,analysis);bs,ba=bes(x,ys),bes(x,ya)
l,r=st.columns([3,1])
with l:
 fig=go.Figure();
 if showa:fig.add_trace(go.Scatter(x=x,y=ya,mode="lines",line={"width":4,"color":"#00a878"},name="P/L data analisi"))
 if shows:fig.add_trace(go.Scatter(x=x,y=ys,mode="lines",line={"width":2,"dash":"dash","color":"#3b82f6"},name="P/L data partenza"))
 fig.add_hline(y=0,line_color="gray");fig.add_vline(x=spot,line_dash="dash",line_color="#e69f00",annotation_text=f"{ticker} {spot:.2f}");fig.update_layout(title=f"{name} - {sel}",xaxis_title=f"Prezzo {ticker}",yaxis_title="P/L",hovermode="x unified");st.plotly_chart(fig,use_container_width=True)
with r:
 st.subheader("Metriche");st.metric("Sottostante",ticker);st.metric("Opzioni incluse",f"{len(active)} / {len(legs)}");st.metric("PoP data analisi",f"{pop_expiry():.1f}%");st.caption(f"Calcolata con ATM IV globale {atmiv:.1f}%")
 st.metric("P/L data analisi",f"{total(np.array([spot]),analysis)[0]:,.2f}");st.metric("P/L data partenza",f"{total(np.array([spot]),start)[0]:,.2f}");st.divider();st.subheader("Break-even")
 if showa:st.info(f"**Alla data di analisi**\n\n{text(ba)}")
 if shows:st.info(f"**Alla data di partenza**\n\n{text(bs)}")
out=legs.drop(columns="Del",errors="ignore").copy();out.Scadenza=out.Scadenza.apply(lambda z:pd.to_datetime(z).date().isoformat());data={"opzioni":out.to_dict("records"),"parametri":{"name":name,"product":sel,"spot":spot,"atmiv":atmiv,"start":start.isoformat(),"analysis":analysis.isoformat(),"showa":showa,"shows":shows,"rf":rf,"comm":comm,"pmin":pmin,"pmax":pmax}}
save_area.download_button("Salva strategia",json.dumps(data,ensure_ascii=False,indent=2).encode(),"strategia_opzioni.json","application/json",use_container_width=True)
