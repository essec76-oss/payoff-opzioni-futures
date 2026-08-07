# APPLICA QUESTE TRE SOSTITUZIONI AL FILE V15
# (Il file V15 completo resta invariato nel resto.)

# 1. Nel DEFAULT, aggiungi "Del":False dopo "Escludi":False in entrambe le righe:
# {"Escludi":False,"Del":False,"Acquisto/Vendita": ... }

# 2. Sostituisci COMPLETAMENTE la chiamata st.data_editor(...) con:
legs=st.data_editor(
    ed,
    num_rows="dynamic",
    use_container_width=True,
    key="editor",
    disabled=["DTE mancanti","Delta","Gamma","Vega (per 1%)","Theta (al giorno)"],
    column_config={
        "Escludi":st.column_config.CheckboxColumn("Escludi",default=False),
        "Del":st.column_config.CheckboxColumn("Del",default=False,help="Spunta e poi premi Elimina righe selezionate"),
        "Acquisto/Vendita":st.column_config.SelectboxColumn(options=["Acquisto","Vendita"],required=True),
        "Call/Put":st.column_config.SelectboxColumn(options=["Call","Put"],required=True),
        "Numero opzioni":st.column_config.NumberColumn(min_value=0.,step=1.),
        "Strike":st.column_config.NumberColumn(step=.25),
        "Vol opz (%)":st.column_config.NumberColumn(min_value=.01,step=.1),
        "Premio":st.column_config.NumberColumn(step=.0001,format="%.4f"),
        "Scadenza":st.column_config.DateColumn(format="DD/MM/YYYY"),
        "DTE mancanti":st.column_config.NumberColumn(format="%d"),
        "Delta":st.column_config.NumberColumn(format="%.2f"),
        "Gamma":st.column_config.NumberColumn(format="%.4f"),
        "Vega (per 1%)":st.column_config.NumberColumn(format="%.2f"),
        "Theta (al giorno)":st.column_config.NumberColumn(format="%.2f"),
    },
)
legs=legs.drop(columns=["DTE mancanti","Delta","Gamma","Vega (per 1%)","Theta (al giorno)"],errors="ignore")

# 3. Inserisci QUESTO BLOCCO subito dopo la riga precedente:
if "Del" not in legs.columns:
    legs["Del"] = False
if st.button("Elimina righe selezionate",type="primary"):
    da_mantenere=legs[~legs["Del"]].drop(columns=["Del"],errors="ignore").reset_index(drop=True)
    if len(da_mantenere)==len(legs):
        st.warning("Spunta Del su almeno una riga da eliminare.")
    else:
        st.session_state.legs_source=da_mantenere
        st.session_state.pop("editor",None)
        st.rerun()

# 4. Sostituisci la definizione req con questa:
req=["Escludi","Del","Acquisto/Vendita","Call/Put","Numero opzioni","Strike","Vol opz (%)","Premio","Scadenza"]

# 5. Subito dopo active=..., aggiungi:
active=active.drop(columns=["Del"],errors="ignore")

# 6. Prima di creare out=legs.copy() per il JSON, aggiungi:
legs=legs.drop(columns=["Del"],errors="ignore")
