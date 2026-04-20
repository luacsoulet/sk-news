import sys
import time
import os
import re
import json
import html
import unicodedata
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- 1. FONCTIONS DE NETTOYAGE ---

def normalize_url(url):
    if not url or "google." in url: return url
    u = urlparse(url)
    return urlunparse((u.scheme, u.netloc, u.path, '', '', ''))

def reparer_encodage(text):
    if not text: return ""
    try:
        text = text.encode('latin-1').decode('utf-8')
    except: pass
    return text.replace('Â', '').replace('\xa0', ' ')

def nettoyer_bloc_texte(raw_text):
    if not raw_text: return ""
    text = html.unescape(raw_text)
    text = re.sub(r'<(p|br|div|h1|h2|h3)[^>]*>', '\n\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    return reparer_encodage(text).strip()

def format_filename(title):
    """Transforme un titre en nom de fichier valide pour Windows"""
    if not title or title == "Titre non trouvé":
        return f"article_sans_titre_{int(time.time())}"
    t = ''.join(c for c in unicodedata.normalize('NFD', title.lower()) if unicodedata.category(c) != 'Mn')
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    return t[:100]

# --- 2. LOGIQUE DE NAVIGATION ET EXTRACTION (Blick) ---

def extract_blick_full(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Flash (Blick) : {google_url}")
    
    article_data = {
        "title": "Titre non trouvé", "description": "", "content": "",
        "article_url": google_url, "is_paywall": False,
        "news_source_id": int(source_id), "created_at": datetime.now().isoformat(), "status": "fail"
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="fr-CH"
            )
            page = context.new_page()

            # Bloquer les ressources lourdes
            page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,css,mp4,mp3}", lambda route: route.abort())

            page.goto(google_url, wait_until="commit", timeout=60000)

            # --- CONTOURNEMENT DE LA POP-UP GOOGLE ---
            if "google." in page.url or "consent." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|J'accepte|Accepter tout", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).first.click(timeout=5000)
                    time.sleep(1)
                except: pass

            # Attente intelligente de la redirection
            start_redir = time.time()
            while time.time() - start_redir < 10:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.5)

            # Sécurité : on attend le script caché qui contient les données de Blick
            try:
                page.wait_for_selector("script#__NEXT_DATA__", timeout=15000)
            except Exception:
                print("⚠️ Attention : La balise de données JSON n'a pas été trouvée à temps.")

            # Mise à jour de l'URL finale nettoyée
            article_data["article_url"] = normalize_url(page.url)

            # Extraction Magique (Récupération directe dans le JSON du code source)
            soup = BeautifulSoup(page.content(), 'html.parser')
            script_next = soup.find('script', id='__NEXT_DATA__')
            corps_segments = []

            if script_next and script_next.string:
                data = json.loads(script_next.string)
                def chercher_donnees(obj):
                    if isinstance(obj, dict):
                        if "isPaid" in obj: article_data["is_paywall"] = obj["isPaid"]
                        if "headline" in obj: article_data["title"] = nettoyer_bloc_texte(obj["headline"])
                        kind = obj.get("kind", [])
                        if isinstance(kind, list) and "text-body" in kind and "text" in obj:
                            corps_segments.append(obj["text"])
                        for v in obj.values(): chercher_donnees(v)
                    elif isinstance(obj, list):
                        for item in obj: chercher_donnees(item)
                chercher_donnees(data)

            article_data["content"] = "\n\n".join([nettoyer_bloc_texte(bloc) for bloc in corps_segments])
            if len(article_data["content"]) > 100: 
                article_data["status"] = "success"

            browser.close()

    except Exception as e:
        print(f"💥 Erreur globale détectée : {e}")
        article_data["content"] = f"Erreur : {str(e)}"

    # --- 3. DOUBLE SAUVEGARDE GARANTIE ---
    print(f"💾 Écriture des données temporaires dans : {output_filename}")
    try:
        # Fichier 1 : Pour processor.py (temp_res_XXX.json)
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(article_data, f, ensure_ascii=False, indent=4)
        
        # Fichier 2 : Sauvegarde avec le vrai nom de l'article
        dossier_parent = os.path.dirname(os.path.abspath(output_filename))
        nom_propre = format_filename(article_data["title"])
        fichier_titre = os.path.join(dossier_parent, f"{nom_propre}.json")
        
        with open(fichier_titre, "w", encoding="utf-8") as f2:
            json.dump(article_data, f2, ensure_ascii=False, indent=4)
            
        print(f"✅ Fichiers JSON créés avec succès !")
    except Exception as e:
        print(f"❌ Impossible de créer le fichier : {e}")

# --- SYSTÈME ROBUSTE DE GESTION DES ARGUMENTS ---
if __name__ == "__main__":
    if len(sys.argv) > 1:
        url_cible = sys.argv[1]
        fichier_sortie = "fallback_error.json"
        id_source = "1"
        
        for arg in sys.argv[2:]:
            arg_clean = arg.strip(' "\'') 
            if arg_clean.lower().endswith(".json"):
                fichier_sortie = arg_clean
            elif arg_clean.isdigit() and len(arg_clean) < 5:
                id_source = arg_clean
                
        extract_blick_full(url_cible, fichier_sortie, id_source)
    else:
        print("❌ Erreur : Nombre d'arguments invalide.")