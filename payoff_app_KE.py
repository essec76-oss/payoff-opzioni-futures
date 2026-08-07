from datetime import date
from math import erf, pi
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Payoff Opzioni",layout="wide")
st.title("Payoff Opzioni")
try: catalog=pd.read_csv("sottostanti.csv")
except FileNotFoundError: st.error("Manca il file sottostanti.csv.");st.stop()
EXP=date(2026,11,20)
COLS=["Escludi","Del","Acquisto/Vendita","Call/Put","Numero opzioni","Strike","Vol opz (%)","Premio","Scadenza"]
DEFAULT=pd.DataFrame([
 [False,False,"Vendita","Put",1,600.,26.5,3.9396,EXP],
 [False,False,"Vendita","Call",1,1200.,48.1,2.6898,EXP]],columns=COLS)
labels=(catalog.Ticker+" - "+catalog.Nome).tolist();default="KE - Wheat Kansas" if "KE - Wheat Kansas" in labels else labels[0]
st.session_state.setdefault("legs_source",DEFAULT.copy())
for k,v in {"name":"Strategia opzioni","product":default,"spot":721.75,"atmiv":30.,"start":date(2026,8,7),"analysis":EXP,"rf":4.,"comm":0.,"pmin":450.,"pmax":1350.,"showa":True,"shows":True}.items():st.session_state.setdefault(k,v)

def sync_editor():
    changes=st.session_state.get("editor",{})
    df=st.session_state.legs_source.copy().reset_index(drop=True)
    for i,vals in changes.get("edited_rows",{}).items():
        for col,val in vals.items():
            if col in COLS and i<len(df): df.at[i,col]=val
    for row in changes.get("added_rows",[]):
        new={"Escludi":False,"Del":False,"Acquisto/Vendita":"Acquisto","Call/Put":"Call","Numero opzioni":1,"Strike":0.,"Vol opz (%)":30.,"Premio":0.,"Scadenza":EXP}
        new.update({k:v for k,v in row.items() if k in COLS})
        df=pd.concat([df,pd.DataFrame([new])],ignore_index=True)
    for i in sorted(changes.get("deleted_rows",[]),reverse=True):
        if i<len(df):df=df.drop(index=i)
    st.session_state.legs_source=df.reset_index(drop=True)

with st.sidebar:
 st.header("Salva / Carica strategia")
 up=st.file_uploader("File strategia (.json)",type="json");a,b=st.columns(2);load=a.button("Carica strategia",use_container_width=True);save_area=b.empty()
 if load and up:
  try:
   z=json.load(up);df=pd.DataFrame(z["opzioni"]);df["Scadenza"]=pd.to_datetime(df["Scadenza"]).dt.date
   for c in COLS:
    if c not in df:df[c]=False if c in ["Escludi","Del"] else None
   st.session_state.legs_source=df[COLS]
   for k,v in z["parametri"].items():st.session_state[k]=pd.to_datetime(v).date() if k in ["start","analysis"] else v
   st.session_state.pop("editor",None);st.rerun()
  except Exception as e:st.error(f"File non valido: {e}")
 if load and not up:st.warning("Scegli prima un file JSON.")
 st.divider();st.header("Parametri strategia")
 name=st.text_input("Nome strategia",key="name");sel=st.selectbox("Sottostante",labels,key="product");pr=catalog.iloc[labels.index(sel)];ticker,mult=pr.Ticker,float(pr.PL_Multiplier)
 spot=st.number_input("Prezzo sottostante corrente",step=.25,key="spot");atmiv=st.number_input("ATM IV globale (%)",min_value=.01,step=.1,key="atmiv")
 start=st.date_input("Data di partenza delle operazioni",key="start");analysis=st.date_input("Data di analisi",key="analysis")
 showa=st.checkbox("Mostra P/L alla data di analisi",key="showa");shows=st.checkbox("Mostra P/L alla data di partenza",key="shows")
 rf=st.number_input("Tasso risk-free (%)",min_value=0.,step=.1,key="rf");comm=st.number_input("Commissioni totali",step=.01,key="comm");pmin=st.number_input("Range minimo",step=1.,key="pmin");pmax=st.number_input("Range massimo",step=1.,key="pmax")
 if st.button("Ripristina esempio KE"):st.session_state.legs_source=DEFAULT.copy();st.session_state.pop("editor",None);st.rerun()
if analysis<start or pmax<=pmin:st.error("Controlla date e range.");st.stop()
def cdf(x):return .5*(1+np.vectorize(erf)(x/np.sqrt(2)))
def pdf(x):return np.exp(-x*x/2)/np.sqrt(2*pi)
def b76(f,k,t,s,r,typ):
 intr=np.maximum(f-k,0) if typ=="Call" else np.maximum(k-f,0)
 if t<=0:return intr
 f=np.maximum(f,1e-12);v=s*np.sqrt(t);d1=(np.log(f/k)+.5*s*s*t)/v;d2=d1-v;d=np.exp(-r*t)
 return d*(f*cdf(d1)-k*cdf(d2)) if typ=="Call" else d*(k*cdf(-d2)-f*cdf(-d1))
def greek(r):
 try:t=max((pd.to_datetime(r.Scadenza).date()-start).days,0)/365;s=float(r["Vol opz (%)"])/100;k=float(r.Strike);q=float(r["Numero opzioni"])*mult*(1 if r["Acquisto/Vendita"]=="Acquisto" else -1)
 except:return pd.Series({"Delta":np.nan,"Gamma":np.nan,"Vega (per 1%)":np.nan,"Theta (al giorno)":np.nan})
 if t<=0:return pd.Series({"Delta":0.,"Gamma":0.,"Vega (per 1%)":0.,"Theta (al giorno)":0.})
 v=s*np.sqrt(t);d1=(np.log(spot/k)+.5*s*s*t)/v;d=np.exp(-(rf/100)*t);delta=d*(cdf(d1) if r["Call/Put"]=="Call" else -cdf(-d1));gamma=d*pdf(d1)/(spot*v);vega=d*spot*pdf(d1)*np.sqrt(t)*.01;a=b76(np.array([spot]),k,t,s,rf/100,r["Call/Put"])[0];b=b76(np.array([spot]),k,max(t-1/365,0),s,rf/100,r["Call/Put"])[0]
 return pd.Series({"Delta":q*delta,"Gamma":q*gamma,"Vega (per 1%)":q*vega,"Theta (al giorno)":q*(b-a)})
st.subheader("Opzioni")
ed=st.session_state.legs_source.copy();ed["DTE mancanti"]=ed.Scadenza.apply(lambda x:max((pd.to_datetime(x).date()-start).days,0) if pd.notna(x) else np.nan);ed[["Delta","Gamma","Vega (per 1%)","Theta (al giorno)"]]=ed.apply(greek,axis=1)
shown=st.data_editor(ed,num_rows="dynamic",use_container_width=True,key="editor",on_change=sync_editor,disabled=["DTE mancanti","Delta","Gamma","Vega (per 1%)","Theta (al giorno)"],column_config={"Escludi":st.column_config.CheckboxColumn("Escludi"),"Del":st.column_config.CheckboxColumn("Del"),"Acquisto/Vendita":st.column_config.SelectboxColumn(options=["Acquisto","Vendita"]),"Call/Put":st.column_config.SelectboxColumn(options=["Call","Put"]),"Scadenza":st.column_config.DateColumn(format="DD/MM/YYYY"),"DTE mancanti":st.column_config.NumberColumn(format="%d"),"Delta":st.column_config.NumberColumn(format="%.2f"),"Gamma":st.column_config.NumberColumn(format="%.4f"),"Vega (per 1%)":st.column_config.NumberColumn(format="%.2f"),"Theta (al giorno)":st.column_config.NumberColumn(format="%.2f")})
if st.button("Elimina righe selezionate",type="primary"):
 clean=shown.drop(columns=["DTE mancanti","Delta","Gamma","Vega (per 1%)","Theta (al giorno)"],errors="ignore")
 if not clean.Del.any():st.warning("Spunta Del su almeno una riga.")
 else:st.session_state.legs_source=clean[~clean.Del].drop(columns="Del").reset_index(drop=True);st.session_state.pop("editor",None);st.rerun()
legs=st.session_state.legs_source.copy();active=legs[~legs.Escludi].drop(columns="Del",errors="ignore")
def pnl(x,r,target):
 t=max((pd.to_datetime(r.Scadenza).date()-target).days,0)/365;sg=1 if r["Acquisto/Vendita"]=="Acquisto" else -1
 return sg*float(r["Numero opzioni"])*(b76(x,float(r.Strike),t,float(r["Vol opz (%)"])/100,rf/100,r["Call/Put"])-float(r.Premio))*mult
def total(x,target):return sum((pnl(x,r,target) for _,r in active.iterrows()),np.zeros_like(x,dtype=float))-comm
def pop():
 t=(analysis-start).days/365;s=atmiv/100
 if t<=0:return 100. if total(np.array([spot]),analysis)[0]>0 else 0.
 z=max(12*s*np.sqrt(t),.25);e=np.concatenate(([0],np.geomspace(max(spot*np.exp(-z),1e-8),spot*np.exp(z),10000),[np.inf]));q=(np.log(e[1:-1]/spot)+.5*s*s*t)/(s*np.sqrt(t));m=np.diff(np.r_[0,cdf(q),1]);mid=np.r_[e[1]/2,np.sqrt(e[1:-2]*e[2:-1]),e[-2]*2];return float(m[total(mid,analysis)>0].sum()*100)
g=active.apply(greek,axis=1).sum();st.subheader("Totali greche");c1,c2,c3,c4=st.columns(4);c1.metric("Delta totale",f"{g['Delta']:,.2f}");c2.metric("Gamma totale",f"{g['Gamma']:,.4f}");c3.metric("Vega totale (+1% IV)",f"{g['Vega (per 1%)']:,.2f}");c4.metric("Theta totale (1 giorno)",f"{g['Theta (al giorno)']:,.2f}")
x=np.linspace(pmin,pmax,2000);ys,ya=total(x,start),total(x,analysis);l,r=st.columns([3,1])
with l:
 fig=go.Figure();
 if showa:fig.add_trace(go.Scatter(x=x,y=ya,name="P/L data analisi"))
 if shows:fig.add_trace(go.Scatter(x=x,y=ys,name="P/L data partenza",line={"dash":"dash"}))
 fig.add_hline(y=0);fig.add_vline(x=spot);fig.update_layout(hovermode="x unified");st.plotly_chart(fig,use_container_width=True)
with r:st.metric("PoP data analisi",f"{pop():.1f}%");st.caption(f"ATM IV: {atmiv:.1f}%")
out=legs.drop(columns="Del",errors="ignore").copy();out.Scadenza=out.Scadenza.apply(lambda x:pd.to_datetime(x).date().isoformat());data={"opzioni":out.to_dict("records"),"parametri":{"name":name,"product":sel,"spot":spot,"atmiv":atmiv,"start":start.isoformat(),"analysis":analysis.isoformat(),"rf":rf,"comm":comm,"pmin":pmin,"pmax":pmax,"showa":showa,"shows":shows}}
save_area.download_button("Salva strategia",json.dumps(data,ensure_ascii=False).encode(),"strategia_opzioni.json","application/json",use_container_width=True)
