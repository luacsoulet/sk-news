import streamlit as st
import feedparser
import urllib.parse
from datetime import datetime

# Configuration de la page
st.set_page_config(page_title="Google News Scraper", page_icon="📰", layout="wide")

# Style CSS pour les cartes cliquables
st.markdown("""
    <style>
    .article-card {
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e6e9ef;
        margin-bottom: 20px;
        transition: transform 0.2s;
        background-color: #ffffff;
        color: #1f1f1f;
    }
    .article-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-color: #ff4b4b;
    }
    .article-title {
        font-size: 1.2rem;
        font-weight: bold;
        color: #ff4b4b;
        text-decoration: none;
    }
    .article-date {
        font-size: 0.8rem;
        color: #666;
        margin-top: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📰 Google News Searcher")

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.header("Paramètres de recherche")
    subject = st.text_input("Sujet à rechercher", value="Swiss krono")
    
    col1, col2 = st.columns(2)
    with col1:
        date_min = st.date_input("Date début", value=None)
    with col2:
        date_max = st.date_input("Date fin", value=None)
    
    search_button = st.button("Lancer la recherche", type="primary")

# --- FONCTION DE RÉCUPÉRATION ---
def fetch_news(query, start_date, end_date):
    encoded_subject = urllib.parse.quote(query)
    
    # Construction de la requête avec filtres de date Google
    full_query = encoded_subject
    if start_date:
        full_query += f"+after:{start_date.strftime('%Y-%m-%d')}"
    if end_date:
        full_query += f"+before:{end_date.strftime('%Y-%m-%d')}"
    
    feed_url = f"https://news.google.com/rss/search?q={full_query}&hl=fr&gl=FR&ceid=FR:fr"
    
    feed = feedparser.parse(feed_url)
    return feed.entries

# --- AFFICHAGE DES RÉSULTATS ---
if search_button or subject:
    with st.spinner('Récupération et tri des articles...'):
        entries = fetch_news(subject, date_min, date_max)
        
        if not entries:
            st.warning("Aucun article trouvé pour cette recherche.")
        else:
            # --- LE TRI SE FAIT ICI ---
            # On trie par 'published_parsed' qui est un objet temporel comparable
            # reverse=True permet d'avoir le plus récent en haut
            entries_sorted = sorted(entries, key=lambda x: x.get('published_parsed'), reverse=True)
            
            st.subheader(f"Résultats pour : {subject} ({len(entries_sorted)} articles)")
            st.info("Triés du plus récent au plus ancien")
            
            for entry in entries_sorted:
                st.markdown(f"""
                    <a href="{entry.link}" target="_blank" style="text-decoration: none;">
                        <div class="article-card">
                            <div class="article-title">{entry.title}</div>
                            <div class="article-date">📅 {entry.published}</div>
                        </div>
                    </a>
                """, unsafe_allow_html=True)

# Bouton de sauvegarde JSON dans la barre latérale
if st.sidebar.button("Préparer le JSON"):
    entries = fetch_news(subject, date_min, date_max)
    # On trie aussi le JSON pour la cohérence
    entries_sorted = sorted(entries, key=lambda x: x.get('published_parsed'), reverse=True)
    
    import json
    data = [{"title": e.title, "link": e.link, "published": e.published} for e in entries_sorted]
    json_string = json.dumps(data, indent=2, ensure_ascii=False)
    
    st.sidebar.download_button(
        label="📥 Télécharger articles.json",
        file_name="articles.json",
        mime="application/json",
        data=json_string
    )