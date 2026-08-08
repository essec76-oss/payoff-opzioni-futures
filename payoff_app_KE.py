from datetime import date
from math import erf, pi
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title='Payoff Opzioni', layout='wide')
st.title('Payoff Opzioni')

try:
    catalog = pd.read_csv('sottostanti.csv')
except FileNotFoundError:
    st.error('Manca il file sottostanti.csv.')
    st.stop()

COLS = ['Escludi', 'Del', 'Buy/Sell', 'Call/Put', 'N° opz', 'Strike', 'Vol opz (%)', 'Premio', 'Scadenza']
EXP = date(2026, 11, 20)
DEFAULT = pd.DataFrame([
    [False, False, 'Sell', 'Put', 1, 600., 26.5, 3.9396, EXP],
    [False, False, 'Sell', 'Call', 1, 1200., 48.1, 2.6898, EXP]
], columns=COLS)

st.session_state.setdefault('legs', DEFAULT.copy())
labels = (catalog.Ticker + ' - ' + catalog.Nome).tolist()
default = 'KE - Wheat Kansas' if 'KE - Wheat Kansas' in labels else labels[0]
for k, v in {
    'name': 'Strategia opzioni', 'product': default, 'spot': 721.75, 'atmiv': 30.,
    'start': date(2026, 8, 7), 'analysis': EXP, 'rf': 0., 'comm': 0.,
    'pmin': 450., 'pmax': 1350., 'showa': True, 'shows': True
}.items():
    st.session_state.setdefault(k, v)

with st.sidebar:
    st.header('Salva / Carica strategia')
    up = st.file_uploader('File strategia (.json)', type='json')
    a, b = st.columns(2)
    load = a.button('Carica', use_container_width=True)
    save_slot = b.empty()
    if load and up:
        z = json.load(up)
        df = pd.DataFrame(z['opzioni'])
        df = df.rename(columns={'Acquisto/Vendita': 'Buy/Sell', 'Numero opzioni': 'N° opz'})
        if 'Buy/Sell' in df:
            df['Buy/Sell'] = df['Buy/Sell'].replace({'Acquisto': 'Buy', 'Vendita': 'Sell'})
        df['Scadenza'] = pd.to_datetime(df['Scadenza']).dt.date
        for c in COLS:
            if c not in df:
                df[c] = False if c in ['Escludi', 'Del'] else None
        st.session_state.legs = df[COLS]
        for k, v in z['parametri'].items():
            st.session_state[k] = pd.to_datetime(v).date() if k in ['start', 'analysis'] else v
        st.rerun()

    st.header('Parametri strategia')
    name = st.text_input('Nome strategia', key='name')
    selected = st.selectbox('Sottostante', labels, key='product')
    product = catalog.iloc[labels.index(selected)]
    ticker, mult = product.Ticker, float(product.PL_Multiplier)
    spot = st.number_input('Prezzo sottostante corrente', step=.25, key='spot')
    atmiv = st.number_input('ATM IV globale (%)', min_value=.01, step=.1, key='atmiv')
    start = st.date_input('Data di partenza delle operazioni', key='start')
    analysis = st.date_input('Data di analisi', key='analysis')
    showa = st.checkbox('Mostra P/L alla data di analisi', key='showa')
    shows = st.checkbox('Mostra P/L alla data di partenza', key='shows')
    rf = st.number_input('Tasso risk-free (%)', min_value=0., step=.1, key='rf')
    comm = st.number_input('Commissioni totali', step=.01, key='comm')
    pmin = st.number_input('Range minimo', step=1., key='pmin')
    pmax = st.number_input('Range massimo', step=1., key='pmax')


def cdf(x):
    return .5 * (1 + np.vectorize(erf)(x / np.sqrt(2)))


def pdf(x):
    return np.exp(-x * x / 2) / np.sqrt(2 * pi)


def valid(r):
    try:
        return pd.notna(r.Scadenza) and float(r.Strike) > 0 and float(r['Vol opz (%)']) > 0 and float(r['N° opz']) > 0
    except (TypeError, ValueError):
        return False


def b76(f, k, t, s, r, typ):
    intr = np.maximum(f - k, 0) if typ == 'Call' else np.maximum(k - f, 0)
    if t <= 0:
        return intr
    v = s * np.sqrt(t)
    d1 = (np.log(np.maximum(f, 1e-12) / k) + .5 * s * s * t) / v
    d2 = d1 - v
    d = np.exp(-r * t)
    return d * (f * cdf(d1) - k * cdf(d2)) if typ == 'Call' else d * (k * cdf(-d2) - f * cdf(-d1))


def greek(r):
    keys = {'Delta': np.nan, 'Gamma': np.nan, 'Vega': np.nan, 'THETA': np.nan}
    if not valid(r):
        return pd.Series(keys)
    t = max((pd.to_datetime(r.Scadenza).date() - start).days, 0) / 365
    if t <= 0:
        return pd.Series({'Delta': 0., 'Gamma': 0., 'Vega': 0., 'THETA': 0.})
    s = float(r['Vol opz (%)']) / 100
    k = float(r.Strike)
    q = float(r['N° opz']) * mult * (1 if r['Buy/Sell'] == 'Buy' else -1)
    v = s * np.sqrt(t)
    d1 = (np.log(spot / k) + .5 * s * s * t) / v
    disc = np.exp(-(rf / 100) * t)
    delta = disc * (cdf(d1) if r['Call/Put'] == 'Call' else -cdf(-d1))
    gamma = disc * pdf(d1) / (spot * v)
    vega = disc * spot * pdf(d1) * np.sqrt(t) * .01
    price_today = b76(spot, k, t, s, rf / 100, r['Call/Put'])
    price_tomorrow = b76(spot, k, max(t - 1 / 365, 0), s, rf / 100, r['Call/Put'])
    theta = price_tomorrow - price_today
    return pd.Series({'Delta': q * delta, 'Gamma': q * gamma, 'Vega': q * vega, 'THETA': q * theta})


base = st.session_state.legs.copy()
base = base.rename(columns={'Acquisto/Vendita': 'Buy/Sell', 'Numero opzioni': 'N° opz'})
if 'Buy/Sell' in base:
    base['Buy/Sell'] = base['Buy/Sell'].replace({'Acquisto': 'Buy', 'Vendita': 'Sell'})
for c in ['Escludi', 'Del']:
    if c not in base:
        base[c] = False
    base[c] = base[c].fillna(False).astype(bool)
st.session_state.legs = base[COLS]

display = base.copy()
display['DTE'] = display.Scadenza.apply(lambda x: max((pd.to_datetime(x).date() - start).days, 0) if pd.notna(x) else np.nan)
display[['Delta', 'Gamma', 'Vega', 'THETA']] = display.apply(greek, axis=1)

st.subheader('Opzioni')
with st.form('editor'):
    edited = st.data_editor(
        display, num_rows='dynamic', use_container_width=True,
        disabled=['DTE', 'Delta', 'Gamma', 'Vega', 'THETA'],
        column_config={
            'Escludi': st.column_config.CheckboxColumn('Escludi', default=False),
            'Del': st.column_config.CheckboxColumn('Del', default=False),
            'Buy/Sell': st.column_config.SelectboxColumn('Buy/Sell', options=['Buy', 'Sell']),
            'Call/Put': st.column_config.SelectboxColumn('Call/Put', options=['Call', 'Put']),
            'Scadenza': st.column_config.DateColumn(format='DD/MM/YYYY'),
            'DTE': st.column_config.NumberColumn(format='%d'),
            'Delta': st.column_config.NumberColumn(format='%.2f'),
            'Gamma': st.column_config.NumberColumn(format='%.4f'),
            'Vega': st.column_config.NumberColumn(format='%.2f'),
            'THETA': st.column_config.NumberColumn(format='%.2f'),
        }
    )
    update = st.form_submit_button('Aggiorna calcoli')

if update:
    new = edited[COLS].copy()
    new['Escludi'] = new['Escludi'].fillna(False).astype(bool)
    new['Del'] = new['Del'].fillna(False).astype(bool)
    st.session_state.legs = new
    st.rerun()

if st.button('Elimina righe selezionate', type='primary'):
    if not st.session_state.legs.Del.any():
        st.warning('Spunta Del su almeno una riga.')
    else:
        st.session_state.legs = st.session_state.legs[~st.session_state.legs.Del].drop(columns='Del').assign(Del=False).reset_index(drop=True)
        st.rerun()

active = st.session_state.legs[(~st.session_state.legs.Escludi) & st.session_state.legs.apply(valid, axis=1)].drop(columns='Del')


def pnl(x, r, target):
    t = max((pd.to_datetime(r.Scadenza).date() - target).days, 0) / 365
    sign = 1 if r['Buy/Sell'] == 'Buy' else -1
    return sign * float(r['N° opz']) * (b76(x, float(r.Strike), t, float(r['Vol opz (%)']) / 100, rf / 100, r['Call/Put']) - float(r.Premio)) * mult


def total(x, target):
    return sum((pnl(x, r, target) for _, r in active.iterrows()), np.zeros_like(x, dtype=float)) - comm


def be(x, y):
    return [round(x[i] + (x[i + 1] - x[i]) * (-y[i]) / (y[i + 1] - y[i]), 2) for i in range(len(x) - 1) if y[i] * y[i + 1] < 0]


def pop():
    t = (analysis - start).days / 365
    if t <= 0:
        return 100. if total(np.array([spot]), analysis)[0] > 0 else 0.
    s = atmiv / 100
    z = max(12 * s * np.sqrt(t), .25)
    e = np.concatenate(([0], np.geomspace(max(spot * np.exp(-z), 1e-8), spot * np.exp(z), 10000), [np.inf]))
    q = (np.log(e[1:-1] / spot) + .5 * s * s * t) / (s * np.sqrt(t))
    m = np.diff(np.r_[0, cdf(q), 1])
    mid = np.r_[e[1] / 2, np.sqrt(e[1:-2] * e[2:-1]), e[-2] * 2]
    return float(m[total(mid, analysis) > 0].sum() * 100)


if active.empty:
    st.warning('Inserisci almeno un’opzione valida.')
    st.stop()

g = active.apply(greek, axis=1).sum()
st.subheader('Totali greche')
c1, c2, c3, c4 = st.columns(4)
c1.metric('Delta totale', f"{g['Delta']:,.2f}")
c2.metric('Gamma totale', f"{g['Gamma']:,.4f}")
c3.metric('Vega totale (+1% IV)', f"{g['Vega']:,.2f}")
c4.metric('Theta totale', f"{g['THETA']:,.2f}")

x = np.linspace(pmin, pmax, 2000)
ys, ya = total(x, start), total(x, analysis)
fig = go.Figure()
if showa:
    fig.add_trace(go.Scatter(x=x, y=ya, name='P/L data analisi', line={'width': 4, 'color': '#00a878'}))
if shows:
    fig.add_trace(go.Scatter(x=x, y=ys, name='P/L data partenza', line={'dash': 'dash', 'color': '#3b82f6'}))
fig.add_hline(y=0, line_color='gray')
fig.add_vline(x=spot, line_dash='dash', line_color='#e69f00')
fig.update_layout(title=f'{name} - {selected}', hovermode='x unified', xaxis_title=f'Prezzo {ticker}', yaxis_title='P/L')
st.plotly_chart(fig, use_container_width=True)
st.metric('PoP data analisi', f'{pop():.1f}%')
st.write('Break-even data analisi:', ', '.join(map(str, be(x, ya))) or 'Nessuno')

out = st.session_state.legs.drop(columns='Del').copy()
out.Scadenza = out.Scadenza.apply(lambda z: pd.to_datetime(z).date().isoformat() if pd.notna(z) else None)
data = {
    'opzioni': out.to_dict('records'),
    'parametri': {
        'name': name, 'product': selected, 'spot': spot, 'atmiv': atmiv,
        'start': start.isoformat(), 'analysis': analysis.isoformat(), 'rf': rf,
        'comm': comm, 'pmin': pmin, 'pmax': pmax, 'showa': showa, 'shows': shows
    }
}
save_slot.download_button('Salva', json.dumps(data, ensure_ascii=False).encode(), 'strategia_opzioni.json', 'application/json', use_container_width=True)
