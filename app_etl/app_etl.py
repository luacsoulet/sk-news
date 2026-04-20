import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
import re
import calendar
import time
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed

# Importation des modules locaux
from db import supabase_db as db
from utils import helpers, processor, check_validity

# --- 1. CONFIGURATION & ÉTATS DE SESSION ---
st.set_page_config(page_title="Robot News SK - Dashboard ETL", layout="wide")

def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

keys_to_init = {
    'rss_entries': [],           
    'articles_to_export': [],    
    'full_execution_log': [],    
    'unknown_sources': {},       
    'start_date': date(2026, 1, 1),
    'end_date': date(2026, 12, 31),
    'sync_status': None
}

for key, default in keys_to_init.items():
    if key not in st.session_state:
        st.session_state[key] = default

supabase = db.get_client()

# --- 2. FILTRES DE DATES ET RACCOURCIS ---
st.title("🤖 Robot News SK - Dashboard ETL")

st.write("### 📅 Période de recherche Google News")
col_d1, col_d2 = st.columns(2)
st.session_state.start_date = col_d1.date_input("Date de début", value=st.session_state.start_date)
st.session_state.end_date = col_d2.date_input("Date de fin", value=st.session_state.end_date)

c_btn1, c_btn2, c_btn3 = st.columns([1, 1.2, 4])

if c_btn1.button("➕ 1 Mois"):
    st.session_state.start_date = add_months(st.session_state.start_date, 1)
    st.session_state.end_date = add_months(st.session_state.end_date, 1)
    st.rerun()

if c_btn2.button("⏩ Trimestre Suivant (+4m)"):
    st.session_state.start_date = add_months(st.session_state.start_date, 4)
    st.session_state.end_date = add_months(st.session_state.end_date, 4)
    st.rerun()

if c_btn3.button("🔄 Reset Année 2026"):
    st.session_state.start_date = date(2026, 1, 1)
    st.session_state.end_date = date(2026, 12, 31)
    st.rerun()

st.divider()

# --- 3. ÉTAPE 1 : ANALYSE DU FLUX & SOURCES ---
st.write("### 🔍 Étape 1 : Analyse des sources")

if st.button("🚀 Lancer l'Analyse"):
    with st.status("Collecte des données...", expanded=True) as status:
        raw_sources, existing_titles = db.fetch_initial_data(supabase)
        titles_norm_bdd = {helpers.normalize_title(t) for t in existing_titles}
        sources_dict = {helpers.clean_journal_name(s['name']): s for s in raw_sources}
        
        st.write(f"📊 {len(sources_dict)} sources connues chargées.")

        query = f"Swiss krono after:{st.session_state.start_date} before:{st.session_state.end_date}"
        encoded_query = urllib.parse.quote(query)
        feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=fr&gl=FR&ceid=FR:fr"
        feed = feedparser.parse(feed_url)
        
        st.write(f"DEBUG : Google News a renvoyé {len(feed.entries)} articles au total.")
        
        st.session_state.rss_entries = []
        st.session_state.unknown_sources = {}
        st.session_state.full_execution_log = []

        for entry in feed.entries:
            parts = re.split(r' [-\u2013\u2014|] ', entry.title)
            journal_raw = parts[-1] if len(parts) > 1 else "Inconnu"
            title_only = " - ".join(parts[:-1]) if len(parts) > 1 else entry.title
            
            j_slug = helpers.clean_journal_name(journal_raw)
            norm_title = helpers.normalize_title(title_only)

            log_item = {"titre": title_only, "journal": journal_raw, "slug": j_slug}

            if norm_title in titles_norm_bdd:
                log_item["statut"] = "⏭️ Doublon RSS"
                st.write(f"⏭️ **Doublon (RSS)** : {title_only[:50]}...")
            elif j_slug not in sources_dict:
                log_item["statut"] = "⚠️ Inconnu"
                st.session_state.unknown_sources.setdefault(journal_raw, []).append(entry)
                st.warning(f"⚠️ **Source inconnue** : {journal_raw}")
            else:
                log_item["statut"] = "✅ Prêt"
                entry.source_id = sources_dict[j_slug]['id']
                entry.j_slug = j_slug
                st.session_state.rss_entries.append(entry)
            
            st.session_state.full_execution_log.append(log_item)
            
        status.update(label="Analyse terminée !", state="complete")

if st.session_state.unknown_sources:
    for name in list(st.session_state.unknown_sources.keys()):
        with st.expander(f"➕ Enregistrer : {name}"):
            c_in, c_bt = st.columns([3, 1])
            new_slug = c_in.text_input("Identifiant (Slug)", value=helpers.clean_journal_name(name), key=f"slug_{name}")
            if c_bt.button("Ajouter", key=f"btn_{name}"):
                db.add_new_source(supabase, new_slug)
                st.rerun()

# --- 4. ÉTAPE 2 : SCRAPING & VALIDATIONS ---
if st.session_state.rss_entries and not st.session_state.unknown_sources:
    st.info(f"🔥 {len(st.session_state.rss_entries)} nouveaux articles détectés.")
    if st.button("📡 Lancer l'extraction du contenu (Playwright)"):
        raw_src, existing_titles = db.fetch_initial_data(supabase)
        titles_norm_bdd = {helpers.normalize_title(t) for t in existing_titles}
        current_sources_dict = {helpers.clean_journal_name(s['name']): s for s in raw_src}

        st.session_state.articles_to_export = []
        
        with st.status("Scraping et validation en cours...", expanded=True):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(processor.process_single_article, e, current_sources_dict, set()) for e in st.session_state.rss_entries]
                for f in as_completed(futures):
                    res = f.result()
                    
                    # 1. Vérification Doublon sur titre réel (Scrappé)
                    scraped_title = res.get("data_scrap", {}).get("title", "")
                    res["is_double_after_scrap"] = helpers.normalize_title(scraped_title) in titles_norm_bdd
                    
                    # 2. Vérification présence "Swiss Krono" (Pertinence)
                    full_txt = f"{scraped_title} {res.get('data_scrap', {}).get('content', '')}"
                    res["is_relevant"] = check_validity.check_keyword_presence(full_txt)
                    
                    st.session_state.articles_to_export.append(res)
                    st.write(f"Vérifié : {res.get('journal')} - {res.get('titre')[:40]}...")

# --- 5. ÉTAPE 3 : ARBITRAGE ET TABLEAU FINAL ---
if st.session_state.articles_to_export:
    st.divider()
    st.subheader("📋 Arbitrage final des données")
    st.info("🔴 Rouge : Doublon BDD | 🟠 Orange : 'Swiss Krono' non trouvé")

    arbitrage_list = []
    for i, a in enumerate(st.session_state.articles_to_export):
        rss = a.get("data_rss", {})
        scrap = a.get("data_scrap", {})
        
        t_rss = rss.get("title") or "Sans titre"
        t_scrap = scrap.get("title") or "❌ Échec extraction"
        c_rss = rss.get("content") or ""
        c_scrap = scrap.get("content") or ""
        
        # Logique de statut pour la couleur
        if a.get("is_double_after_scrap"):
            statut_label = "🚩 DOUBLON"
        elif not a.get("is_relevant"):
            statut_label = "⚠️ HORS-SUJET"
        else:
            statut_label = "✨ NEUF"

        arbitrage_list.append({
            "INDEX_INT": i,
            "Sync": (not a.get("is_double_after_scrap")) and a.get("is_relevant"),
            "Statut": statut_label,
            "Journal": a["journal"],
            "Source_Titre": "Scrap" if a.get("has_scrap") else "RSS",
            "Source_Desc": "Scrap" if a.get("has_scrap") else "RSS",
            "Titre_RSS": t_rss,
            "Titre_Scrap": t_scrap,
            "Aperçu_RSS": c_rss[:100] + "..." if c_rss else "Vide",
            "Aperçu_Scrap": c_scrap[:100] + "..." if c_scrap else "Vide",
            "URL": a["url"]
        })

    df_arb = pd.DataFrame(arbitrage_list)

    # Fonction pour colorer les doublons en rouge (#F53811) et les hors-sujet en orange
    def style_rows(row):
        if row.Statut == "🚩 DOUBLON":
            return ['background-color: #F53811'] * len(row) # Rouge
        if row.Statut == "⚠️ HORS-SUJET":
            return ['background-color: #FFA500'] * len(row) # Orange
        return [''] * len(row)

    # Affichage du tableau d'édition
    edited_df = st.data_editor(
        df_arb.style.apply(style_rows, axis=1),
        column_config={
            "Sync": st.column_config.CheckboxColumn("Sync ?"),
            "Source_Titre": st.column_config.SelectboxColumn("Titre via", options=["RSS", "Scrap"]),
            "Source_Desc": st.column_config.SelectboxColumn("Contenu via", options=["RSS", "Scrap"]),
            "Aperçu_RSS": st.column_config.TextColumn("Aperçu RSS", width="medium"),
            "Aperçu_Scrap": st.column_config.TextColumn("Aperçu Scrap", width="medium"),
            "URL": st.column_config.LinkColumn("Lien"),
            "INDEX_INT": None # Caché
        },
        disabled=["Statut", "Journal", "Titre_RSS", "Titre_Scrap", "Aperçu_RSS", "Aperçu_Scrap", "URL"],
        hide_index=True, width="stretch", height=450
    )

    if st.button("🔥 SYNCHRONISER LA SÉLECTION VERS SUPABASE"):
        success_count = 0
        for idx, row in edited_df.iterrows():
            if not row["Sync"]: continue
            
            # Récupération de l'objet original via l'index stocké
            original = st.session_state.articles_to_export[row["INDEX_INT"]]
            
            # On prépare le payload final sur mesure
            final_payload = original["data_scrap"].copy() if original.get("has_scrap") else original["data_rss"].copy()
            
            # Application de l'arbitrage Titre
            if row["Source_Titre"] == "RSS":
                final_payload["title"] = original["data_rss"]["title"]
            else:
                final_payload["title"] = original["data_scrap"].get("title", original["data_rss"]["title"])
            
            # Application de l'arbitrage Description
            if row["Source_Desc"] == "RSS":
                final_payload["content"] = original["data_rss"]["content"]
            else:
                final_payload["content"] = original["data_scrap"].get("content", original["data_rss"]["content"])

            db.upsert_article(supabase, final_payload)
            success_count += 1
        
        st.session_state.articles_to_export = []
        st.session_state.rss_entries = []
        st.success(f"✅ {success_count} articles traités avec succès !")
        time.sleep(1)
        st.rerun()

# --- 6. LOGS TECHNIQUES ---
with st.expander("🛠️ Debug : Signatures et Slugs"):
    if st.session_state.full_execution_log:
        st.dataframe(pd.DataFrame(st.session_state.full_execution_log))