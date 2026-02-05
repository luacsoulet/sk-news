import streamlit as st
import feedparser
import urllib.parse
from datetime import datetime
from collections import Counter

# Configuration de la page
st.set_page_config(page_title="Veille Médiatique", page_icon="🔻", layout="wide")

# --- CSS "ULTRA GLASSMORPHISM RED - V3" ---
st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #000000, #150505, #350a0a);
        background-attachment: fixed;
    }
    
    [data-testid="stHeader"] { background: transparent; }

    /* SIDEBAR - Ultra contrastée */
    [data-testid="stSidebar"] {
        background-color: #050505 !important; 
        border-right: 3px solid #dc2626 !important; 
        box-shadow: 10px 0 30px rgba(0,0,0,1);
    }
    
    /* Titre et Badge Compteur */
    .title-wrapper {
        display: flex;
        align-items: center;
        gap: 15px;
        margin-bottom: 30px;
    }
    .main-badge {
        background: rgba(220, 38, 38, 0.4);
        border: 2px solid #dc2626;
        color: #ffffff;
        padding: 5px 18px;
        border-radius: 15px;
        font-weight: 800;
        font-size: 1.6rem;
        box-shadow: 0 0 15px rgba(220, 38, 38, 0.3);
    }

    /* DASHBOARD - Cases identiques */
    .stat-card-fixed {
        background: rgba(30, 30, 30, 0.6);
        backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 20px;
        height: 140px; 
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: flex-start;
    }

    /* BADGE SOURCE (Ajusté au texte) */
    .source-badge {
        background: rgba(220, 38, 38, 0.25);
        border: 1px solid rgba(220, 38, 38, 0.6);
        color: #ff4b4b;
        padding: 4px 12px;
        border-radius: 8px;
        font-size: 0.7rem;
        font-weight: 800;
        text-transform: uppercase;
        margin-bottom: 12px;
        width: fit-content; 
        display: block; 
    }

    /* GRILLE ARTICLES */
    .article-card {
        background: rgba(20, 20, 20, 0.7);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 24px;
        height: 380px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: all 0.3s ease;
    }
    .article-card:hover {
        transform: translateY(-8px);
        background: rgba(45, 10, 10, 0.85);
        border-color: rgba(220, 38, 38, 0.7);
    }

    .btn-glass-red {
        display: block;
        width: 100%;
        background: linear-gradient(90deg, #991b1b, #dc2626);
        color: white !important;
        text-align: center;
        padding: 12px 0;
        border-radius: 12px;
        text-decoration: none !important;
        font-weight: 700;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIQUE ---

def clean_and_parse_entries(entries):
    parsed_data = []
    for entry in entries:
        title = entry.title
        parts = title.rsplit(' - ', 1)
        clean_title = parts[0]
        source = parts[1] if len(parts) > 1 else "Source"
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
    if start_date: full_query += f"+after:{start_date.strftime('%Y-%m-%d')}"
    if end_date: full_query += f"+before:{end_date.strftime('%Y-%m-%d')}"
    
    feed_url = f"https://news.google.com/rss/search?q={full_query}&hl=fr&gl=FR&ceid=FR:fr"
    feed = feedparser.parse(feed_url)
    return clean_and_parse_entries(feed.entries)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h2 style='color:white; font-size:1.5rem;'>⚙️ Paramètres</h2>", unsafe_allow_html=True)
    subject = st.text_input("Sujet de veille", value="Swiss krono")
    date_min_input = st.date_input("Depuis le", value=None)
    date_max_input = st.date_input("Jusqu'au", value=None)
    
    all_articles = fetch_news(subject, date_min_input, date_max_input)
    sources_disponibles = sorted(list(set(a['source'] for a in all_articles)))
    selected_sources = st.multiselect("Filtrer sources", sources_disponibles, default=sources_disponibles)
    sort_option = st.selectbox("Trier par", ["Plus récent", "Plus ancien", "Média"])

# --- TRAITEMENT ---
filtered = [a for a in all_articles if a['source'] in selected_sources]
if sort_option == "Plus récent": filtered.sort(key=lambda x: x['timestamp'], reverse=True)
elif sort_option == "Plus ancien": filtered.sort(key=lambda x: x['timestamp'], reverse=False)
else: filtered.sort(key=lambda x: x['source'])

# --- AFFICHAGE HEADER ---
count = len(filtered)
st.markdown(f"""
    <div class="title-wrapper">
        <h1 style="margin:0; color: white; font-size: 2.5rem; font-weight: 800; letter-spacing: -1px;">Veille Médiatique</h1>
    </div>
    """, unsafe_allow_html=True)

if not filtered:
    st.info("Utilisez la barre latérale pour lancer une recherche.")
else:
    # --- DASHBOARD (CORRECTION DATES ICI) ---
    top_source = Counter([a['source'] for a in filtered]).most_common(1)[0][0]
    
    # Transformation des struct_time en objets datetime pour un formatage propre
    dt_min = datetime(*filtered[-1]['timestamp'][:6])
    dt_max = datetime(*filtered[0]['timestamp'][:6])
    date_range = f"{dt_min.strftime('%d/%m/%Y')} — {dt_max.strftime('%d/%m/%Y')}"
    
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f"""<div class="stat-card-fixed">
            <div style="color: rgba(255,255,255,0.4); font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">Articles</div>
            <div style="font-size: 2.2rem; font-weight: 800; color: #dc2626;">{count}</div>
        </div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""<div class="stat-card-fixed">
            <div style="color: rgba(255,255,255,0.4); font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">Top Source</div>
            <div style="font-size: 1.2rem; font-weight: 700; color: white;">{top_source}</div>
        </div>""", unsafe_allow_html=True)
    with m3:
        st.markdown(f"""<div class="stat-card-fixed">
            <div style="color: rgba(255,255,255,0.4); font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">Période</div>
            <div style="font-size: 0.95rem; font-weight: 700; color: white;">{date_range}</div>
        </div>""", unsafe_allow_html=True)

    st.write("##")

    # --- GRID ---
    cols = st.columns(3)
    for idx, art in enumerate(filtered):
        with cols[idx % 3]:
            # Pour la grille, on garde un peu plus de détails sur la date
            st.markdown(f"""
                <div class="article-card">
                    <div>
                        <div class="source-badge">{art['source']}</div>
                        <div style="font-size: 1.15rem; font-weight: 600; color: white; line-height: 1.4;">{art['title']}</div>
                    </div>
                    <div>
                        <div style="color: rgba(255,255,255,0.4); font-size: 0.8rem; margin-bottom: 15px;">📅 {art['published'][:16]}</div>
                        <a href="{art['link']}" target="_blank" class="btn-glass-red">Consulter l'article</a>
                    </div>
                </div>
                """, unsafe_allow_html=True)