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

def nettoyer_texte(text):
    if not text: return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text) # Nettoie le HTML résiduel
    text = re.sub(r'\s+', ' ', text)
    return reparer_encodage(text).strip()

def format_filename(title):
    if not title or title == "Titre non trouvé":
        return f"article_sans_titre_{int(time.time())}"
    t = ''.join(c for c in unicodedata.normalize('NFD', title.lower()) if unicodedata.category(c) != 'Mn')
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    return t[:100]

# --- 2. EXTRACTION SPÉCIFIQUE (Quidam Hebdo) ---

def extraire_donnees_quidam(html_content, url, source_id):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    article_data = {
        "title": "Titre non trouvé",
        "description": "",
        "content": "",
        "article_url": url,
        "is_paywall": False,
        "news_source_id": int(source_id),
        "created_at": datetime.now().isoformat(),
        "status": "fail"
    }

    # 1. Extraction SEO prioritaire (Yoast JSON-LD)
    script_json_ld = soup.find('script', class_='yoast-schema-graph')
    if script_json_ld and script_json_ld.string:
        try:
            data = json.loads(script_json_ld.string)
            if "@graph" in data:
                for item in data["@graph"]:
                    if item.get("@type") == "Article":
                        article_data["title"] = nettoyer_texte(item.get("headline", ""))
                        raw_date = item.get("datePublished")
                        if raw_date:
                            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                            article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
        except: pass

    # 2. Extraction du Titre (Fallback)
    if article_data["title"] == "Titre non trouvé":
        h1 = soup.find('h1', class_='single_post_title_main') or soup.find('h1')
        if h1: article_data["title"] = nettoyer_texte(h1.get_text())

    # 3. Extraction du Sous-titre / Chapeau
    desc = soup.find('p', class_='post_subtitle_text')
    if desc:
        article_data["description"] = nettoyer_texte(desc.get_text())

    # 4. Extraction du Contenu Principal
    corps_final = []
    
    # On cible la div spécifique qui contient l'article complet
    content_div = soup.find('div', class_=re.compile(r'post_content.*jl_content'))
    
    if content_div:
        # NETTOYAGE : Suppression des encarts publicitaires (ex: Prévifrance)
        for pub in content_div.find_all('div', class_=re.compile(r'code-block')):
            pub.decompose()
            
        # Extraction séquentielle
        for elem in content_div.find_all(['p', 'h2', 'h3', 'ul', 'ol']):
            if elem.name in ['ul', 'ol']:
                for li in elem.find_all('li'):
                    txt = nettoyer_texte(li.get_text())
                    if txt: corps_final.append(f"- {txt}")
            else:
                txt = nettoyer_texte(elem.get_text())
                if len(txt) > 5:
                    if elem.name in ['h2', 'h3'] or elem.find('strong', recursive=False):
                        corps_final.append(f"## {txt}")
                    else:
                        corps_final.append(txt)

    # Nettoyage des doublons éventuels
    corps_final_sans_doublons = list(dict.fromkeys(corps_final))
    article_data["content"] = "\n\n".join(corps_final_sans_doublons)

    # Validation
    if len(article_data["content"]) > 50:
        article_data["status"] = "success"
        
    return article_data

# --- 3. LOGIQUE DE NAVIGATION ---

def process_quidam(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement (Quidam Hebdo) : {google_url}")
    
    resultat = {
        "title": "Crash",
        "description": "",
        "content": "Erreur lors du chargement de la page.",
        "article_url": google_url,
        "is_paywall": False,
        "news_source_id": int(source_id),
        "created_at": datetime.now().isoformat(),
        "status": "fail"
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False, # Mettre sur True si tu ne veux pas voir le navigateur s'ouvrir
                args=["--disable-blink-features=AutomationControlled"] 
            ) 
            
            context = browser.new_context(
                locale="fr-FR",
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            print("⏳ Accès à l'URL...")
            # On attend que la page soit "load" (complètement chargée)
            page.goto(google_url, wait_until="load", timeout=60000)

            # Bypass Google News consent
            if "google." in page.url or "consent." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|Accept all|J'accepte|Accepter tout", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).first.click(timeout=3000)
                except: pass

            # Attente de la redirection depuis Google
            start_redir = time.time()
            while time.time() - start_redir < 10:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.5)

            # 🛑 FORCE L'ATTENTE DE L'AFFICHAGE DE L'ARTICLE
            print("👁️ Attente de l'affichage de l'article à l'écran...")
            try:
                # On attend que la div contenant le texte ou le titre H1 devienne "visible"
                page.wait_for_selector(".jl_content, h1.single_post_title_main", state="visible", timeout=15000)
                time.sleep(2) # Petite pause pour laisser les animations se terminer
            except Exception:
                print("⚠️ Temps d'attente expiré, on tente d'extraire quand même...")
                time.sleep(3) # Pause de secours

            # Extraction
            html_content = page.content()
            resultat = extraire_donnees_quidam(html_content, normalize_url(page.url), source_id)
            browser.close()
            
    except Exception as e:
        print(f"💥 Erreur globale détectée : {e}")

    # --- SAUVEGARDE GARANTIE ---
    print(f"💾 Écriture des données dans : {output_filename}")
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(resultat, f, ensure_ascii=False, indent=4)
        
        dossier_parent = os.path.dirname(os.path.abspath(output_filename))
        nom_propre = format_filename(resultat["title"])
        fichier_titre = os.path.join(dossier_parent, f"{nom_propre}.json")
        
        with open(fichier_titre, "w", encoding="utf-8") as f2:
            json.dump(resultat, f2, ensure_ascii=False, indent=4)
            
        print(f"✅ Fichiers JSON créés avec succès !")
    except Exception as e:
        print(f"❌ Impossible de créer le fichier : {e}")

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
                
        process_quidam(url_cible, fichier_sortie, id_source)
    else:
        print("❌ Erreur : Nombre d'arguments invalide.")