from datetime import date
from math import erf, pi
import json, re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title='Payoff Opzioni', layout='wide')
st.title('Payoff Opzioni')
try: catalog = pd.read_csv('sottostanti.csv')
except FileNotFoundError: st.error('Manca il file sottostanti.csv.'); st.stop()

COLS=['Escludi temporaneamente','Del','Buy/Sell','Call/Put','N° opz','Strike','Vol opz (%)','Premio','Scadenza']
EXP=date(2026,11,20)
DEFAULT=pd.DataFrame([[False,False,'Sell','Put',1,600.,26.5,3.9396,EXP],[False,False,'Sell','Call',1,1200.,48.1,2.6898,EXP]],columns=COLS)
st.session_state.setdefault('legs',DEFAULT.copy())
labels=(catalog.Ticker.astype(str)+' - '+catalog.Nome.astype(str)).tolist()
default='KE - Wheat Kansas' if 'KE - Wheat Kansas' in labels else labels[0]
for k,v in {'project_name':'Strategia_opzioni','asset_class':'Futures Commodity','product':default,'spot':721.75,'atmiv':30.,'simulation':EXP,'rf':0.,'cash':0.,'pmin':450.,'pmax':1350.,'show_simulation':True,'show_today':True}.items(): st.session_state.setdefault(k,v)

def cdf(x): return .5*(1+np.vectorize(erf)(x/np.sqrt(2)))
def pdf(x): return np.exp(-x*x/2)/np.sqrt(2*pi)
def valid(r):
    try: return pd.notna(r.Scadenza) and float(r.Strike)>0 and float(r['Vol opz (%)'])>0 and float(r['N° opz'])>0
    except: return False
def b76(f,k,t,s,r,typ):
    intr=np.maximum(f-k,0) if typ=='Call' else np.maximum(k-f,0)
    if t<=0 or s<=0:return intr
    v=s*np.sqrt(t);d1=(np.log(np.maximum(f,1e-12)/k)+.5*s*s*t)/v;d2=d1-v;d=np.exp(-r*t)
    return d*(f*cdf(d1)-k*cdf(d2)) if typ=='Call' else d*(k*cdf(-d2)-f*cdf(-d1))
def calc(r,dt):
    if not valid(r): return pd.Series({'DTE':np.nan,'xTM':'','Delta':np.nan,'Gamma':np.nan,'Vega':np.nan,'THETA':np.nan,'Pr. opz.':np.nan,'V. Temp.':np.nan,'V. Intr.':np.nan})
    dte=max((pd.to_datetime(r.Scadenza).date()-dt).days,0);t=dte/365;k=float(r.Strike);s=float(r['Vol opz (%)'])/100;typ=r['Call/Put'];fac=(1 if r['Buy/Sell']=='Buy' else -1)*float(r['N° opz'])*mult
    intr=max(spot-k,0) if typ=='Call' else max(k-spot,0);xtm='ATM' if abs(spot-k)/spot<=.005 else ('ITM' if ((typ=='Call' and spot>k)or(typ=='Put' and spot<k)) else 'OTM');theo=float(b76(spot,k,t,s,rate,typ))
    if t<=0:return pd.Series({'DTE':dte,'xTM':xtm,'Delta':0.,'Gamma':0.,'Vega':0.,'THETA':0.,'Pr. opz.':theo,'V. Temp.':0.,'V. Intr.':intr})
    rt=np.sqrt(t);d1=(np.log(spot/k)+.5*s*s*t)/(s*rt);disc=np.exp(-rate*t);delta=disc*(cdf(d1) if typ=='Call' else-cdf(-d1));gamma=disc*pdf(d1)/(spot*s*rt);vega=disc*spot*pdf(d1)*rt*.01;theta=float(b76(spot,k,max(t-1/365,0),s,rate,typ))-theo
    return pd.Series({'DTE':dte,'xTM':xtm,'Delta':fac*float(delta),'Gamma':fac*float(gamma),'Vega':fac*float(vega),'THETA':fac*theta,'Pr. opz.':theo,'V. Temp.':max(theo-intr,0),'V. Intr.':intr})
def pnl(x,r,dt):
    t=max((pd.to_datetime(r.Scadenza).date()-dt).days,0)/365;sign=1 if r['Buy/Sell']=='Buy' else-1
    return sign*float(r['N° opz'])*(b76(x,float(r.Strike),t,float(r['Vol opz (%)'])/100,rate,r['Call/Put'])-float(r.Premio))*mult
def total(x,dt): return sum((pnl(x,r,dt) for _,r in active.iterrows()),np.zeros_like(x,dtype=float))+cash

with st.expander('Salva / Carica progetto'):
    up=st.file_uploader('File JSON',type='json');a,b=st.columns([1,5]);load=a.button('Carica');slot=b.empty()
    if load and up:
        z=json.load(up);df=pd.DataFrame(z['opzioni']).rename(columns={'Acquisto/Vendita':'Buy/Sell','Numero opzioni':'N° opz'});df['Scadenza']=pd.to_datetime(df.Scadenza).dt.date
        if 'Buy/Sell' in df:df['Buy/Sell']=df['Buy/Sell'].replace({'Acquisto':'Buy','Vendita':'Sell'})
        for c in COLS:
            if c not in df:df[c]=False if c in ['Escludi temporaneamente','Del'] else None
        st.session_state.legs=df[COLS]
        params=z.get('parametri',{}).copy()
        if 'analysis' in params and 'simulation' not in params: params['simulation']=params['analysis']
        for k,v in params.items():
            if k not in ['start','analysis']: st.session_state[k]=pd.to_datetime(v).date() if k=='simulation' else v
        st.rerun()

r1=st.columns([1.2,1.25,1.6,1,1,1]);project_name=r1[0].text_input('Nome progetto',key='project_name');asset=r1[1].selectbox('Tipo sottostante',['Futures Commodity','Azioni','Futures Indici'],key='asset_class');selected=r1[2].selectbox('Sottostante',labels,key='product');product=catalog.iloc[labels.index(selected)];ticker,mult=product.Ticker,float(product.PL_Multiplier);spot=r1[3].number_input('Prezzo sottostante',min_value=.0001,step=.25,key='spot');cash=r1[4].number_input('Cash ($)',step=.01,key='cash');r1[5].metric('Ticker / Mult.',f'{ticker} ×{mult:g}')
r2=st.columns(6);today=r2[0].date_input('Oggi',value=date.today(),disabled=True);simulation=r2[1].date_input('Data simulazione',key='simulation');atmiv=r2[2].number_input('ATM IV (%)',min_value=.01,step=.1,key='atmiv');rf=r2[3].number_input('Tasso risk-free (%)',min_value=0.,step=.1,key='rf');pmin=r2[4].number_input('Range minimo',step=1.,key='pmin');pmax=r2[5].number_input('Range massimo',step=1.,key='pmax');rate=rf/100;st.divider()
base=st.session_state.legs.copy().rename(columns={'Acquisto/Vendita':'Buy/Sell','Numero opzioni':'N° opz'});base['Escludi temporaneamente']=base.get('Escludi temporaneamente',False);base['Escludi temporaneamente']=base['Escludi temporaneamente'].fillna(False).astype(bool);base['Del']=base.get('Del',False);base['Del']=base.Del.fillna(False).astype(bool);base=base[COLS];st.session_state.legs=base;active=base[(~base['Escludi temporaneamente']) & base.apply(valid,axis=1)].drop(columns=['Escludi temporaneamente','Del'])
t1,t2,t3=st.tabs(['Strategia','Comparazione 1','Comparazione 2'])
with t1:
    display=pd.concat([base,base.apply(lambda r:calc(r,simulation),axis=1)],axis=1);display['P&L Oggi']=display.apply(lambda r:pnl(np.array([spot]),r,today)[0] if valid(r) else np.nan,axis=1);display['P&L simulazione']=display.apply(lambda r:pnl(np.array([spot]),r,simulation)[0] if valid(r) else np.nan,axis=1)
    with st.form('editor'):
        edited=st.data_editor(display,num_rows='dynamic',use_container_width=True,disabled=['DTE','xTM','Delta','Gamma','Vega','THETA','Pr. opz.','V. Temp.','V. Intr.','P&L Oggi','P&L simulazione'],column_config={'Escludi temporaneamente':st.column_config.CheckboxColumn('Escludi temporaneamente'),'Del':st.column_config.CheckboxColumn('Del'),'Buy/Sell':st.column_config.SelectboxColumn('Buy/Sell',options=['Buy','Sell']),'Call/Put':st.column_config.SelectboxColumn('Call/Put',options=['Call','Put']),'Scadenza':st.column_config.DateColumn(format='DD/MM/YYYY')});update=st.form_submit_button('Calcola payoff',type='primary')
    if update:st.session_state.legs=edited[COLS];st.rerun()
    if st.button('Elimina righe selezionate'):
        st.session_state.legs=base[~base.Del].assign(Del=False).reset_index(drop=True);st.rerun()
    if not active.empty:
        g=active.apply(lambda r:calc(r,simulation),axis=1)[['Delta','Gamma','Vega','THETA']].sum()
        for c,n,v in zip(st.columns(4),g.index,g.values):c.metric(n,f'{v:,.3f}')
        x=np.linspace(pmin,pmax,2000);y_today,y_simulation=total(x,today),total(x,simulation);fig=go.Figure()
        if st.session_state.show_simulation:fig.add_trace(go.Scatter(x=x,y=y_simulation,name='P/L data simulazione',line={'width':4,'color':'#00a878'}))
        if st.session_state.show_today:fig.add_trace(go.Scatter(x=x,y=y_today,name='P/L oggi',line={'dash':'dash','color':'#3b82f6'}))
        fig.add_hline(y=0,line_color='gray');fig.add_vline(x=spot,line_dash='dash');fig.update_layout(title=f'{asset} — {selected}',hovermode='x unified',xaxis_title=f'Prezzo {ticker}',yaxis_title='P/L');st.plotly_chart(fig,use_container_width=True)
        q=st.columns([1.3,1.3,5]);q[0].checkbox('P/L data simulazione',key='show_simulation');q[1].checkbox('P/L oggi',key='show_today')
with t2:st.info('Comparazione 1 predisposta.')
with t3:st.info('Comparazione 2 predisposta.')
out=st.session_state.legs.drop(columns=['Escludi temporaneamente','Del']).copy();out.Scadenza=out.Scadenza.apply(lambda v:pd.to_datetime(v).date().isoformat() if pd.notna(v) else None);safe=re.sub(r'[^A-Za-z0-9_-]+','_',project_name).strip('_') or 'strategia_opzioni';data={'opzioni':out.to_dict('records'),'parametri':{'project_name':project_name,'asset_class':asset,'product':selected,'spot':spot,'atmiv':atmiv,'simulation':simulation.isoformat(),'rf':rf,'cash':cash,'pmin':pmin,'pmax':pmax,'show_simulation':st.session_state.show_simulation,'show_today':st.session_state.show_today}};slot.download_button('Salva progetto',json.dumps(data,ensure_ascii=False,indent=2).encode(),f'{safe}_{date.today().isoformat()}.json','application/json')
