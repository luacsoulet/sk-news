import streamlit as st
import feedparser
import urllib.parse
from datetime import datetime

# Configuration de la page
st.set_page_config(page_title="Veille Média Pro", page_icon="📊", layout="wide")

# --- DESIGN & CSS AMÉLIORÉ ---
st.markdown("""
    <style>
    /* Fond de l'application */
    .main {
        background-color: #f8f9fa;
    }
    /* Style des cartes */
    .article-card {
        padding: 24px;
        border-radius: 15px;
        background-color: white;
        border: 1px solid #e0e0e0;
        margin-bottom: 18px;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .article-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.08);
        border-color: #007bff;
    }
    /* Badge du journal */
    .source-badge {
        background-color: #e7f1ff;
        color: #007bff;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        display: inline-block;
        margin-bottom: 10px;
    }
    .article-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #1a1a1a;
        margin-bottom: 8px;
        line-height: 1.4;
    }
    .article-date {
        font-size: 0.85rem;
        color: #6c757d;
        display: flex;
        align-items: center;
        gap: 5px;
    }
    a {
        text-decoration: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FONCTIONS LOGIQUES ---

def clean_and_parse_entries(entries):
    """Extrait le journal du titre et nettoie la donnée."""
    parsed_data = []
    for entry in entries:
        title = entry.title
        # Google News met souvent "Titre - Journal"
        parts = title.rsplit(' - ', 1)
        
        clean_title = parts[0]
        source = parts[1] if len(parts) > 1 else "Source inconnue"
        
        parsed_data.append({
            "title": clean_title,
            "source": source,
            "link": entry.link,
            "published": entry.published,
            "timestamp": entry.get('published_parsed')
        })
    return parsed_data

def fetch_news(query, start_date, end_date):
    encoded_subject = urllib.parse.quote(query)
    full_query = encoded_subject
    if start_date:
        full_query += f"+after:{start_date.strftime('%Y-%m-%d')}"
    if end_date:
        full_query += f"+before:{end_date.strftime('%Y-%m-%d')}"
    
    feed_url = f"https://news.google.com/rss/search?q={full_query}&hl=fr&gl=FR&ceid=FR:fr"
    feed = feedparser.parse(feed_url)
    return clean_and_parse_entries(feed.entries)

# --- INTERFACE UTILISATEUR ---

st.title("📊 Veille Stratégique")

with st.sidebar:
    st.header("🔍 Recherche")
    subject = st.text_input("Sujet", value="Swiss krono")
    
    col1, col2 = st.columns(2)
    with col1:
        date_min = st.date_input("Début", value=None)
    with col2:
        date_max = st.date_input("Fin", value=None)
    
    st.divider()
    st.header("⚙️ Filtres & Tri")
    
    # On récupère les données pour remplir les filtres
    all_articles = fetch_news(subject, date_min, date_max)
    
    # Liste unique des journaux pour le filtre
    sources_disponibles = sorted(list(set(a['source'] for a in all_articles)))
    selected_sources = st.multiselect("Filtrer par journaux", sources_disponibles, default=sources_disponibles)
    
    sort_option = st.selectbox("Trier par", ["Plus récent", "Plus ancien", "Journal (A-Z)"])

# --- TRAITEMENT DES DONNÉES ---

# 1. Filtrage par journal
filtered_articles = [a for a in all_articles if a['source'] in selected_sources]

# 2. Logique de Tri
if sort_option == "Plus récent":
    filtered_articles.sort(key=lambda x: x['timestamp'], reverse=True)
elif sort_option == "Plus ancien":
    filtered_articles.sort(key=lambda x: x['timestamp'], reverse=False)
else:
    filtered_articles.sort(key=lambda x: x['source'])

# --- AFFICHAGE ---

st.subheader(f"📈 {len(filtered_articles)} Articles trouvés")

if not filtered_articles:
    st.info("Aucun article ne correspond à vos filtres.")
else:
    for art in filtered_articles:
        st.markdown(f"""
            <a href="{art['link']}" target="_blank">
                <div class="article-card">
                    <span class="source-badge">{art['source']}</span>
                    <div class="article-title">{art['title']}</div>
                    <div class="article-date">
                        <span>📅</span> {art['published']}
                    </div>
                </div>
            </a>
        """, unsafe_allow_html=True)