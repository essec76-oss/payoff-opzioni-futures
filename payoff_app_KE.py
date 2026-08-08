from pathlib import Path
import re

source = Path('payoff_opzioni_v24_2_completo.py')
target = Path('payoff_opzioni_v24_3.py')
text = source.read_text(encoding='utf-8')

text = text.replace("COLS = ['Del', 'Buy/Sell', 'Call/Put', 'N° opz', 'Strike', 'Vol opz (%)', 'Premio', 'Scadenza']", "COLS = ['Oscura', 'Del', 'Buy/Sell', 'Call/Put', 'N° opz', 'Strike', 'Vol opz (%)', 'Premio', 'Scadenza']")
text = text.replace("    [False, 'Sell', 'Put', 1, 600., 26.5, 3.9396, EXP],\n    [False, 'Sell', 'Call', 1, 1200., 48.1, 2.6898, EXP],", "    [False, False, 'Sell', 'Put', 1, 600., 26.5, 3.9396, EXP],\n    [False, False, 'Sell', 'Call', 1, 1200., 48.1, 2.6898, EXP],")
text = text.replace("df[col] = False if col == 'Del' else None", "df[col] = False if col in ['Oscura', 'Del'] else None")

old_base = """if 'Del' not in base:
    base['Del'] = False
base['Del'] = base['Del'].fillna(False).astype(bool)
base = base[COLS].copy()
st.session_state.legs = base
active = base[base.apply(valid, axis=1)].drop(columns='Del')"""
new_base = """if 'Oscura' not in base:
    base['Oscura'] = False
base['Oscura'] = base['Oscura'].fillna(False).astype(bool)
if 'Del' not in base:
    base['Del'] = False
base['Del'] = base['Del'].fillna(False).astype(bool)
base = base[COLS].copy()
st.session_state.legs = base
active = base[(~base['Oscura']) & base.apply(valid, axis=1)].drop(columns=['Oscura', 'Del'])"""
if old_base not in text:
    raise RuntimeError('Blocco base non trovato: usa esattamente payoff_opzioni_v24_2_completo.py.')
text = text.replace(old_base, new_base)

text = text.replace("'Del': st.column_config.CheckboxColumn('Del', default=False),", "'Oscura': st.column_config.CheckboxColumn('Oscura', default=False),\n            'Del': st.column_config.CheckboxColumn('Del', default=False),")
text = text.replace("new['Del'] = new['Del'].fillna(False).astype(bool)", "new['Oscura'] = new['Oscura'].fillna(False).astype(bool)\n        new['Del'] = new['Del'].fillna(False).astype(bool)")
text = text.replace("display['P&L scad.'] = display.apply(lambda r: pnl(np.array([spot]), r, analysis_date)[0] if valid(r) else np.nan, axis=1)", "display['P&L scad.'] = display.apply(lambda r: pnl(np.array([spot]), r, pd.to_datetime(r.Scadenza).date())[0] if valid(r) else np.nan, axis=1)")
text = text.replace("now, expiry = total(np.array([spot]), start_date)[0], total(np.array([spot]), analysis_date)[0]", "now = total(np.array([spot]), start_date)[0]\n        expiry = sum((pnl(np.array([spot]), r, pd.to_datetime(r.Scadenza).date())[0] for _, r in active.iterrows()), 0.) + cash")
text = text.replace("['Delta', 'Gamma', 'Vega', 'THETA', 'P&L AtNow', 'P&L analisi']", "['Delta', 'Gamma', 'Vega', 'THETA', 'P&L AtNow', 'P&L scadenza']")
text = text.replace("y_start, y_analysis = total(x, start_date), total(x, analysis_date)", "y_start = total(x, start_date)\n        y_expiry = sum((pnl(x, r, pd.to_datetime(r.Scadenza).date()) for _, r in active.iterrows()), np.zeros_like(x, dtype=float)) + cash")
text = text.replace("if show_analysis:\n            fig.add_trace(go.Scatter(x=x, y=y_analysis, name='P/L data analisi', line={'width': 4, 'color': '#00a878'}))", "if show_analysis:\n            fig.add_trace(go.Scatter(x=x, y=y_expiry, name='P/L a scadenza', line={'width': 4, 'color': '#00a878'}))")
text = text.replace("if show_start:\n            fig.add_trace(go.Scatter(x=x, y=y_start, name='P/L data partenza', line={'dash': 'dash', 'color': '#3b82f6'}))", "if show_start:\n            fig.add_trace(go.Scatter(x=x, y=y_start, name='P/L at now', line={'dash': 'dash', 'color': '#3b82f6'}))")
text = text.replace("a.metric('PoP data analisi', f'{pop():.1f}%')\n        b.metric('Break-even data analisi', ', '.join(map(str, break_evens(x, y_analysis))) or 'Nessuno')", "a.metric('PoP data analisi', f'{pop():.1f}%')\n        b.metric('Break-even a scadenza', ', '.join(map(str, break_evens(x, y_expiry))) or 'Nessuno')")
text = text.replace("out = st.session_state.legs.drop(columns='Del').copy()", "out = st.session_state.legs.drop(columns=['Oscura', 'Del']).copy()")

if "'Oscura': st.column_config.CheckboxColumn('Oscura'" not in text or "y_expiry" not in text:
    raise RuntimeError('Una o più modifiche non sono state applicate.')
target.write_text(text, encoding='utf-8')
print(f'Creato: {target.name}')
