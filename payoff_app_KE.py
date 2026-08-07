# FILE COMPLETO V21
# Sostituisci integralmente payoff_app_KE.py con questo file.
from datetime import date
from math import erf, pi
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Payoff Opzioni', layout='wide')
st.title('Payoff Opzioni')
try:
    catalog=pd.read_csv('sottostanti.csv')
except FileNotFoundError:
    st.error('Manca il file sottostanti.csv.');st.stop()
COLS=['Escludi','Del','Acquisto/Vendita','Call/Put','Numero opzioni','Strike','Vol opz (%)','Premio','Scadenza']
EXP=date(2026,11,20)
DEFAULT=pd.DataFrame([[False,False,'Vendita','Put',1,600.,26.5,3.9396,EXP],[False,False,'Vendita','Call',1,1200.,48.1,2.6898,EXP]],columns=COLS)
st.session_state.setdefault('legs',DEFAULT.copy())
for k,v in {'spot':721.75,'start':date(2026,8,7),'rf':4.0}.items():st.session_state.setdefault(k,v)
labels=(catalog['Ticker']+' - '+catalog['Nome']).tolist()
with st.sidebar:
    selected=st.selectbox('Sottostante',labels)
    product=catalog.iloc[labels.index(selected)]
    spot=st.number_input('Prezzo sottostante corrente',step=.25,key='spot')
    start=st.date_input('Data di partenza delle operazioni',key='start')
    rf=st.number_input('Tasso risk-free (%)',min_value=0.,step=.1,key='rf')

def cdf(x):return .5*(1+np.vectorize(erf)(x/np.sqrt(2)))
def pdf(x):return np.exp(-x*x/2)/np.sqrt(2*pi)
def valid(r):
    try:return pd.notna(r['Scadenza']) and float(r['Strike'])>0 and float(r['Vol opz (%)'])>0 and float(r['Numero opzioni'])>0
    except:return False
def greek(r):
    if not valid(r):return pd.Series({'Delta':np.nan,'Gamma':np.nan,'Vega (per 1%)':np.nan,'Theta (al giorno)':np.nan})
    t=max((pd.to_datetime(r['Scadenza']).date()-start).days,0)/365
    if t<=0:return pd.Series({'Delta':0.,'Gamma':0.,'Vega (per 1%)':0.,'Theta (al giorno)':0.})
    mult=float(product['PL_Multiplier']);s=float(r['Vol opz (%)'])/100;k=float(r['Strike']);q=float(r['Numero opzioni'])*mult*(1 if r['Acquisto/Vendita']=='Acquisto' else -1);v=s*np.sqrt(t);d1=(np.log(spot/k)+.5*s*s*t)/v;disc=np.exp(-(rf/100)*t);delta=disc*(cdf(d1) if r['Call/Put']=='Call' else -cdf(-d1));gamma=disc*pdf(d1)/(spot*v);vega=disc*spot*pdf(d1)*np.sqrt(t)*.01
    return pd.Series({'Delta':q*delta,'Gamma':q*gamma,'Vega (per 1%)':q*vega,'Theta (al giorno)':0.})
# Normalizzazione: impedisce None e checkbox invisibili.
base=st.session_state.legs.copy()
for col in ['Escludi','Del']:
    if col not in base:base[col]=False
    base[col]=base[col].fillna(False).astype(bool)
st.session_state.legs=base[COLS]
display=base.copy();display['DTE mancanti']=display['Scadenza'].apply(lambda x:max((pd.to_datetime(x).date()-start).days,0) if pd.notna(x) else np.nan);display[['Delta','Gamma','Vega (per 1%)','Theta (al giorno)']]=display.apply(greek,axis=1)
st.subheader('Opzioni')
with st.form('editor'):
    edited=st.data_editor(display,num_rows='dynamic',use_container_width=True,disabled=['DTE mancanti','Delta','Gamma','Vega (per 1%)','Theta (al giorno)'],column_config={'Escludi':st.column_config.CheckboxColumn('Escludi',default=False),'Del':st.column_config.CheckboxColumn('Del',default=False),'Acquisto/Vendita':st.column_config.SelectboxColumn(options=['Acquisto','Vendita']),'Call/Put':st.column_config.SelectboxColumn(options=['Call','Put']),'Scadenza':st.column_config.DateColumn(format='DD/MM/YYYY'),'DTE mancanti':st.column_config.NumberColumn(format='%d'),'Delta':st.column_config.NumberColumn(format='%.2f'),'Gamma':st.column_config.NumberColumn(format='%.4f'),'Vega (per 1%)':st.column_config.NumberColumn(format='%.2f'),'Theta (al giorno)':st.column_config.NumberColumn(format='%.2f')})
    update=st.form_submit_button('Aggiorna calcoli')
if update:
    new=edited[COLS].copy();new['Escludi']=new['Escludi'].fillna(False).astype(bool);new['Del']=new['Del'].fillna(False).astype(bool);st.session_state.legs=new;st.rerun()
if st.button('Elimina righe selezionate',type='primary'):
    if not st.session_state.legs['Del'].any():st.warning('Spunta Del su almeno una riga.')
    else:st.session_state.legs=st.session_state.legs[~st.session_state.legs['Del']].drop(columns='Del').assign(Del=False).reset_index(drop=True);st.rerun()
active=st.session_state.legs[(~st.session_state.legs['Escludi']) & st.session_state.legs.apply(valid,axis=1)]
g=active.apply(greek,axis=1).sum() if not active.empty else pd.Series({'Delta':0.,'Gamma':0.,'Vega (per 1%)':0.,'Theta (al giorno)':0.})
st.subheader('Totali greche');a,b,c,d=st.columns(4);a.metric('Delta totale',f"{g['Delta']:,.2f}");b.metric('Gamma totale',f"{g['Gamma']:,.4f}");c.metric('Vega totale (+1% IV)',f"{g['Vega (per 1%)']:,.2f}");d.metric('Theta totale',f"{g['Theta (al giorno)']:,.2f}")
