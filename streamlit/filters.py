import streamlit as st
from datetime import datetime, timedelta

def render_sidebar_filters(sources):
    st.sidebar.markdown("<h2 style='color:white;'>🔍 FILTRES</h2>", unsafe_allow_html=True)
    
    # Filtre Journaux
    source_map = {s['name']: s['id'] for s in sources}
    source_names = sorted(list(source_map.keys()))
    selected_names = st.sidebar.multiselect("Journaux :", options=source_names, default=source_names)
    selected_ids = [source_map[name] for name in selected_names]

    st.sidebar.write("---")
    
    # Filtre Dates
    st.sidebar.markdown("<b style='color:white;'>Période :</b>", unsafe_allow_html=True)
    now = datetime.now().date()
    
    preset = st.sidebar.selectbox(
        "Préréglages :",
        ["Depuis toujours", "Depuis 2 ans", "Depuis 1 an", "Depuis 1 mois", "Personnalisé"]
    )

    if preset == "Depuis toujours":
        start_default = datetime(2000, 1, 1).date()
    elif preset == "Depuis 2 ans":
        start_default = now - timedelta(days=730)
    elif preset == "Depuis 1 an":
        start_default = now - timedelta(days=365)
    elif preset == "Depuis 1 mois":
        start_default = now - timedelta(days=30)
    else:
        start_default = now - timedelta(days=365)

    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Début", value=start_default)
    with col2:
        end_date = st.date_input("Fin", value=now)

    return selected_ids, start_date, end_date