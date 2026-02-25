import streamlit as st

def inject_custom_css():
    st.markdown("""
    <style>
    .main .block-container { max-width: 95% !important; padding-top: 2rem; }
    
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #000000, #150505, #350a0a);
        background-attachment: fixed;
    }

    /* ----------------------------------------------------------------- */
    /* LA CORRECTION : Ciblage ultra-précis du conteneur de la carte     */
    /* ----------------------------------------------------------------- */
    
    /* En utilisant "> div[data-testid='stElementContainer']", on s'assure */
    /* de ne cibler QUE la carte, et absolument pas la galerie ! */
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .sk-marker) {
        background: rgba(20, 20, 20, 0.7);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 24px;
        min-height: 400px; /* min-height permet à la carte de respirer et s'élargir */
        width: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        margin-bottom: 20px;
        transition: 0.3s ease;
    }
    
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .sk-marker):hover {
        border-color: #dc2626; box-shadow: 0 4px 15px rgba(220, 38, 38, 0.2);
    }

    /* ----------------------------------------------------------------- */
    /* STYLE DES ÉLÉMENTS INTERNES                                       */
    /* ----------------------------------------------------------------- */
    
    .sk-marker { display: none; } /* Le marqueur invisible */

    .source-badge { background: rgba(220, 38, 38, 0.8); border: 1px solid #dc2626; color: white; padding: 2px 10px; border-radius: 6px; font-size: 0.7rem; font-weight: 800; text-transform: uppercase; margin-bottom: 12px; display: inline-block; }
    .article-title { color: white; font-size: 1.15rem; font-weight: 700; line-height: 1.3; margin-bottom: 5px; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
    .date-txt { color: rgba(255,255,255,0.4); font-size: 0.8rem; margin-bottom: 15px; }
    .article-desc { color: rgba(255,255,255,0.7); font-size: 0.85rem; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
    .paywall-alert { color: #ff4b4b; font-size: 0.7rem; font-weight: 800; text-transform: uppercase; margin-top: 10px; margin-bottom: 10px;}

    /* Les boutons Streamlit au fond de la carte */
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .sk-marker) button,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .sk-marker) a {
        background: linear-gradient(90deg, #991b1b, #dc2626) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        padding: 10px 0 !important;
        transition: 0.3s ease !important;
        width: 100%;
        margin-top: auto; /* Force le bouton tout en bas */
    }
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .sk-marker) button:hover,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .sk-marker) a:hover {
        filter: brightness(1.2) !important;
        box-shadow: 0 4px 15px rgba(220, 38, 38, 0.4) !important;
    }
    </style>
    """, unsafe_allow_html=True)


@st.dialog("Article", width="large")
def show_full_modal(article, source_name):
    st.markdown("""
    <style>
    div[data-testid="stDialog"] > div[role="dialog"] {
        width: 75vw !important;
        max-width: 75vw !important;
        height: auto !important;
    }
    .modal-margins { padding: 0 8%; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='modal-margins'>", unsafe_allow_html=True)
    st.markdown(f"<h1 style='color:white; font-size:2.2rem; line-height:1.2;'>{article.get('title', 'Sans titre')}</h1>", unsafe_allow_html=True)
    st.markdown(f"<b style='color:#dc2626; font-size:1.1rem;'>{source_name.upper()}</b> &nbsp;|&nbsp; <span style='color:rgba(255,255,255,0.4);'>📅 {str(article.get('created_at'))[:10]}</span>", unsafe_allow_html=True)
    st.write("---")
    
    if article.get('description'):
        st.markdown(f"<p style='color:#ccc; font-style:italic; font-size:1.1rem;'>{article.get('description')}</p>", unsafe_allow_html=True)
        st.write("---")
        
    st.write(article.get('content', 'Contenu non disponible.'))
    st.markdown("</div>", unsafe_allow_html=True)

def render_article_card(article, source_name):
    title = article.get('title') or "Titre indisponible"
    desc = article.get('description') or "Pas de description."
    date_str = str(article.get('created_at', ''))[:10]
    is_paywall = article.get('is_paywall', False)
    link = article.get('article_url', '#')

    with st.container():
        # HTML 100% collé à gauche. On injecte le marqueur ".sk-marker" caché.
        html_content = f'''<span class="sk-marker"></span>
<div>
<div class="source-badge">{source_name}</div>
<div class="article-title">{title}</div>
<div class="date-txt">📅 {date_str}</div>
<div class="article-desc">{desc}</div>
{f'<div class="paywall-alert">🚫 ACCÈS ABONNÉ (PAYWALL)</div>' if is_paywall else ''}
</div>'''
        st.markdown(html_content, unsafe_allow_html=True)
        
        # Les boutons déclencheurs
        if is_paywall:
            st.link_button("Lire l'article en ligne", link, use_container_width=True)
        else:
            if st.button("Lire l'article", key=f"btn_{article['id']}", use_container_width=True):
                show_full_modal(article, source_name)