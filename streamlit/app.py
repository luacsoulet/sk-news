import streamlit as st
import db
import filters
import ui_components as ui
from datetime import datetime

# --- LIGNE CRUCIALE POUR LA PLEINE LARGEUR ---
st.set_page_config(page_title="News SK", page_icon="🔻", layout="wide")

# Setup
ui.inject_custom_css()

# 2. Chargement des données (Avant génération)
sources = db.get_news_sources()
articles = db.get_articles()
source_map = {s['id']: s['name'] for s in sources}

# 3. Sidebar
selected_ids, d_start, d_end = filters.render_sidebar_filters(sources)

# 4. En-tête
st.markdown("<h1 style='color:white; font-size:3rem; font-weight:900; margin-bottom:30px;'>News <span style='color:#dc2626;'>SK</span></h1>", unsafe_allow_html=True)

# 5. Filtrage des données
filtered = []
for a in articles:
    try:
        a_date = datetime.fromisoformat(a['created_at'].replace('Z', '+00:00')).date()
        if a['news_source_id'] in selected_ids and d_start <= a_date <= d_end:
            filtered.append(a)
    except:
        continue

# 6. Rendu de la galerie
if not filtered:
    st.info("Aucun article ne correspond à vos filtres.")
else:
    cols = st.columns(3)
    for idx, article in enumerate(filtered):
        s_name = source_map.get(article['news_source_id'], "Source")
        with cols[idx % 3]:
            ui.render_article_card(article, s_name)

st.sidebar.write("---")
st.sidebar.caption(f"Synchronisation OK : {len(filtered)} articles")