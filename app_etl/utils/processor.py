import os, sys, subprocess, json, uuid, re
from datetime import datetime
from .helpers import clean_journal_name, should_ignore, normalize_title

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def process_single_article(entry, sources_dict, existing_titles_normalized):
    if hasattr(entry, 'title'):
        raw_title, article_link = entry.title, entry.link
    else:
        raw_title, article_link = entry.get('titre', ''), entry.get('url', '')

    parts = re.split(r' [-\u2013\u2014|] ', raw_title)
    title_only = " ".join(parts[:-1]) if len(parts) > 1 else raw_title
    raw_journal = parts[-1] if len(parts) > 1 else "Inconnu"
    
    if normalize_title(title_only) in existing_titles_normalized:
        return {"journal": raw_journal, "titre": title_only, "url": article_link, "statut": "⏭️ Doublon"}

    journal_key = clean_journal_name(raw_journal)
    source_info = sources_dict.get(journal_key)

    res_base = {"journal": raw_journal, "titre": title_only, "url": article_link, "statut": "❓ Inconnu"}
    data_rss = {
        "title": title_only, 
        "description": None, 
        "content": None, 
        "article_url": article_link, 
        "is_paywall": True, 
        "news_source_id": source_info['id'] if source_info else None, 
        "created_at": datetime.now().isoformat()
    }

    if not source_info:
        return {**res_base, "data_rss": data_rss}

    target_script = os.path.join(PROJECT_ROOT, "news_source", journal_key, "all_in_one.py")
    db_allows_pro = source_info.get('as_program', False)
    file_exists = os.path.exists(target_script)

    temp_json = os.path.join(PROJECT_ROOT, f"temp_res_{uuid.uuid4().hex[:8]}.json")

    try:
        if db_allows_pro and file_exists:
            script_to_run = target_script
            statut_label = "✅ Scraping (Pro)"
        else:
            script_to_run = os.path.join(PROJECT_ROOT, "generic_fallback.py")
            
            # --- LE DÉTECTEUR DE PROBLÈME MAGIQUE EST ICI ---
            if not db_allows_pro:
                statut_label = "❌ BDD bloque (as_program=False)"
            elif not file_exists:
                statut_label = f"❌ Dossier introuvable ({journal_key})"
            else:
                statut_label = "🔍 Scraping (Générique)"

        subprocess.run([sys.executable, script_to_run, article_link, temp_json, str(source_info['id'])], timeout=120, check=True)

        if os.path.exists(temp_json):
            with open(temp_json, "r", encoding="utf-8") as f: data_scrap = json.load(f)
            os.remove(temp_json)
            return {**res_base, "statut": statut_label, "data_scrap": data_scrap, "data_rss": data_rss, "has_scrap": True}
        else:
            return {**res_base, "statut": f"❌ Fichier non créé ({statut_label})", "data_rss": data_rss, "has_scrap": False}
            
    except Exception as e:
        if os.path.exists(temp_json): os.remove(temp_json)
        return {**res_base, "statut": f"❌ Plantage: {str(e)[:15]}", "data_rss": data_rss, "has_scrap": False}