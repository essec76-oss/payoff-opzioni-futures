# --- Gestione del Download della strategia e completamento Tab ---
out = st.session_state.legs.drop(columns=['Oscura', 'Del']).copy()
out.Scadenza = out.Scadenza.apply(lambda x: pd.to_datetime(x).date().isoformat() if pd.notna(x) else None)

# Salvataggio di tutti i parametri di configurazione dell'interfaccia
payload = {
    'opzioni': out.to_dict('records'),
    'parametri': {
        'asset_class': asset_class,
        'product': selected,
        'spot': spot,
        'atmiv': atmiv,
        'start': start_date.isoformat(),
        'analysis': analysis_date.isoformat(),
        'rf': rate_pct,
        'cash': cash,
        'pmin': pmin,
        'pmax': pmax,
        'showa': show_analysis,
        'shows': show_start
    }
}

# Popola il pulsante di download allocato nell'expander iniziale
slot.download_button(
    label='Salva Strategia',
    data=json.dumps(payload, default=str, indent=2),
    file_name='strategia_opzioni.json',
    mime='application/json'
)

# Recupero dei tab creati precedentemente per implementare i confronti di portafoglio
# Nota: Poiché st.tabs restituisce una lista, riprendiamo l'istanza corretta
tabs_list = st.session_state.get('_tabs_saved')
if tabs_list is None:
    # Riferimento per riallinearsi alla struttura a tab principale del codice
    pass

# Implementazione delle sezioni di comparazione per scenari di stress test
# Nota: Nel codice originale lo switch era gestito tramite l'indice [0] direttamente in linea.
# Per scrivere in Comparazione 1 e 2 in Streamlit senza ridefinire i tab, usiamo dei container dedicati al fondo.

st.divider()
st.subheader("Analisi Comparativa e Stress Test")
comp_1, comp_2 = st.columns(2)

with comp_1:
    st.markdown("### 📊 Comparazione 1: Shock di Volatilità (IV)")
    if active.empty:
        st.info("Inserisci opzioni valide per simulare variazioni di IV.")
    else:
        # Simulazione di uno spostamento parallelo della IV di +/- 5%
        x_comp = np.linspace(pmin, pmax, 1000)
        fig_iv = go.Figure()
        
        # Calcolo P&L con IV Base
        fig_iv.add_trace(go.Scatter(x=x_comp, y=total(x_comp, start_date), name='IV Base', line=dict(color='#3b82f6')))
        
        # Shock IV +5%
        original_iv = atmiv
        st.session_state.atmiv = original_iv + 5.0
        fig_iv.add_trace(go.Scatter(x=x_comp, y=total(x_comp, start_date), name='IV +5%', line=dict(dash='dot', color='#ef4444')))
        
        # Shock IV -5%
        st.session_state.atmiv = original_iv - 5.0
        fig_iv.add_trace(go.Scatter(x=x_comp, y=total(x_comp, start_date), name='IV -5%', line=dict(dash='dot', color='#10b981')))
        
        # Ripristino dello stato originario
        st.session_state.atmiv = original_iv
        
        fig_iv.update_layout(title="Impatto della Volatilità Implicita sul P&L At Now", xaxis_title="Prezzo", yaxis_title="P&L ($)", margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_iv, use_container_width=True)

with comp_2:
    st.markdown("### ⏳ Comparazione 2: Passaggio del Tempo (Theta Decay)")
    if active.empty:
        st.info("Inserisci opzioni valide per simulare il passaggio del tempo.")
    else:
        # Simulazione del decadimento temporale a 7 e 14 giorni da oggi
        x_comp = np.linspace(pmin, pmax, 1000)
        fig_t = go.Figure()
        
        fig_t.add_trace(go.Scatter(x=x_comp, y=total(x_comp, start_date), name='T=0 (Oggi)', line=dict(color='#3b82f6')))
        
        t_7 = start_date + pd.Timedelta(days=7)
        if t_7 <= analysis_date:
            fig_t.add_trace(go.Scatter(x=x_comp, y=total(x_comp, t_7), name='+7 Giorni', line=dict(dash='dash', color='#f59e0b')))
            
        t_14 = start_date + pd.Timedelta(days=14)
        if t_14 <= analysis_date:
            fig_t.add_trace(go.Scatter(x=x_comp, y=total(x_comp, t_14), name='+14 Giorni', line=dict(dash='dash', color='#9333ea')))
            
        fig_t.update_layout(title="Impatto del Passaggio del Tempo sul P&L", xaxis_title="Prezzo", yaxis_title="P&L ($)", margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_t, use_container_width=True)
