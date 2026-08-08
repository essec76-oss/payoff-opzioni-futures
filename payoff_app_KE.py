from pathlib import Path

source = Path('payoff_opzioni_v24_2_completo.py')
target = Path('payoff_opzioni_v24_3.py')
text = source.read_text(encoding='utf-8')

text = text.replace('import json\n', 'import json\nimport re\n')
text = text.replace("'asset_class': 'Futures Commodity', 'product': default_product, 'spot': 721.75,", "'project_name': 'Strategia_opzioni', 'asset_class': 'Futures Commodity', 'product': default_product, 'spot': 721.75,")
old_params = """r1 = st.columns([1.25, 1.6, 1, 1, 1])
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
st.divider()"""
new_params = """r1 = st.columns([1.25, 1.25, 1.6, 1, 1, 1])
project_name = r1[0].text_input('Nome progetto', key='project_name')
asset_class = r1[1].selectbox('Tipo sottostante', ['Futures Commodity', 'Azioni', 'Futures Indici'], key='asset_class')
selected = r1[2].selectbox('Sottostante', labels, key='product')
product = catalog.iloc[labels.index(selected)]
ticker, multiplier = product.Ticker, float(product.PL_Multiplier)
spot = r1[3].number_input('Prezzo sottostante', min_value=.0001, step=.25, key='spot')
cash = r1[4].number_input('Cash ($)', step=.01, key='cash')
r1[5].metric('Ticker / Mult.', f'{ticker} ×{multiplier:g}')

r2 = st.columns(6)
start_date = r2[0].date_input('Data partenza', key='start')
analysis_date = r2[1].date_input('Data analisi', key='analysis')
atmiv = r2[2].number_input('ATM IV (%)', min_value=.01, step=.1, key='atmiv')
rate_pct = r2[3].number_input('Tasso risk-free (%)', min_value=0., step=.1, key='rf')
pmin = r2[4].number_input('Range minimo', step=1., key='pmin')
pmax = r2[5].number_input('Range massimo', step=1., key='pmax')
st.divider()"""
text = text.replace(old_params, new_params)
text = text.replace("if show_analysis:\n            fig.add_trace", "if st.session_state.showa:\n            fig.add_trace")
text = text.replace("if show_start:\n            fig.add_trace", "if st.session_state.shows:\n            fig.add_trace")
text = text.replace("st.plotly_chart(fig, use_container_width=True)\n        a, b = st.columns(2)", """st.plotly_chart(fig, use_container_width=True)
        chart_controls = st.columns([1.3, 1.3, 5])
        chart_controls[0].checkbox('P/L data analisi', key='showa')
        chart_controls[1].checkbox('P/L data partenza', key='shows')
        a, b = st.columns(2)""")
text = text.replace("'asset_class': asset_class, 'product': selected,", "'project_name': project_name, 'asset_class': asset_class, 'product': selected,")
text = text.replace("download_slot.download_button('Salva', json.dumps(save_data, ensure_ascii=False).encode(), 'strategia_opzioni.json', 'application/json')", """safe_name = re.sub(r'[^A-Za-z0-9_-]+', '_', project_name.strip()).strip('_') or 'strategia_opzioni'
filename = f'{safe_name}_{date.today().isoformat()}.json'
download_slot.download_button('Salva progetto', json.dumps(save_data, ensure_ascii=False, indent=2).encode(), filename, 'application/json')""")
text = text.replace("st.session_state.setdefault('asset_class', 'Futures Commodity')", "st.session_state.setdefault('asset_class', 'Futures Commodity')\n        st.session_state.setdefault('project_name', saved['parametri'].get('project_name', 'Strategia_opzioni'))")

if old_params not in Path('payoff_opzioni_v24_2_completo.py').read_text(encoding='utf-8'):
    raise RuntimeError('La versione di partenza non corrisponde al file V24.2 completo.')
target.write_text(text, encoding='utf-8')
print(f'Creato: {target.name}')
