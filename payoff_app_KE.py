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
    st.error('Manca il file sottostanti.csv nella stessa cartella dell’app.')
    st.stop()

COLS = ['Del', 'Buy/Sell', 'Call/Put', 'N° opz', 'Strike', 'Vol opz (%)', 'Premio', 'Scadenza']
EXP = date(2026, 11, 20)
DEFAULT = pd.DataFrame([
    [False, 'Sell', 'Put', 1, 600., 26.5, 3.9396, EXP],
    [False, 'Sell', 'Call', 1, 1200., 48.1, 2.6898, EXP],
], columns=COLS)

st.session_state.setdefault('legs', DEFAULT.copy())
labels = (catalog.Ticker.astype(str) + ' - ' + catalog.Nome.astype(str)).tolist()
default_product = 'KE - Wheat Kansas' if 'KE - Wheat Kansas' in labels else labels[0]
for key, value in {
    'asset_class': 'Futures Commodity', 'product': default_product, 'spot': 721.75,
    'atmiv': 30., 'start': date(2026, 8, 7), 'analysis': EXP, 'rf': 0.,
    'cash': 0., 'pmin': 450., 'pmax': 1350., 'showa': True, 'shows': True,
}.items():
    st.session_state.setdefault(key, value)


def cdf(x):
    return .5 * (1 + np.vectorize(erf)(x / np.sqrt(2)))


def pdf(x):
    return np.exp(-x * x / 2) / np.sqrt(2 * pi)


def valid(r):
    try:
        return pd.notna(r.Scadenza) and float(r.Strike) > 0 and float(r['Vol opz (%)']) > 0 and float(r['N° opz']) > 0
    except (TypeError, ValueError):
        return False


def b76(f, k, t, sigma, rate, option_type):
    intrinsic = np.maximum(f - k, 0) if option_type == 'Call' else np.maximum(k - f, 0)
    if t <= 0 or sigma <= 0:
        return intrinsic
    v = sigma * np.sqrt(t)
    d1 = (np.log(np.maximum(f, 1e-12) / k) + .5 * sigma * sigma * t) / v
    d2 = d1 - v
    discount = np.exp(-rate * t)
    if option_type == 'Call':
        return discount * (f * cdf(d1) - k * cdf(d2))
    return discount * (k * cdf(-d2) - f * cdf(-d1))


def values(r, valuation_date):
    missing = {'DTE': np.nan, 'xTM': '', 'Delta': np.nan, 'Gamma': np.nan, 'Vega': np.nan, 'THETA': np.nan, 'Pr. opz.': np.nan, 'V. Temp.': np.nan, 'V. Intr.': np.nan}
    if not valid(r):
        return missing
    dte = max((pd.to_datetime(r.Scadenza).date() - valuation_date).days, 0)
    t = dte / 365
    k, sigma, typ = float(r.Strike), float(r['Vol opz (%)']) / 100, r['Call/Put']
    factor = (1 if r['Buy/Sell'] == 'Buy' else -1) * float(r['N° opz']) * multiplier
    intrinsic = max(spot - k, 0) if typ == 'Call' else max(k - spot, 0)
    xtm = 'ATM' if abs(spot - k) / spot <= .005 else ('ITM' if ((typ == 'Call' and spot > k) or (typ == 'Put' and spot < k)) else 'OTM')
    theoretical = float(b76(spot, k, t, sigma, rate, typ))
    if t <= 0:
        return {'DTE': dte, 'xTM': xtm, 'Delta': 0., 'Gamma': 0., 'Vega': 0., 'THETA': 0., 'Pr. opz.': theoretical, 'V. Temp.': 0., 'V. Intr.': intrinsic}
    root_t = np.sqrt(t)
    d1 = (np.log(spot / k) + .5 * sigma * sigma * t) / (sigma * root_t)
    discount = np.exp(-rate * t)
    delta = discount * (cdf(d1) if typ == 'Call' else -cdf(-d1))
    gamma = discount * pdf(d1) / (spot * sigma * root_t)
    vega = discount * spot * pdf(d1) * root_t * .01
    tomorrow = float(b76(spot, k, max(t - 1 / 365, 0), sigma, rate, typ))
    return {'DTE': dte, 'xTM': xtm, 'Delta': factor * float(delta), 'Gamma': factor * float(gamma), 'Vega': factor * float(vega), 'THETA': factor * (tomorrow - theoretical), 'Pr. opz.': theoretical, 'V. Temp.': max(theoretical - intrinsic, 0), 'V. Intr.': intrinsic}


def pnl(x, r, valuation_date):
    t = max((pd.to_datetime(r.Scadenza).date() - valuation_date).days, 0) / 365
    sign = 1 if r['Buy/Sell'] == 'Buy' else -1
    return sign * float(r['N° opz']) * (b76(x, float(r.Strike), t, float(r['Vol opz (%)']) / 100, rate, r['Call/Put']) - float(r.Premio)) * multiplier


def total(x, valuation_date):
    return sum((pnl(x, r, valuation_date) for _, r in active.iterrows()), np.zeros_like(x, dtype=float)) + cash


def break_evens(x, y):
    return [round(x[i] + (x[i + 1] - x[i]) * (-y[i]) / (y[i + 1] - y[i]), 2) for i in range(len(x) - 1) if y[i] * y[i + 1] < 0]


def pop():
    t = (analysis_date - start_date).days / 365
    if t <= 0:
        return 100. if total(np.array([spot]), analysis_date)[0] > 0 else 0.
    sigma = atmiv / 100
    z = max(12 * sigma * np.sqrt(t), .25)
    edges = np.concatenate(([0], np.geomspace(max(spot * np.exp(-z), 1e-8), spot * np.exp(z), 10000), [np.inf]))
    q = (np.log(edges[1:-1] / spot) + .5 * sigma * sigma * t) / (sigma * np.sqrt(t))
    masses = np.diff(np.r_[0, cdf(q), 1])
    midpoints = np.r_[edges[1] / 2, np.sqrt(edges[1:-2] * edges[2:-1]), edges[-2] * 2]
    return float(masses[total(midpoints, analysis_date) > 0].sum() * 100)


with st.expander('Salva / Carica strategia', expanded=False):
    upload = st.file_uploader('File strategia (.json)', type='json')
    load_col, save_col = st.columns([1, 5])
    load = load_col.button('Carica')
    download_slot = save_col.empty()
    if load and upload:
        saved = json.load(upload)
        df = pd.DataFrame(saved['opzioni']).rename(columns={'Acquisto/Vendita': 'Buy/Sell', 'Numero opzioni': 'N° opz'})
        if 'Buy/Sell' in df:
            df['Buy/Sell'] = df['Buy/Sell'].replace({'Acquisto': 'Buy', 'Vendita': 'Sell'})
        df['Scadenza'] = pd.to_datetime(df['Scadenza']).dt.date
        for col in COLS:
            if col not in df:
                df[col] = False if col == 'Del' else None
        st.session_state.legs = df[COLS]
        for key, value in saved['parametri'].items():
            st.session_state[key] = pd.to_datetime(value).date() if key in ['start', 'analysis'] else value
        st.session_state.setdefault('cash', saved['parametri'].get('comm', 0.))
        st.session_state.setdefault('asset_class', 'Futures Commodity')
        st.rerun()

r1 = st.columns([1.25, 1.6, 1, 1, 1])
asset_class = r1[0].selectbox('Tipo sottostante', ['Futures Commodity', 'Azioni', 'Futures Indici'], key='asset_class')
selected = r1[1].selectbox('Sottostante', labels, key='product')
product = catalog.iloc[labels.index(selected)]
ticker, multiplier = product.Ticker, float(product.PL_Multiplier)
spot = r1[2].number_input('Prezzo sottostante', min_value=.0001, step=.25, key='spot')
cash = r1[3].number_input('Cash ($)', step=.01, key='cash')
r1[4].metric('Ticker / Mult.', f'{ticker} ×{multiplier:g}')

r2 = st.columns([1, 1, 1, 1, 1, 1, 1.25, 1.25])
start_date = r2[0].date_input('Data partenza', key='start')
analysis_date = r2[1].date_input('Data analisi', key='analysis')
atmiv = r2[2].number_input('ATM IV (%)', min_value=.01, step=.1, key='atmiv')
rate_pct = r2[3].number_input('Tasso risk-free (%)', min_value=0., step=.1, key='rf')
pmin = r2[4].number_input('Range minimo', step=1., key='pmin')
pmax = r2[5].number_input('Range massimo', step=1., key='pmax')
show_analysis = r2[6].checkbox('P/L data analisi', key='showa')
show_start = r2[7].checkbox('P/L data partenza', key='shows')
st.divider()

rate = rate_pct / 100
base = st.session_state.legs.copy().rename(columns={'Acquisto/Vendita': 'Buy/Sell', 'Numero opzioni': 'N° opz'})
if 'Buy/Sell' in base:
    base['Buy/Sell'] = base['Buy/Sell'].replace({'Acquisto': 'Buy', 'Vendita': 'Sell'})
if 'Del' not in base:
    base['Del'] = False
base['Del'] = base['Del'].fillna(False).astype(bool)
base = base[COLS].copy()
st.session_state.legs = base
active = base[base.apply(valid, axis=1)].drop(columns='Del')

strategy_tab, comparison_1, comparison_2 = st.tabs(['Strategia', 'Comparazione 1', 'Comparazione 2'])
with strategy_tab:
    display = base.copy()
    display = pd.concat([display, display.apply(lambda r: pd.Series(values(r, start_date)), axis=1)], axis=1)
    display['P&L AtNow'] = display.apply(lambda r: pnl(np.array([spot]), r, start_date)[0] if valid(r) else np.nan, axis=1)
    display['P&L scad.'] = display.apply(lambda r: pnl(np.array([spot]), r, analysis_date)[0] if valid(r) else np.nan, axis=1)
    st.subheader('Option Trades')
    with st.form('editor'):
        edited = st.data_editor(display, num_rows='dynamic', use_container_width=True, disabled=['DTE', 'xTM', 'Delta', 'Gamma', 'Vega', 'THETA', 'Pr. opz.', 'V. Temp.', 'V. Intr.', 'P&L AtNow', 'P&L scad.'], column_config={
            'Del': st.column_config.CheckboxColumn('Del', default=False),
            'Buy/Sell': st.column_config.SelectboxColumn('Buy/Sell', options=['Buy', 'Sell']),
            'Call/Put': st.column_config.SelectboxColumn('Call/Put', options=['Call', 'Put']),
            'Scadenza': st.column_config.DateColumn(format='DD/MM/YYYY'),
            'DTE': st.column_config.NumberColumn(format='%d'),
            'Delta': st.column_config.NumberColumn(format='%.3f'),
            'Gamma': st.column_config.NumberColumn(format='%.5f'),
            'Vega': st.column_config.NumberColumn(format='%.3f'),
            'THETA': st.column_config.NumberColumn(format='%.3f'),
            'Pr. opz.': st.column_config.NumberColumn(format='%.4f'),
            'V. Temp.': st.column_config.NumberColumn(format='%.4f'),
            'V. Intr.': st.column_config.NumberColumn(format='%.4f'),
            'P&L AtNow': st.column_config.NumberColumn(format='%.2f'),
            'P&L scad.': st.column_config.NumberColumn(format='%.2f'),
        })
        update = st.form_submit_button('Calcola payoff', type='primary')
    if update:
        new = edited[COLS].copy()
        new['Del'] = new['Del'].fillna(False).astype(bool)
        st.session_state.legs = new
        st.rerun()
    if st.button('Elimina righe selezionate'):
        if not st.session_state.legs.Del.any():
            st.warning('Spunta Del su almeno una riga.')
        else:
            st.session_state.legs = st.session_state.legs[~st.session_state.legs.Del].assign(Del=False).reset_index(drop=True)
            st.rerun()
    if active.empty:
        st.warning('Inserisci almeno un’opzione valida.')
    else:
        greeks = active.apply(lambda r: pd.Series(values(r, start_date)), axis=1)[['Delta', 'Gamma', 'Vega', 'THETA']].sum()
        now, expiry = total(np.array([spot]), start_date)[0], total(np.array([spot]), analysis_date)[0]
        for col, label, value, fmt in zip(st.columns(6), ['Delta', 'Gamma', 'Vega', 'THETA', 'P&L AtNow', 'P&L analisi'], [greeks.Delta, greeks.Gamma, greeks.Vega, greeks.THETA, now, expiry], ['.3f', '.5f', '.3f', '.3f', '.2f', '.2f']):
            col.metric(label, format(value, ',' + fmt))
        x = np.linspace(pmin, pmax, 2000)
        y_start, y_analysis = total(x, start_date), total(x, analysis_date)
        fig = go.Figure()
        if show_analysis:
            fig.add_trace(go.Scatter(x=x, y=y_analysis, name='P/L data analisi', line={'width': 4, 'color': '#00a878'}))
        if show_start:
            fig.add_trace(go.Scatter(x=x, y=y_start, name='P/L data partenza', line={'dash': 'dash', 'color': '#3b82f6'}))
        fig.add_hline(y=0, line_color='gray')
        fig.add_vline(x=spot, line_dash='dash', line_color='#e69f00')
        fig.update_layout(title=f'{asset_class} — {selected}', hovermode='x unified', xaxis_title=f'Prezzo {ticker}', yaxis_title='P/L')
        st.plotly_chart(fig, use_container_width=True)
        a, b = st.columns(2)
        a.metric('PoP data analisi', f'{pop():.1f}%')
        b.metric('Break-even data analisi', ', '.join(map(str, break_evens(x, y_analysis))) or 'Nessuno')
with comparison_1:
    st.info('Scheda predisposta per il confronto con una seconda strategia.')
with comparison_2:
    st.info('Scheda predisposta per il confronto con una terza strategia.')

out = st.session_state.legs.drop(columns='Del').copy()
out.Scadenza = out.Scadenza.apply(lambda z: pd.to_datetime(z).date().isoformat() if pd.notna(z) else None)
save_data = {'opzioni': out.to_dict('records'), 'parametri': {'asset_class': asset_class, 'product': selected, 'spot': spot, 'atmiv': atmiv, 'start': start_date.isoformat(), 'analysis': analysis_date.isoformat(), 'rf': rate_pct, 'cash': cash, 'pmin': pmin, 'pmax': pmax, 'showa': show_analysis, 'shows': show_start}}
download_slot.download_button('Salva', json.dumps(save_data, ensure_ascii=False).encode(), 'strategia_opzioni.json', 'application/json')
