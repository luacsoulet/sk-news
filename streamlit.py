import streamlit as st
import feedparser
import urllib.parse
from datetime import datetime
from collections import Counter

# --- CONFIGURATION ---
st.set_page_config(page_title="Veille Médias Stratégique", page_icon="🔻", layout="wide")

# --- CSS "ULTRA GLASSMORPHISM RED - DYNAMIC EDITION" ---
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
    [data-testid="stSidebar"] .stMarkdown p, [data-testid="stSidebar"] label {
        color: #ffffff !important;
        font-weight: 600;
    }

    /* Simulation de Tabs avec Radio Horizontal */
    div.stRadio > div {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 5px;
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    div.stRadio > div > label {
        color: white !important;
        font-weight: 600 !important;
        padding: 10px 20px !important;
        border-radius: 10px !important;
    }
    div.stRadio > div > label[data-baseweb="radio"] {
        background: transparent !important;
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

    /* Grille Articles */
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
        margin-bottom: 20px;
    }
    .source-badge {
        background: rgba(220, 38, 38, 0.25);
        border: 1px solid rgba(220, 38, 38, 0.6);
        color: #ff4b4b;
        padding: 4px 12px;
        border-radius: 8px;
        font-size: 0.7rem;
        font-weight: 800;
        text-transform: uppercase;
        width: fit-content;
    }
    .btn-glass-red {
        display: block; width: 100%; background: linear-gradient(90deg, #991b1b, #dc2626);
        color: white !important; text-align: center; padding: 10px 0;
        border-radius: 12px; text-decoration: none !important; font-weight: 700;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIQUE RÉCUPÉRATION ---

EDITIONS = {
    "🌐 Global": {"hl": "fr", "gl": "FR", "ceid": "FR:fr", "flag": "🌐"},
    "🇫🇷 France": {"hl": "fr", "gl": "FR", "ceid": "FR:fr", "flag": "🇫🇷"},
    "🇨🇭 Suisse": {"hl": "fr", "gl": "CH", "ceid": "CH:fr", "flag": "🇨🇭"},
    "🇺🇸 USA": {"hl": "en", "gl": "US", "ceid": "US:en", "flag": "🇺🇸"},
}

def fetch_country_data(query, start_date, end_date, country_label):
    # Si Global, on doit techniquement tout récupérer pour le calcul
    # Mais pour l'affichage simple, on cible l'édition demandée
    key = "France" if "France" in country_label else ("Suisse" if "Suisse" in country_label else "USA")
    if country_label == "🌐 Global":
        # Logique pour agréger les 3 pays
        all_data = []
        for k in ["🇫🇷 France", "🇨🇭 Suisse", "🇺🇸 USA"]:
            all_data.extend(fetch_country_data(query, start_date, end_date, k))
        # Dédoublonnage final
        seen = set()
        unique = []
        for a in all_data:
            if a['title'] not in seen:
                unique.append(a)
                seen.add(a['title'])
        return unique

    # Extraction propre du pays
    clean_key = country_label.split(" ")[1]
    ed = EDITIONS[country_label]
    
    encoded_query = urllib.parse.quote(query)
    full_q = encoded_query
    if start_date: full_q += f"+after:{start_date.strftime('%Y-%m-%d')}"
    if end_date: full_q += f"+before:{end_date.strftime('%Y-%m-%d')}"
    
    url = f"https://news.google.com/rss/search?q={full_q}&hl={ed['hl']}&gl={ed['gl']}&ceid={ed['ceid']}"
    feed = feedparser.parse(url)
    
    seen_titles = set()
    parsed_data = []
    for entry in feed.entries:
        title = entry.title.rsplit(' - ', 1)[0]
        if title not in seen_titles:
            source = entry.title.rsplit(' - ', 1)[1] if ' - ' in entry.title else "Source"
            parsed_data.append({
                "title": title,
                "source": source,
                "link": entry.link,
                "published": entry.published,
                "timestamp": entry.get('published_parsed'),
                "region": clean_key
            })
            seen_titles.add(title)
    return parsed_data

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h2 style='color:white;'>🔍 Configuration</h2>", unsafe_allow_html=True)
    subject = st.text_input("Sujet de veille", value="Swiss krono")
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        d_min = st.date_input("Du", value=None)
    with col_d2:
        d_max = st.date_input("Au", value=None)
    
    st.write("---")
    sort_option = st.selectbox("Trier par", ["Plus récent", "Plus ancien", "Média"])

# --- NAVIGATION PAR "TABS" DYNAMIQUES ---
st.write("##")
view_selection = st.radio(
    "Sélectionnez la zone :",
    options=list(EDITIONS.keys()),
    horizontal=True,
    label_visibility="collapsed"
)

# --- RÉCUPÉRATION DES DONNÉES SELON SÉLECTION ---
articles = fetch_country_data(subject, d_min, d_max, view_selection)

# Tri
if sort_option == "Plus récent": articles.sort(key=lambda x: x['timestamp'], reverse=True)
elif sort_option == "Plus ancien": articles.sort(key=lambda x: x['timestamp'], reverse=False)
else: articles.sort(key=lambda x: x['source'])

# --- HEADER (SANS COMPTEUR) ---
st.markdown(f"""
    <div style="margin-bottom:25px;">
        <h1 style="margin:0; color:white; font-size:2.8rem; font-weight:800; letter-spacing:-1px;">Veille Médiatique</h1>
    </div>
    """, unsafe_allow_html=True)

# --- DASHBOARD DYNAMIQUE ---
if articles:
    dt_min = datetime(*articles[-1]['timestamp'][:6])
    dt_max = datetime(*articles[0]['timestamp'][:6])
    
    m1, m2, m3 = st.columns(3)
    with m1: 
        st.markdown(f"""<div class="stat-card-fixed">
            <small style="color:rgba(255,255,255,0.4)">ARTICLES ({view_selection.split(' ')[-1]})</small>
            <div style="font-size:2.5rem; font-weight:800; color:#dc2626;">{len(articles)}</div>
        </div>""", unsafe_allow_html=True)
    with m2: 
        st.markdown(f"""<div class="stat-card-fixed">
            <small style="color:rgba(255,255,255,0.4)">ZONE ACTIVE</small>
            <div style="font-size:1.2rem; font-weight:700; color:white;">{view_selection}</div>
        </div>""", unsafe_allow_html=True)
    with m3: 
        st.markdown(f"""<div class="stat-card-fixed">
            <small style="color:rgba(255,255,255,0.4)">PÉRIODE</small>
            <div style="font-size:0.95rem; font-weight:700; color:white;">{dt_min.strftime("%d/%m/%Y")}<br>{dt_max.strftime("%d/%m/%Y")}</div>
        </div>""", unsafe_allow_html=True)

st.write("##")

# --- GRILLE D'ARTICLES ---
if not articles:
    st.info("Aucun article trouvé pour cette sélection.")
else:
    cols = st.columns(3)
    for idx, art in enumerate(articles):
        with cols[idx % 3]:
            st.markdown(f"""
                <div class="article-card">
                    <div>
                        <div class="source-badge">{art['source']}</div>
                        <div style="font-size: 1.15rem; font-weight: 600; color: white; line-height: 1.4; margin-top:12px;">{art['title']}</div>
                    </div>
                    <div>
                        <div style="color: rgba(255,255,255,0.4); font-size: 0.85rem; margin-bottom: 15px;">📅 {art['published'][:16]}</div>
                        <a href="{art['link']}" target="_blank" class="btn-glass-red">Consulter l'article</a>
                    </div>
                </div>
                """, unsafe_allow_html=True)