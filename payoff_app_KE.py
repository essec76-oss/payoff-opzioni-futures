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

INPUT_COLS = ['Escludi', 'Del', 'Buy/Sell', 'Call/Put', 'N° opz', 'Strike', 'Vol opz (%)', 'Premio', 'Scadenza']
EXP = date(2026, 11, 20)
DEFAULT = pd.DataFrame([
    [False, False, 'Sell', 'Put', 1, 600., 26.5, 3.9396, EXP],
    [False, False, 'Sell', 'Call', 1, 1200., 48.1, 2.6898, EXP],
], columns=INPUT_COLS)

st.session_state.setdefault('legs', DEFAULT.copy())
labels = (catalog.Ticker.astype(str) + ' - ' + catalog.Nome.astype(str)).tolist()
default_product = 'KE - Wheat Kansas' if 'KE - Wheat Kansas' in labels else labels[0]
for key, value in {
    'name': 'Strategia opzioni', 'product': default_product, 'spot': 721.75,
    'atmiv': 30., 'start': date(2026, 8, 7), 'analysis': EXP, 'rf': 0.,
    'comm': 0., 'pmin': 450., 'pmax': 1350., 'showa': True, 'shows': True,
}.items():
    st.session_state.setdefault(key, value)


def cdf(x):
    return .5 * (1 + np.vectorize(erf)(x / np.sqrt(2)))


def pdf(x):
    return np.exp(-x * x / 2) / np.sqrt(2 * pi)


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


def is_valid(r):
    try:
        return (pd.notna(r.Scadenza) and float(r.Strike) > 0 and
                float(r['Vol opz (%)']) > 0 and float(r['N° opz']) > 0)
    except (TypeError, ValueError):
        return False


def position_values(r, valuation_date):
    empty = {'DTE': np.nan, 'xTM': '', 'Delta': np.nan, 'Gamma': np.nan, 'Vega': np.nan,
             'THETA': np.nan, 'Pr. opz.': np.nan, 'V. Temp.': np.nan, 'V. Intr.': np.nan}
    if not is_valid(r):
        return empty
    dte = max((pd.to_datetime(r.Scadenza).date() - valuation_date).days, 0)
    t = dte / 365
    strike = float(r.Strike)
    sigma = float(r['Vol opz (%)']) / 100
    typ = r['Call/Put']
    sign = 1 if r['Buy/Sell'] == 'Buy' else -1
    qty_mult = sign * float(r['N° opz']) * multiplier
    intrinsic = max(spot - strike, 0) if typ == 'Call' else max(strike - spot, 0)
    if abs(spot - strike) / spot <= .005:
        moneyness = 'ATM'
    elif (typ == 'Call' and spot > strike) or (typ == 'Put' and spot < strike):
        moneyness = 'ITM'
    else:
        moneyness = 'OTM'
    theoretical = float(b76(spot, strike, t, sigma, rate, typ))
    if t <= 0:
        return {'DTE': dte, 'xTM': moneyness, 'Delta': 0., 'Gamma': 0., 'Vega': 0., 'THETA': 0.,
                'Pr. opz.': theoretical, 'V. Temp.': 0., 'V. Intr.': intrinsic}
    root_t = np.sqrt(t)
    d1 = (np.log(spot / strike) + .5 * sigma * sigma * t) / (sigma * root_t)
    discount = np.exp(-rate * t)
    delta = discount * (cdf(d1) if typ == 'Call' else -cdf(-d1))
    gamma = discount * pdf(d1) / (spot * sigma * root_t)
    vega = discount * spot * pdf(d1) * root_t * .01
    tomorrow = float(b76(spot, strike, max(t - 1 / 365, 0), sigma, rate, typ))
    return {
        'DTE': dte, 'xTM': moneyness, 'Delta': qty_mult * float(delta),
        'Gamma': qty_mult * float(gamma), 'Vega': qty_mult * float(vega),
        'THETA': qty_mult * (tomorrow - theoretical), 'Pr. opz.': theoretical,
        'V. Temp.': max(theoretical - intrinsic, 0), 'V. Intr.': intrinsic,
    }


def pnl(x, r, valuation_date):
    t = max((pd.to_datetime(r.Scadenza).date() - valuation_date).days, 0) / 365
    sign = 1 if r['Buy/Sell'] == 'Buy' else -1
    theoretical = b76(x, float(r.Strike), t, float(r['Vol opz (%)']) / 100, rate, r['Call/Put'])
    return sign * float(r['N° opz']) * (theoretical - float(r.Premio)) * multiplier


def total_pnl(x, valuation_date):
    return sum((pnl(x, r, valuation_date) for _, r in active.iterrows()), np.zeros_like(x, dtype=float)) - commission


def break_evens(x, y):
    return [round(x[i] + (x[i + 1] - x[i]) * (-y[i]) / (y[i + 1] - y[i]), 2)
            for i in range(len(x) - 1) if y[i] * y[i + 1] < 0]


def probability_of_profit():
    t = (analysis_date - start_date).days / 365
    if t <= 0:
        return 100. if total_pnl(np.array([spot]), analysis_date)[0] > 0 else 0.
    sigma = atmiv / 100
    z = max(12 * sigma * np.sqrt(t), .25)
    edges = np.concatenate(([0], np.geomspace(max(spot * np.exp(-z), 1e-8), spot * np.exp(z), 10000), [np.inf]))
    q = (np.log(edges[1:-1] / spot) + .5 * sigma * sigma * t) / (sigma * np.sqrt(t))
    masses = np.diff(np.r_[0, cdf(q), 1])
    midpoints = np.r_[edges[1] / 2, np.sqrt(edges[1:-2] * edges[2:-1]), edges[-2] * 2]
    return float(masses[total_pnl(midpoints, analysis_date) > 0].sum() * 100)


with st.sidebar:
    st.header('Salva / Carica')
    upload = st.file_uploader('File strategia (.json)', type='json')
    load_col, save_col = st.columns(2)
    load = load_col.button('Carica', use_container_width=True)
    download_slot = save_col.empty()
    if load and upload:
        saved = json.load(upload)
        loaded = pd.DataFrame(saved['opzioni']).rename(columns={
            'Acquisto/Vendita': 'Buy/Sell', 'Numero opzioni': 'N° opz'
        })
        if 'Buy/Sell' in loaded:
            loaded['Buy/Sell'] = loaded['Buy/Sell'].replace({'Acquisto': 'Buy', 'Vendita': 'Sell'})
        loaded['Scadenza'] = pd.to_datetime(loaded['Scadenza']).dt.date
        for col in INPUT_COLS:
            if col not in loaded:
                loaded[col] = False if col in ['Escludi', 'Del'] else None
        st.session_state.legs = loaded[INPUT_COLS]
        for key, value in saved['parametri'].items():
            st.session_state[key] = pd.to_datetime(value).date() if key in ['start', 'analysis'] else value
        st.rerun()

    st.header('Parametri strategia')
    strategy_name = st.text_input('Nome strategia', key='name')
    selected = st.selectbox('Sottostante', labels, key='product')
    product = catalog.iloc[labels.index(selected)]
    ticker, multiplier = product.Ticker, float(product.PL_Multiplier)
    spot = st.number_input('Prezzo sottostante', min_value=.0001, step=.25, key='spot')
    atmiv = st.number_input('ATM IV globale (%)', min_value=.01, step=.1, key='atmiv')
    start_date = st.date_input('Data di partenza', key='start')
    analysis_date = st.date_input('Data analisi', key='analysis')
    rate_pct = st.number_input('Tasso risk-free (%)', min_value=0., step=.1, key='rf')
    commission = st.number_input('Commissioni totali', step=.01, key='comm')
    pmin = st.number_input('Range minimo', step=1., key='pmin')
    pmax = st.number_input('Range massimo', step=1., key='pmax')
    show_analysis = st.checkbox('Mostra P/L alla data di analisi', key='showa')
    show_start = st.checkbox('Mostra P/L alla data di partenza', key='shows')

rate = rate_pct / 100
base = st.session_state.legs.copy().rename(columns={'Acquisto/Vendita': 'Buy/Sell', 'Numero opzioni': 'N° opz'})
if 'Buy/Sell' in base:
    base['Buy/Sell'] = base['Buy/Sell'].replace({'Acquisto': 'Buy', 'Vendita': 'Sell'})
for col in ['Escludi', 'Del']:
    if col not in base:
        base[col] = False
    base[col] = base[col].fillna(False).astype(bool)
st.session_state.legs = base[INPUT_COLS]
active = base[(~base.Escludi) & base.apply(is_valid, axis=1)].drop(columns='Del')

strategy_tab, comparison_1, comparison_2 = st.tabs(['Strategia', 'Comparazione 1', 'Comparazione 2'])
with strategy_tab:
    top = st.columns([1.2, 1.2, 1, 1, 1])
    top[0].metric('Ticker', ticker)
    top[1].metric('Moltiplicatore', f'x{multiplier:g}')
    top[2].metric('Prezzo', f'{spot:,.2f}')
    top[3].metric('Risk-free', f'{rate_pct:.2f}%')
    top[4].metric('P/L cash', f'{commission:,.2f}')

    display = base.copy()
    calculated = display.apply(lambda r: pd.Series(position_values(r, start_date)), axis=1)
    display = pd.concat([display, calculated], axis=1)
    if not active.empty:
        display['P&L AtNow'] = display.apply(lambda r: pnl(np.array([spot]), r, start_date)[0] if is_valid(r) else np.nan, axis=1)
        display['P&L scad.'] = display.apply(lambda r: pnl(np.array([spot]), r, analysis_date)[0] if is_valid(r) else np.nan, axis=1)
    else:
        display['P&L AtNow'] = np.nan
        display['P&L scad.'] = np.nan

    st.subheader('Option Trades')
    with st.form('editor'):
        edited = st.data_editor(
            display, num_rows='dynamic', use_container_width=True,
            disabled=['DTE', 'xTM', 'Delta', 'Gamma', 'Vega', 'THETA', 'Pr. opz.', 'V. Temp.', 'V. Intr.', 'P&L AtNow', 'P&L scad.'],
            column_config={
                'Escludi': st.column_config.CheckboxColumn('Escludi', default=False),
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
            }
        )
        update = st.form_submit_button('Calcola payoff', type='primary')
    if update:
        new = edited[INPUT_COLS].copy()
        new['Escludi'] = new['Escludi'].fillna(False).astype(bool)
        new['Del'] = new['Del'].fillna(False).astype(bool)
        st.session_state.legs = new
        st.rerun()
    if st.button('Elimina righe selezionate'):
        if not st.session_state.legs.Del.any():
            st.warning('Spunta Del su almeno una riga.')
        else:
            st.session_state.legs = st.session_state.legs[~st.session_state.legs.Del].drop(columns='Del').assign(Del=False).reset_index(drop=True)
            st.rerun()

    if active.empty:
        st.warning('Inserisci almeno un’opzione valida.')
    else:
        totals = active.apply(lambda r: pd.Series(position_values(r, start_date)), axis=1)[['Delta', 'Gamma', 'Vega', 'THETA']].sum()
        total_now = total_pnl(np.array([spot]), start_date)[0]
        total_analysis = total_pnl(np.array([spot]), analysis_date)[0]
        st.subheader('Totali strategia')
        t1, t2, t3, t4, t5, t6 = st.columns(6)
        t1.metric('Delta', f"{totals['Delta']:,.3f}")
        t2.metric('Gamma', f"{totals['Gamma']:,.5f}")
        t3.metric('Vega', f"{totals['Vega']:,.3f}")
        t4.metric('THETA', f"{totals['THETA']:,.3f}")
        t5.metric('P&L AtNow', f'{total_now:,.2f}')
        t6.metric('P&L analisi', f'{total_analysis:,.2f}')

        x = np.linspace(pmin, pmax, 2000)
        pnl_start, pnl_analysis = total_pnl(x, start_date), total_pnl(x, analysis_date)
        figure = go.Figure()
        if show_analysis:
            figure.add_trace(go.Scatter(x=x, y=pnl_analysis, name='P/L data analisi', line={'width': 4, 'color': '#00a878'}))
        if show_start:
            figure.add_trace(go.Scatter(x=x, y=pnl_start, name='P/L data partenza', line={'dash': 'dash', 'color': '#3b82f6'}))
        figure.add_hline(y=0, line_color='gray')
        figure.add_vline(x=spot, line_dash='dash', line_color='#e69f00')
        figure.update_layout(title=f'{strategy_name} — {selected}', hovermode='x unified', xaxis_title=f'Prezzo {ticker}', yaxis_title='P/L')
        st.plotly_chart(figure, use_container_width=True)
        m1, m2 = st.columns(2)
        m1.metric('PoP data analisi', f'{probability_of_profit():.1f}%')
        m2.metric('Break-even data analisi', ', '.join(map(str, break_evens(x, pnl_analysis))) or 'Nessuno')

with comparison_1:
    st.info('Scheda pronta per una futura seconda strategia e il confronto del payoff.')
with comparison_2:
    st.info('Scheda pronta per una futura terza strategia e il confronto del payoff.')

out = st.session_state.legs.drop(columns='Del').copy()
out.Scadenza = out.Scadenza.apply(lambda value: pd.to_datetime(value).date().isoformat() if pd.notna(value) else None)
save_data = {'opzioni': out.to_dict('records'), 'parametri': {
    'name': strategy_name, 'product': selected, 'spot': spot, 'atmiv': atmiv,
    'start': start_date.isoformat(), 'analysis': analysis_date.isoformat(), 'rf': rate_pct,
    'comm': commission, 'pmin': pmin, 'pmax': pmax, 'showa': show_analysis, 'shows': show_start,
}}
download_slot.download_button('Salva', json.dumps(save_data, ensure_ascii=False).encode(), 'strategia_opzioni.json', 'application/json', use_container_width=True)
