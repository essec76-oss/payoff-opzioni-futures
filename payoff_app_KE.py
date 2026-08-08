from datetime import date
from math import erf,pi
import json
import numpy as np,pandas as pd
import plotly.graph_objects as go
import streamlit as st
st.set_page_config(page_title='Payoff Opzioni',layout='wide');st.title('Payoff Opzioni')
try: catalog=pd.read_csv('sottostanti.csv')
except FileNotFoundError: st.error('Manca il file sottostanti.csv nella stessa cartella dell’app.');st.stop()
COLS=['Oscura','Del','Buy/Sell','Call/Put','N° opz','Strike','Vol opz (%)','Premio','Scadenza'];EXP=date(2026,11,20)
DEFAULT=pd.DataFrame([[False,False,'Sell','Put',1,600.,26.5,3.9396,EXP],[False,False,'Sell','Call',1,1200.,48.1,2.6898,EXP]],columns=COLS)
st.session_state.setdefault('legs',DEFAULT.copy());labels=(catalog.Ticker.astype(str)+' - '+catalog.Nome.astype(str)).tolist();default='KE - Wheat Kansas' if 'KE - Wheat Kansas' in labels else labels[0]
for k,v in {'asset_class':'Futures Commodity','product':default,'spot':721.75,'atmiv':30.,'start':date(2026,8,7),'analysis':EXP,'rf':0.,'cash':0.,'pmin':450.,'pmax':1350.,'showa':True,'shows':True}.items():st.session_state.setdefault(k,v)
def cdf(x):return .5*(1+np.vectorize(erf)(x/np.sqrt(2)))
def pdf(x):return np.exp(-x*x/2)/np.sqrt(2*pi)
def valid(r):
 try:return pd.notna(r.Scadenza) and float(r.Strike)>0 and float(r['Vol opz (%)'])>0 and float(r['N° opz'])>0
 except:return False
def b76(f,k,t,s,r,typ):
 intr=np.maximum(f-k,0) if typ=='Call' else np.maximum(k-f,0)
 if t<=0 or s<=0:return intr
 v=s*np.sqrt(t);d1=(np.log(np.maximum(f,1e-12)/k)+.5*s*s*t)/v;d2=d1-v;d=np.exp(-r*t)
 return d*(f*cdf(d1)-k*cdf(d2)) if typ=='Call' else d*(k*cdf(-d2)-f*cdf(-d1))
def values(r,dt):
 miss={'DTE':np.nan,'xTM':'','Delta':np.nan,'Gamma':np.nan,'Vega':np.nan,'THETA':np.nan,'Pr. opz.':np.nan,'V. Temp.':np.nan,'V. Intr.':np.nan}
 if not valid(r):return miss
 dte=max((pd.to_datetime(r.Scadenza).date()-dt).days,0);t=dte/365;k=float(r.Strike);s=float(r['Vol opz (%)'])/100;typ=r['Call/Put'];fac=(1 if r['Buy/Sell']=='Buy' else -1)*float(r['N° opz'])*multiplier;intr=max(spot-k,0) if typ=='Call' else max(k-spot,0);theo=float(b76(spot,k,t,s,rate,typ));xtm='ATM' if abs(spot-k)/spot<=.005 else ('ITM' if ((typ=='Call' and spot>k)or(typ=='Put' and spot<k)) else 'OTM')
 if t<=0:return {'DTE':dte,'xTM':xtm,'Delta':0.,'Gamma':0.,'Vega':0.,'THETA':0.,'Pr. opz.':theo,'V. Temp.':0.,'V. Intr.':intr}
 rt=np.sqrt(t);d1=(np.log(spot/k)+.5*s*s*t)/(s*rt);d=np.exp(-rate*t);delta=d*(cdf(d1) if typ=='Call' else-cdf(-d1));gamma=d*pdf(d1)/(spot*s*rt);vega=d*spot*pdf(d1)*rt*.01;theta=float(b76(spot,k,max(t-1/365,0),s,rate,typ))-theo
 return {'DTE':dte,'xTM':xtm,'Delta':fac*float(delta),'Gamma':fac*float(gamma),'Vega':fac*float(vega),'THETA':fac*theta,'Pr. opz.':theo,'V. Temp.':max(theo-intr,0),'V. Intr.':intr}
def pnl(x,r,dt):return (1 if r['Buy/Sell']=='Buy' else -1)*float(r['N° opz'])*(b76(x,float(r.Strike),max((pd.to_datetime(r.Scadenza).date()-dt).days,0)/365,float(r['Vol opz (%)'])/100,rate,r['Call/Put'])-float(r.Premio))*multiplier
def total(x,dt):return sum((pnl(x,r,dt) for _,r in active.iterrows()),np.zeros_like(x,dtype=float))+cash
def beps(x,y):return [round(x[i]+(x[i+1]-x[i])*(-y[i])/(y[i+1]-y[i]),2) for i in range(len(x)-1) if y[i]*y[i+1]<0]
def pop():
 t=(analysis_date-start_date).days/365
 if t<=0:return 100. if total(np.array([spot]),analysis_date)[0]>0 else 0.
 s=atmiv/100;z=max(12*s*np.sqrt(t),.25);e=np.concatenate(([0],np.geomspace(max(spot*np.exp(-z),1e-8),spot*np.exp(z),10000),[np.inf]));q=(np.log(e[1:-1]/spot)+.5*s*s*t)/(s*np.sqrt(t));m=np.diff(np.r_[0,cdf(q),1]);mid=np.r_[e[1]/2,np.sqrt(e[1:-2]*e[2:-1]),e[-2]*2]
 return float(m[total(mid,analysis_date)>0].sum()*100)
with st.expander('Salva / Carica strategia'):
 up=st.file_uploader('File strategia (.json)',type='json');a,b=st.columns([1,5]);load=a.button('Carica');slot=b.empty()
 if load and up:
  z=json.load(up);df=pd.DataFrame(z['opzioni']).rename(columns={'Acquisto/Vendita':'Buy/Sell','Numero opzioni':'N° opz'});df['Scadenza']=pd.to_datetime(df.Scadenza).dt.date
  for c in COLS:
   if c not in df:df[c]=False if c in ['Oscura','Del'] else None
  st.session_state.legs=df[COLS]
  for k,v in z['parametri'].items():st.session_state[k]=pd.to_datetime(v).date() if k in ['start','analysis'] else v
  st.rerun()
r1=st.columns([1.25,1.6,1,1,1]);asset_class=r1[0].selectbox('Tipo sottostante',['Futures Commodity','Azioni','Futures Indici'],key='asset_class');selected=r1[1].selectbox('Sottostante',labels,key='product');product=catalog.iloc[labels.index(selected)];ticker,multiplier=product.Ticker,float(product.PL_Multiplier);spot=r1[2].number_input('Prezzo sottostante',min_value=.0001,step=.25,key='spot');cash=r1[3].number_input('Cash ($)',step=.01,key='cash');r1[4].metric('Ticker / Mult.',f'{ticker} ×{multiplier:g}')
r2=st.columns(8);start_date=r2[0].date_input('Data partenza',key='start');analysis_date=r2[1].date_input('Data analisi',key='analysis');atmiv=r2[2].number_input('ATM IV (%)',min_value=.01,step=.1,key='atmiv');rate_pct=r2[3].number_input('Tasso risk-free (%)',min_value=0.,step=.1,key='rf');pmin=r2[4].number_input('Range minimo',step=1.,key='pmin');pmax=r2[5].number_input('Range massimo',step=1.,key='pmax');show_analysis=r2[6].checkbox('P/L a scadenza',key='showa');show_start=r2[7].checkbox('P/L at now',key='shows');rate=rate_pct/100
base=st.session_state.legs.copy();base['Oscura']=base.get('Oscura',False);base['Oscura']=base['Oscura'].fillna(False).astype(bool);base['Del']=base.get('Del',False);base['Del']=base['Del'].fillna(False).astype(bool);base=base[COLS];st.session_state.legs=base;active=base[(~base.Oscura)&base.apply(valid,axis=1)].drop(columns=['Oscura','Del'])
with st.tabs(['Strategia','Comparazione 1','Comparazione 2'])[0]:
 display=pd.concat([base,base.apply(lambda r:pd.Series(values(r,start_date)),axis=1)],axis=1);display['P&L AtNow']=display.apply(lambda r:pnl(np.array([spot]),r,start_date)[0] if valid(r) else np.nan,axis=1);display['P&L scad.']=display.apply(lambda r:pnl(np.array([spot]),r,pd.to_datetime(r.Scadenza).date())[0] if valid(r) else np.nan,axis=1)
 with st.form('editor'):
  edited=st.data_editor(display,num_rows='dynamic',use_container_width=True,disabled=['DTE','xTM','Delta','Gamma','Vega','THETA','Pr. opz.','V. Temp.','V. Intr.','P&L AtNow','P&L scad.'],column_config={'Oscura':st.column_config.CheckboxColumn('Oscura'),'Del':st.column_config.CheckboxColumn('Del'),'Buy/Sell':st.column_config.SelectboxColumn('Buy/Sell',options=['Buy','Sell']),'Call/Put':st.column_config.SelectboxColumn('Call/Put',options=['Call','Put']),'Scadenza':st.column_config.DateColumn(format='DD/MM/YYYY')});update=st.form_submit_button('Calcola payoff')
 if update:st.session_state.legs=edited[COLS];st.rerun()
 if st.button('Elimina righe selezionate'):st.session_state.legs=base[~base.Del].assign(Del=False).reset_index(drop=True);st.rerun()
 if active.empty:st.warning('Inserisci almeno un’opzione attiva e valida.')
 else:
  g=active.apply(lambda r:pd.Series(values(r,start_date)),axis=1)[['Delta','Gamma','Vega','THETA']].sum();x=np.linspace(pmin,pmax,2000);y_now=total(x,start_date);y_exp=sum((pnl(x,r,pd.to_datetime(r.Scadenza).date()) for _,r in active.iterrows()),np.zeros_like(x))+cash;fig=go.Figure()
  if show_analysis:fig.add_trace(go.Scatter(x=x,y=y_exp,name='P/L a scadenza',line={'width':4,'color':'#00a878'}))
  if show_start:fig.add_trace(go.Scatter(x=x,y=y_now,name='P/L at now',line={'dash':'dash','color':'#3b82f6'}))
  fig.add_hline(y=0,line_color='gray');fig.add_vline(x=spot,line_dash='dash');st.plotly_chart(fig,use_container_width=True)
  b=beps(x,y_exp);c=st.columns(7)
  for col,n,v in zip(c[:4],g.index,g.values):col.metric(n,f'{v:,.3f}')
  c[4].metric('PoP data analisi',f'{pop():.1f}%');c[5].metric('BEP inferiore',f'{b[0]:.2f}' if b else 'Nessuno');c[6].metric('BEP superiore',f'{b[-1]:.2f}' if len(b)>1 else 'Nessuno')
out=st.session_state.legs.drop(columns=['Oscura','Del']).copy();out.Scadenza=out.Scadenza.apply(lambda x:pd.to_datetime(x).date().isoformat() if pd.notna(x) else None);data={'opzioni':out.to_dict('records'),'parametri':{'asset_class':asset_class,'product':selected,'spot':spot,'atmiv':atmiv,'start':start_date.isoformat(),'analysis':analysis_date.isoformat(),'rf':rate_pct,'cash':cash,'pmin':pmin,'pmax':pmax,'showa':show_analysis,'shows':show_start}};slot.download_button('Salva',json.dumps(data,ensure_ascii=False).encode(),'strategia_opzioni.json','application/json')
