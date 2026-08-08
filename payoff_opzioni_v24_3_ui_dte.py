from pathlib import Path

source = Path(__file__).with_name('payoff_opzioni_v24_3_completo.py')
text = source.read_text(encoding='utf-8')

old_r2 = "r2=st.columns(8);start_date=r2[0].date_input('Data partenza',key='start');analysis_date=r2[1].date_input('Data analisi',key='analysis');atmiv=r2[2].number_input('ATM IV (%)',min_value=.01,step=.1,key='atmiv');rate_pct=r2[3].number_input('Tasso risk-free (%)',min_value=0.,step=.1,key='rf');pmin=r2[4].number_input('Range minimo',step=1.,key='pmin');pmax=r2[5].number_input('Range massimo',step=1.,key='pmax');show_analysis=r2[6].checkbox('P/L a scadenza',key='showa');show_start=r2[7].checkbox('P/L at now',key='shows');rate=rate_pct/100"
new_r2 = "r2=st.columns(6);start_date=r2[0].date_input('Data partenza',key='start');analysis_date=r2[1].date_input('Data analisi',key='analysis');atmiv=r2[2].number_input('ATM IV (%)',min_value=.01,step=.1,key='atmiv');rate_pct=r2[3].number_input('Tasso risk-free (%)',min_value=0.,step=.1,key='rf');pmin=r2[4].number_input('Range minimo',step=1.,key='pmin');pmax=r2[5].number_input('Range massimo',step=1.,key='pmax');rate=rate_pct/100"
if old_r2 not in text:
    raise RuntimeError('Blocco parametri non trovato nella versione di partenza.')
text = text.replace(old_r2, new_r2)

old_display = "display=pd.concat([base,base.apply(lambda r:pd.Series(values(r,start_date)),axis=1)],axis=1)"
new_display = "display=pd.concat([base,base.apply(lambda r:pd.Series(values(r,analysis_date)),axis=1)],axis=1)"
if old_display not in text:
    raise RuntimeError('Blocco DTE non trovato nella versione di partenza.')
text = text.replace(old_display, new_display)

old_chart = "g=active.apply(lambda r:pd.Series(values(r,start_date)),axis=1)[['Delta','Gamma','Vega','THETA']].sum();x=np.linspace(pmin,pmax,2000);y_now=total(x,start_date);y_exp=sum((pnl(x,r,pd.to_datetime(r.Scadenza).date()) for _,r in active.iterrows()),np.zeros_like(x))+cash;fig=go.Figure()"
new_chart = "g=active.apply(lambda r:pd.Series(values(r,start_date)),axis=1)[['Delta','Gamma','Vega','THETA']].sum();x=np.linspace(pmin,pmax,2000);y_now=total(x,start_date);y_exp=sum((pnl(x,r,pd.to_datetime(r.Scadenza).date()) for _,r in active.iterrows()),np.zeros_like(x))+cash;chart_controls=st.columns([1.3,1.3,6]);show_analysis=chart_controls[0].checkbox('P/L a scadenza',key='showa');show_start=chart_controls[1].checkbox('P/L at now',key='shows');fig=go.Figure()"
if old_chart not in text:
    raise RuntimeError('Blocco grafico non trovato nella versione di partenza.')
text = text.replace(old_chart, new_chart)

exec(compile(text, str(source), 'exec'), globals())