from datetime import date
from math import erf, pi
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title='Payoff Opzioni',layout='wide')
st.title('Payoff Opzioni')
try: catalog=pd.read_csv('sottostanti.csv')
except FileNotFoundError: st.error('Manca il file sottostanti.csv.');st.stop()
COLS=['Escludi','Del','Acquisto/Vendita','Call/Put','Numero opzioni','Strike','Vol opz (%)','Premio','Scadenza'];EXP=date(2026,11,20)
DEFAULT=pd.DataFrame([[False,False,'Vendita','Put',1,600.,26.5,3.9396,EXP],[False,False,'Vendita','Call',1,1200.,48.1,2.6898,EXP]],columns=COLS)
st.session_state.setdefault('legs',DEFAULT.copy());labels=(catalog.Ticker+' - '+catalog.Nome).tolist();default='KE - Wheat Kansas' if 'KE - Wheat Kansas' in labels else labels[0]
for k,v in {'name':'Strategia opzioni','product':default,'spot':721.75,'atmiv':30.,'start':date(2026,8,7),'analysis':EXP,'rf':4.,'comm':0.,'pmin':450.,'pmax':1350.,'showa':True,'shows':True}.items():st.session_state.setdefault(k,v)
with st.sidebar:
 st.header('Salva / Carica strategia');up=st.file_uploader('File strategia (.json)',type='json');a,b=st.columns(2);load=a.button('Carica',use_container_width=True);save_slot=b.empty()
 if load and up:
  z=json.load(up);df=pd.DataFrame(z['opzioni']);df['Scadenza']=pd.to_datetime(df['Scadenza']).dt.date
  for c in COLS:
   if c not in df:df[c]=False if c in ['Escludi','Del'] else None
  st.session_state.legs=df[COLS]
  for k,v in z['parametri'].items():st.session_state[k]=pd.to_datetime(v).date() if k in ['start','analysis'] else v
  st.rerun()
 st.header('Parametri strategia');name=st.text_input('Nome strategia',key='name');selected=st.selectbox('Sottostante',labels,key='product');product=catalog.iloc[labels.index(selected)];ticker,mult=product.Ticker,float(product.PL_Multiplier)
 spot=st.number_input('Prezzo sottostante corrente',step=.25,key='spot');atmiv=st.number_input('ATM IV globale (%)',min_value=.01,step=.1,key='atmiv');start=st.date_input('Data di partenza delle operazioni',key='start');analysis=st.date_input('Data di analisi',key='analysis');showa=st.checkbox('Mostra P/L alla data di analisi',key='showa');shows=st.checkbox('Mostra P/L alla data di partenza',key='shows');rf=st.number_input('Tasso risk-free (%)',min_value=0.,step=.1,key='rf');comm=st.number_input('Commissioni totali',step=.01,key='comm');pmin=st.number_input('Range minimo',step=1.,key='pmin');pmax=st.number_input('Range massimo',step=1.,key='pmax')

def cdf(x):return .5*(1+np.vectorize(erf)(x/np.sqrt(2)))
def pdf(x):return np.exp(-x*x/2)/np.sqrt(2*pi)
def valid(r):
 try:return pd.notna(r.Scadenza) and float(r.Strike)>0 and float(r['Vol opz (%)'])>0 and float(r['Numero opzioni'])>0
 except:return False
def b76(f,k,t,s,r,typ):
 intr=np.maximum(f-k,0) if typ=='Call' else np.maximum(k-f,0)
 if t<=0:return intr
 v=s*np.sqrt(t);d1=(np.log(np.maximum(f,1e-12)/k)+.5*s*s*t)/v;d2=d1-v;d=np.exp(-r*t)
 return d*(f*cdf(d1)-k*cdf(d2)) if typ=='Call' else d*(k*cdf(-d2)-f*cdf(-d1))
def greek(r):
 if not valid(r):return pd.Series({'Delta':np.nan,'Gamma':np.nan,'Vega (per 1%)':np.nan,'Theta (al giorno)':np.nan})
 t=max((pd.to_datetime(r.Scadenza).date()-start).days,0)/365
 if t<=0:return pd.Series({'Delta':0.,'Gamma':0.,'Vega (per 1%)':0.,'Theta (al giorno)':0.})
 s=float(r['Vol opz (%)'])/100;k=float(r.Strike);q=float(r['Numero opzioni'])*mult*(1 if r['Acquisto/Vendita']=='Acquisto' else -1);v=s*np.sqrt(t);d1=(np.log(spot/k)+.5*s*s*t)/v;d=np.exp(-(rf/100)*t);delta=d*(cdf(d1) if r['Call/Put']=='Call' else -cdf(-d1));gamma=d*pdf(d1)/(spot*v);vega=d*spot*pdf(d1)*np.sqrt(t)*.01
 return pd.Series({'Delta':q*delta,'Gamma':q*gamma,'Vega (per 1%)':q*vega,'Theta (al giorno)':0.})
base=st.session_state.legs.copy()
for c in ['Escludi','Del']:
 if c not in base:base[c]=False
 base[c]=base[c].fillna(False).astype(bool)
st.session_state.legs=base[COLS];display=base.copy();display['DTE mancanti']=display.Scadenza.apply(lambda x:max((pd.to_datetime(x).date()-start).days,0) if pd.notna(x) else np.nan);display[['Delta','Gamma','Vega (per 1%)','Theta (al giorno)']]=display.apply(greek,axis=1)
st.subheader('Opzioni')
with st.form('editor'):
 edited=st.data_editor(display,num_rows='dynamic',use_container_width=True,disabled=['DTE mancanti','Delta','Gamma','Vega (per 1%)','Theta (al giorno)'],column_config={'Escludi':st.column_config.CheckboxColumn('Escludi',default=False),'Del':st.column_config.CheckboxColumn('Del',default=False),'Acquisto/Vendita':st.column_config.SelectboxColumn(options=['Acquisto','Vendita']),'Call/Put':st.column_config.SelectboxColumn(options=['Call','Put']),'Scadenza':st.column_config.DateColumn(format='DD/MM/YYYY'),'DTE mancanti':st.column_config.NumberColumn(format='%d'),'Delta':st.column_config.NumberColumn(format='%.2f'),'Gamma':st.column_config.NumberColumn(format='%.4f'),'Vega (per 1%)':st.column_config.NumberColumn(format='%.2f'),'Theta (al giorno)':st.column_config.NumberColumn(format='%.2f')})
 update=st.form_submit_button('Aggiorna calcoli')
if update:
 new=edited[COLS].copy();new['Escludi']=new['Escludi'].fillna(False).astype(bool);new['Del']=new['Del'].fillna(False).astype(bool);st.session_state.legs=new;st.rerun()
if st.button('Elimina righe selezionate',type='primary'):
 if not st.session_state.legs.Del.any():st.warning('Spunta Del su almeno una riga.')
 else:st.session_state.legs=st.session_state.legs[~st.session_state.legs.Del].drop(columns='Del').assign(Del=False).reset_index(drop=True);st.rerun()
active=st.session_state.legs[(~st.session_state.legs.Escludi)&st.session_state.legs.apply(valid,axis=1)].drop(columns='Del')
def pnl(x,r,target):
 t=max((pd.to_datetime(r.Scadenza).date()-target).days,0)/365;sign=1 if r['Acquisto/Vendita']=='Acquisto' else -1
 return sign*float(r['Numero opzioni'])*(b76(x,float(r.Strike),t,float(r['Vol opz (%)'])/100,rf/100,r['Call/Put'])-float(r.Premio))*mult
def total(x,target):return sum((pnl(x,r,target) for _,r in active.iterrows()),np.zeros_like(x,dtype=float))-comm
def be(x,y):return [round(x[i]+(x[i+1]-x[i])*(-y[i])/(y[i+1]-y[i]),2) for i in range(len(x)-1) if y[i]*y[i+1]<0]
def pop():
 t=(analysis-start).days/365
 if t<=0:return 100. if total(np.array([spot]),analysis)[0]>0 else 0.
 s=atmiv/100;z=max(12*s*np.sqrt(t),.25);e=np.concatenate(([0],np.geomspace(max(spot*np.exp(-z),1e-8),spot*np.exp(z),10000),[np.inf]));q=(np.log(e[1:-1]/spot)+.5*s*s*t)/(s*np.sqrt(t));m=np.diff(np.r_[0,cdf(q),1]);mid=np.r_[e[1]/2,np.sqrt(e[1:-2]*e[2:-1]),e[-2]*2];return float(m[total(mid,analysis)>0].sum()*100)
if active.empty:st.warning('Inserisci almeno un’opzione valida.');st.stop()
g=active.apply(greek,axis=1).sum();st.subheader('Totali greche');c1,c2,c3,c4=st.columns(4);c1.metric('Delta totale',f"{g['Delta']:,.2f}");c2.metric('Gamma totale',f"{g['Gamma']:,.4f}");c3.metric('Vega totale (+1% IV)',f"{g['Vega (per 1%)']:,.2f}");c4.metric('Theta totale',f"{g['Theta (al giorno)']:,.2f}")
x=np.linspace(pmin,pmax,2000);ys,ya=total(x,start),total(x,analysis);fig=go.Figure();
if showa:fig.add_trace(go.Scatter(x=x,y=ya,name='P/L data analisi',line={'width':4,'color':'#00a878'}))
if shows:fig.add_trace(go.Scatter(x=x,y=ys,name='P/L data partenza',line={'dash':'dash','color':'#3b82f6'}))
fig.add_hline(y=0,line_color='gray');fig.add_vline(x=spot,line_dash='dash',line_color='#e69f00');fig.update_layout(title=f'{name} - {selected}',hovermode='x unified',xaxis_title=f'Prezzo {ticker}',yaxis_title='P/L');st.plotly_chart(fig,use_container_width=True)
st.metric('PoP data analisi',f'{pop():.1f}%');st.write('Break-even data analisi:',', '.join(map(str,be(x,ya))) or 'Nessuno')
out=st.session_state.legs.drop(columns='Del').copy();out.Scadenza=out.Scadenza.apply(lambda z:pd.to_datetime(z).date().isoformat() if pd.notna(z) else None);data={'opzioni':out.to_dict('records'),'parametri':{'name':name,'product':selected,'spot':spot,'atmiv':atmiv,'start':start.isoformat(),'analysis':analysis.isoformat(),'rf':rf,'comm':comm,'pmin':pmin,'pmax':pmax,'showa':showa,'shows':shows}};save_slot.download_button('Salva',json.dumps(data,ensure_ascii=False).encode(),'strategia_opzioni.json','application/json',use_container_width=True)
