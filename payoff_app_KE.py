from datetime import date
from math import erf
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Payoff Opzioni e Futures", layout="wide")
st.title("Payoff Opzioni e Futures")
st.caption("P/L At Now, data di analisi, calendar e PoP teorica")

DEFAULT_EXPIRY = date(2026, 11, 20)
DEFAULT_LEGS = pd.DataFrame([
    {"Escludi": False, "Strumento": "Opzione", "Lato": "Short", "Tipo": "Put", "Quantita": 1, "Strike": 600.0, "Scadenza opzione": DEFAULT_EXPIRY, "Premio/Ingresso": 3.9396, "IV %": 26.5, "Multiplier": 50.0},
    {"Escludi": False, "Strumento": "Opzione", "Lato": "Short", "Tipo": "Call", "Quantita": 1, "Strike": 1200.0, "Scadenza opzione": DEFAULT_EXPIRY, "Premio/Ingresso": 2.6898, "IV %": 48.1, "Multiplier": 50.0},
])
if "legs" not in st.session_state:
    st.session_state.legs = DEFAULT_LEGS.copy()

with st.sidebar:
    st.header("Parametri strategia")
    name = st.text_input("Nome strategia", "KE Dec 2026 - Short Strangle")
    underlying = st.text_input("Future sottostante", "KE Dec 2026")
    future_price = st.number_input("Prezzo future corrente", value=721.75, step=0.25, format="%.4f")
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
    st.caption("At Now, data di analisi e PoP usano la sola ATM IV globale.")
    st.divider()
    commissions = st.number_input("Commissioni totali", value=0.0, step=0.01)
    price_min = st.number_input("Range minimo", value=450.0, step=1.0)
    price_max = st.number_input("Range massimo", value=1350.0, step=1.0)
    if st.button("Ripristina esempio KE"):
        st.session_state.legs = DEFAULT_LEGS.copy()
        st.rerun()

st.subheader("Gambe")
st.caption("Ogni opzione ha la propria scadenza. Spunta Escludi per rimuovere una gamba dai calcoli senza cancellarla.")
legs = st.data_editor(
    st.session_state.legs, num_rows="dynamic", use_container_width=True,
    column_config={
        "Escludi": st.column_config.CheckboxColumn("Escludi", default=False),
        "Strumento": st.column_config.SelectboxColumn(options=["Opzione", "Future"], required=True),
        "Lato": st.column_config.SelectboxColumn(options=["Long", "Short"], required=True),
        "Tipo": st.column_config.SelectboxColumn(options=["Call", "Put", "Future"], required=True),
        "Quantita": st.column_config.NumberColumn(min_value=0.0, step=1.0, required=True),
        "Strike": st.column_config.NumberColumn(step=0.25),
        "Scadenza opzione": st.column_config.DateColumn(format="DD/MM/YYYY", required=True),
        "Premio/Ingresso": st.column_config.NumberColumn(step=0.0001, format="%.4f", required=True),
        "IV %": st.column_config.NumberColumn(step=0.1, help="Informativa: i calcoli usano ATM IV globale"),
        "Multiplier": st.column_config.NumberColumn(min_value=0.0001, step=1.0, required=True),
    }, key="editor")
st.session_state.legs = legs

required = ["Escludi", "Strumento", "Lato", "Tipo", "Quantita", "Strike", "Scadenza opzione", "Premio/Ingresso", "Multiplier"]
if price_max <= price_min or legs.empty or legs[required].isnull().any().any():
    st.error("Controlla range grafico e dati obbligatori della tabella.")
    st.stop()
if analysis_date < valuation_date:
    st.error("La data di analisi deve essere uguale o successiva alla data di valutazione.")
    st.stop()
if not show_analysis and not show_now:
    st.warning("Seleziona almeno una curva da mostrare.")
    st.stop()
active = legs[~legs["Escludi"]].copy()
if active.empty:
    st.warning("Tutte le gambe sono escluse. Togli Escludi da almeno una riga.")
    st.stop()


def row_expiry(row):
    return pd.to_datetime(row["Scadenza opzione"]).date()


def ncdf(x):
    return 0.5 * (1.0 + np.vectorize(erf)(x / np.sqrt(2.0)))


def black76(f, k, ty, sigma, rate, typ):
    intrinsic = np.maximum(f-k, 0.0) if typ == "Call" else np.maximum(k-f, 0.0)
    if ty <= 0 or sigma <= 0:
        return intrinsic
    f = np.maximum(f, 1e-12)
    vs = sigma*np.sqrt(ty)
    d1 = (np.log(f/k) + .5*sigma*sigma*ty) / vs
    d2 = d1-vs
    disc = np.exp(-rate*ty)
    return disc*(f*ncdf(d1)-k*ncdf(d2)) if typ == "Call" else disc*(k*ncdf(-d2)-f*ncdf(-d1))


def pnl_at_date(p, row, target_date):
    sign = 1 if row["Lato"] == "Long" else -1
    q, m, entry = sign*float(row["Quantita"]), float(row["Multiplier"]), float(row["Premio/Ingresso"])
    if row["Strumento"] == "Future":
        return q*(p-entry)*m
    rem = max((row_expiry(row)-target_date).days, 0)/365.0
    theoretical = black76(p, float(row["Strike"]), rem, atm_iv/100, risk_free/100, row["Tipo"])
    return q*(theoretical-entry)*m


def total(p, target_date):
    return sum((pnl_at_date(p, row, target_date) for _, row in active.iterrows()), np.zeros_like(p, dtype=float))-commissions


def crossings(x, y):
    out=[]
    for i in range(len(x)-1):
        if y[i] == 0: out.append(x[i])
        elif y[i]*y[i+1] < 0: out.append(x[i]+(x[i+1]-x[i])*(-y[i])/(y[i+1]-y[i]))
    return sorted(set(round(v,4) for v in out))


def pop_at_analysis():
    ty = (analysis_date-valuation_date).days/365.0
    if ty <= 0:
        return 100.0 if total(np.array([future_price]), analysis_date)[0] > 0 else 0.0
    sigma = atm_iv/100
    spread=max(12*sigma*np.sqrt(ty), .25)
    low, high=max(future_price*np.exp(-spread),1e-8), future_price*np.exp(spread)
    strikes=active.loc[active["Strumento"]=="Opzione","Strike"].astype(float)
    if not strikes.empty:
        low=min(low,max(strikes.min()*.05,1e-8)); high=max(high,strikes.max()*5)
    edges=np.concatenate(([0.0],np.geomspace(low,high,12000),[np.inf]))
    z=(np.log(edges[1:-1]/future_price)+.5*sigma*sigma*ty)/(sigma*np.sqrt(ty))
    masses=np.diff(np.concatenate(([0.0],ncdf(z),[1.0])))
    mids=np.empty(len(masses)); mids[0]=low/2; mids[-1]=high*2; mids[1:-1]=np.sqrt(edges[1:-2]*edges[2:-1])
    return float(np.sum(masses[total(mids,analysis_date)>0])*100)

prices=np.linspace(price_min,price_max,2000)
now_total=total(prices,valuation_date)
analysis_total=total(prices,analysis_date)
now_be, analysis_be=crossings(prices,now_total),crossings(prices,analysis_total)
now_current=total(np.array([future_price]),valuation_date)[0]
analysis_current=total(np.array([future_price]),analysis_date)[0]
pop=pop_at_analysis()
dte_analysis=(analysis_date-valuation_date).days

left,right=st.columns([3,1])
with left:
    fig=go.Figure()
    if show_components:
        for _,row in active.iterrows():
            fig.add_trace(go.Scatter(x=prices,y=pnl_at_date(prices,row,analysis_date),mode="lines",opacity=.3,line={"dash":"dot"},name=f"Analisi {row['Lato']} {row['Tipo']} {row['Strike']}"))
    if show_analysis:
        fig.add_trace(go.Scatter(x=prices,y=analysis_total,mode="lines",line={"width":4,"color":"#00a878"},name="P/L data analisi"))
        for be in analysis_be: fig.add_vline(x=be,line_dash="dot",line_color="#d55e00",annotation_text=f"BE analisi {be:.4f}")
    if show_now:
        fig.add_trace(go.Scatter(x=prices,y=now_total,mode="lines",line={"width":2,"dash":"dash","color":"#3b82f6"},name="P/L At Now"))
        for be in now_be: fig.add_vline(x=be,line_dash="dash",line_color="#3b82f6",annotation_text=f"BE now {be:.4f}")
    fig.add_hline(y=0,line_color="gray")
    fig.add_vline(x=future_price,line_dash="dash",line_color="#e69f00",annotation_text=f"Future {future_price:.2f}")
    fig.update_layout(title=f"{name} - curve P/L",xaxis_title=f"Prezzo {underlying}",yaxis_title="P/L (in base al multiplier)",hovermode="x unified",margin={"l":10,"r":10,"t":50,"b":10})
    st.plotly_chart(fig,use_container_width=True)
with right:
    st.subheader("Metriche")
    st.metric("Gambe incluse",f"{len(active)} / {len(legs)}")
    st.metric("Future corrente",f"{future_price:.4f}")
    st.metric("DTE data analisi",dte_analysis)
    st.metric("ATM IV globale",f"{atm_iv:.1f}%")
    st.metric("PoP teorica data analisi",f"{pop:.1f}%")
    if show_analysis: st.metric("P/L data analisi al prezzo attuale",f"{analysis_current:,.2f}")
    if show_now: st.metric("P/L At Now al prezzo attuale",f"{now_current:,.2f}")

levels=sorted(set([price_min,future_price,price_max]+active.loc[active["Strumento"]=="Opzione","Strike"].astype(float).tolist()+analysis_be+now_be))
scenarios=pd.DataFrame({"Prezzo":levels})
if show_analysis: scenarios["P/L data analisi"]=total(np.array(levels),analysis_date)
if show_now: scenarios["P/L At Now"]=total(np.array(levels),valuation_date)
st.subheader("Scenari")
st.dataframe(scenarios.style.format({c:"{:.2f}" for c in scenarios.columns}),use_container_width=True)
st.download_button("Scarica le gambe in CSV",legs.to_csv(index=False).encode("utf-8"),"gambe_strategia.csv","text/csv")
st.info("La data di analisi valorizza ogni opzione alla sua scadenza individuale: intrinseco se gia scaduta, Black-76 con tempo residuo se ancora aperta.")
