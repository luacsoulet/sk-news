import streamlit as st
import feedparser
import urllib.parse
from datetime import datetime
from collections import Counter

# --- CONFIGURATION ---
st.set_page_config(page_title="Veille Média - Intelligence", page_icon="🔻", layout="wide")

# --- CSS "ULTRA GLASSMORPHISM RED - CLEAN & TAGS" ---
st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #000000, #150505, #350a0a);
        background-attachment: fixed;
    }
    [data-testid="stHeader"] { background: transparent; }

    /* SIDEBAR */
    [data-testid="stSidebar"] {
        background-color: #050505 !important; 
        border-right: 3px solid #dc2626 !important; 
    }

    /* Badges */
    .badges-container { 
        display: flex; 
        gap: 6px; 
        margin-bottom: 12px; 
        flex-wrap: wrap;
        align-items: center;
    }
    
    .source-badge {
        background: rgba(220, 38, 38, 0.8);
        border: 1px solid #dc2626;
        color: #ffffff;
        padding: 2px 10px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 800;
        text-transform: uppercase;
    }
    
    .country-tag {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.4);
        color: #ffffff;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.65rem;
        font-weight: 700;
    }

    /* Dashboard Metrics */
    .stat-card-fixed {
        background: rgba(30, 30, 30, 0.6);
        backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 20px;
        height: 130px; 
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    /* Grille Articles - Correction bug d'affichage */
    .article-card {
        background: rgba(20, 20, 20, 0.7);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 24px;
        height: 340px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        margin-bottom: 20px;
        overflow: hidden;
    }
    
    .article-title {
        font-size: 1.1rem; 
        font-weight: 600; 
        color: white; 
        line-height: 1.4; 
        margin-top: 5px;
        display: -webkit-box;
        -webkit-line-clamp: 4;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }

    .btn-glass-red {
        display: block; 
        width: 100%; 
        background: linear-gradient(90deg, #991b1b, #dc2626);
        color: white !important; 
        text-align: center; 
        padding: 10px 0;
        border-radius: 12px; 
        text-decoration: none !important; 
        font-weight: 700;
        transition: 0.3s ease;
    }
    .btn-glass-red:hover {
        filter: brightness(1.2);
        box-shadow: 0 4px 15px rgba(220, 38, 38, 0.4);
    }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIQUE RÉCUPÉRATION ---

EDITIONS = {
    "🌐 Global": {"hl": "fr", "gl": "FR", "ceid": "FR:fr", "tag": "ALL"},
    "🇫🇷 France": {"hl": "fr", "gl": "FR", "ceid": "FR:fr", "tag": "FR"},
    "🇨🇭 Suisse": {"hl": "fr", "gl": "CH", "ceid": "CH:fr", "tag": "CH"},
    "🇺🇸 USA": {"hl": "en", "gl": "US", "ceid": "US:en", "tag": "US"},
}

def fetch_data(query, start_date, end_date, country_label):
    countries_to_fetch = ["🇫🇷 France", "🇨🇭 Suisse", "🇺🇸 USA"] if country_label == "🌐 Global" else [country_label]
    titles_tracker = {}

    for country in countries_to_fetch:
        ed = EDITIONS[country]
        encoded_query = urllib.parse.quote(query)
        date_filter = ""
        if start_date: date_filter += f"+after:{start_date.strftime('%Y-%m-%d')}"
        if end_date: date_filter += f"+before:{end_date.strftime('%Y-%m-%d')}"
        
        url = f"https://news.google.com/rss/search?q={encoded_query}{date_filter}&hl={ed['hl']}&gl={ed['gl']}&ceid={ed['ceid']}"
        feed = feedparser.parse(url)
        
        for entry in feed.entries:
            clean_title = entry.title.rsplit(' - ', 1)[0]
            # Protection contre les titres vides ou mal formés
            if not clean_title: continue
            
            source = entry.title.rsplit(' - ', 1)[1] if ' - ' in entry.title else "Source"
            
            if clean_title not in titles_tracker:
                titles_tracker[clean_title] = {
                    "title": clean_title,
                    "source": source,
                    "link": entry.link,
                    "published": entry.published,
                    "timestamp": entry.get('published_parsed'),
                    "countries": {ed['tag']}
                }
            else:
                titles_tracker[clean_title]["countries"].add(ed['tag'])
    
    return list(titles_tracker.values())

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h2 style='color:white;'>🔍 Filtres</h2>", unsafe_allow_html=True)
    subject = st.text_input("Sujet de veille", value="Swiss krono")
    col_d1, col_d2 = st.columns(2)
    with col_d1: d_min = st.date_input("Du", value=None)
    with col_d2: d_max = st.date_input("Au", value=None)
    st.write("---")
    sort_option = st.selectbox("Trier par", ["Plus récent", "Plus ancien", "Média"])

# --- NAVIGATION ---
view_selection = st.radio("Navigation pays :", options=list(EDITIONS.keys()), horizontal=True, label_visibility="collapsed")

# --- EXECUTION ---
articles = fetch_data(subject, d_min, d_max, view_selection)

# Tri
if sort_option == "Plus récent": articles.sort(key=lambda x: x['timestamp'] if x['timestamp'] else 0, reverse=True)
elif sort_option == "Plus ancien": articles.sort(key=lambda x: x['timestamp'] if x['timestamp'] else 0, reverse=False)
else: articles.sort(key=lambda x: x['source'])

# --- HEADER ---
st.markdown("<h1 style='color:white; font-size:2.5rem; font-weight:800; margin-bottom:20px;'>Veille Médiatique</h1>", unsafe_allow_html=True)

# --- DASHBOARD ---
if articles:
    m1, m2, m3 = st.columns(3)
    with m1: st.markdown(f'<div class="stat-card-fixed"><small style="color:rgba(255,255,255,0.4)">TOTAL UNIQUE</small><div style="font-size:2.5rem; font-weight:800; color:#dc2626;">{len(articles)}</div></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="stat-card-fixed"><small style="color:rgba(255,255,255,0.4)">ZONE SÉLECTIONNÉE</small><div style="font-size:1.2rem; font-weight:700; color:white;">{view_selection}</div></div>', unsafe_allow_html=True)
    
    # Date propre pour m3
    dt_m = datetime(*articles[0]['timestamp'][:6]) if articles[0]['timestamp'] else datetime.now()
    with m3: st.markdown(f'<div class="stat-card-fixed"><small style="color:rgba(255,255,255,0.4)">DERNIER ARTICLE</small><div style="font-size:1rem; font-weight:700; color:white;">{dt_m.strftime("%d/%m/%Y")}</div></div>', unsafe_allow_html=True)

st.write("##")

# --- GRILLE D'ARTICLES ---
if not articles:
    st.info("Aucun article trouvé.")
else:
    cols = st.columns(3)
    for idx, art in enumerate(articles):
        # Création dynamique des tags pays
        country_badges = "".join([f'<div class="country-tag">{c}</div>' for c in sorted(list(art['countries']))])
        
        with cols[idx % 3]:
            # Structure HTML ultra-simplifiée pour éviter les bugs d'affichage
            st.markdown(f"""
                <div class="article-card">
                    <div>
                        <div class="badges-container">
                            <div class="source-badge">{art['source']}</div>
                            {country_badges}
                        </div>
                        <div class="article-title">{art['title']}</div>
                    </div>
                    <div>
                        <div style="color: rgba(255,255,255,0.4); font-size: 0.8rem; margin-bottom: 12px;">📅 {art['published'][:16]}</div>
                        <a href="{art['link']}" target="_blank" class="btn-glass-red">Consulter l'article</a>
                    </div>
                </div>
                """, unsafe_allow_html=True)