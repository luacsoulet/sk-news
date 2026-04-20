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

# --- 2. EXTRACTION MULTI-NIVEAUX (Fichier Source) ---

def extraire_donnees_depuis_source(html_content, url, source_id):
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

    # NIVEAU 1 : SCRIPT JSON-LD (Priorité absolue)
    script_json_ld = soup.find('script', id='articleJsonLd') or soup.find('script', type='application/ld+json')
    if script_json_ld and script_json_ld.string:
        try:
            data = json.loads(script_json_ld.string)
            if isinstance(data, list): data = data[0]
            article_data["title"] = nettoyer_texte(data.get("headline", ""))
            article_data["description"] = nettoyer_texte(data.get("description", ""))
            if "articleBody" in data:
                article_data["content"] = nettoyer_texte(data["articleBody"])
            if "datePublished" in data:
                dt = datetime.fromisoformat(data["datePublished"].replace('Z', '+00:00'))
                article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
        except: pass

    # NIVEAU 2 : FUSION METADATA (Spécifique au Moniteur / Usine Nouvelle)
    if not article_data["content"]:
        script_fusion = soup.find('script', id='fusion-metadata')
        if script_fusion and script_fusion.string:
            try:
                match = re.search(r'Fusion\.globalContent\s*=\s*(\{.*?\});\n', script_fusion.string, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    
                    if not article_data["title"] or article_data["title"] == "Titre non trouvé":
                        article_data["title"] = nettoyer_texte(data.get("headlines", {}).get("basic", "Titre non trouvé"))
                    if not article_data["description"]:
                        article_data["description"] = nettoyer_texte(data.get("subheadlines", {}).get("basic", ""))
                        
                    if data.get("content_restrictions", {}).get("content_code") not in ["0", 0, None]:
                        article_data["is_paywall"] = True
                        
                    corps_final = []
                    if article_data["description"]: corps_final.append(article_data["description"])
                    for elem in data.get("content_elements", []):
                        if elem.get("type") == "text": 
                            corps_final.append(nettoyer_texte(elem.get("content", "")))
                        elif elem.get("type") == "header": 
                            corps_final.append(f"## {nettoyer_texte(elem.get('content', ''))}")
                        elif elem.get("type") == "list": # Prise en charge des listes dans le JSON
                            for item in elem.get("items", []):
                                if isinstance(item, dict) and item.get("type") == "text":
                                    corps_final.append(f"- {nettoyer_texte(item.get('content', ''))}")
                    
                    article_data["content"] = "\n\n".join(corps_final)
            except: pass

    # NIVEAU 3 : DOM HTML CLASSIQUE (Le Moniteur, Blick, Swissinfo...)
    if not article_data["content"] or len(article_data["content"]) < 100:
        
        # Titre
        if not article_data["title"] or article_data["title"] == "Titre non trouvé":
            h1 = soup.find('span', class_=re.compile(r'Title__StyledTitle')) or soup.find('h1', class_=re.compile(r'b-headline|entry-title')) or soup.find('h1')
            if h1: article_data["title"] = nettoyer_texte(h1.get_text())
        
        # Description
        if not article_data["description"]:
            desc = soup.find('div', class_=re.compile(r'b-subheadline|lead-text'))
            if desc: article_data["description"] = nettoyer_texte(desc.get_text())

        # Paywall
        if soup.find(class_=re.compile(r'paywall-mark|c-paywall-label|restricted')):
            article_data["is_paywall"] = True

        # Contenu
        corps_final = []
        if article_data["description"]: corps_final.append(article_data["description"])
        
        article_container = soup.find('article', class_=re.compile(r'b-article-body|article-body')) or soup.find('div', class_=re.compile(r'entry-content|article-main|content'))
        
        if article_container:
            # Nettoyage des blocs "À lire aussi" et pollutions
            for read_also in article_container.find_all(attrs={'data-testid': 'read-also'}):
                read_also.decompose()
            for unwanted in article_container.find_all(['iframe', 'script', 'style', 'figure']):
                unwanted.decompose()

            # Extraction séquentielle des P, H2, H3, UL, OL
            for elem in article_container.find_all(['p', 'h2', 'h3', 'ul', 'ol']):
                if elem.name in ['ul', 'ol']:
                    # Pour les listes, on formate chaque puce
                    for li in elem.find_all('li'):
                        txt = nettoyer_texte(li.get_text())
                        if txt:
                            corps_final.append(f"- {txt}")
                else:
                    txt = nettoyer_texte(elem.get_text())
                    if len(txt) > 5 and not txt.startswith('À lire aussi'):
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

def process(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement (Source Directe) : {google_url}")
    
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
                headless=False, # <-- Indispensable pour bypasser DataDome
                args=["--disable-blink-features=AutomationControlled"] 
            ) 
            
            context = browser.new_context(
                locale="fr-FR",
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            print("⏳ Accès à l'URL...")
            # domcontentloaded est suffisant pour capter le fichier source
            page.goto(google_url, wait_until="domcontentloaded", timeout=45000)

            # Bypass Google News
            if "google." in page.url or "consent." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|Accept all|J'accepte|Accepter tout", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).first.click(timeout=3000)
                except: pass

            # Attente de redirection
            start_redir = time.time()
            while time.time() - start_redir < 10:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.5)

            # On laisse la page s'installer dans le DOM
            time.sleep(2)

            # Extraction immédiate depuis le code source
            html_content = page.content()
            resultat = extraire_donnees_depuis_source(html_content, normalize_url(page.url), source_id)
            browser.close()
            
    except Exception as e:
        print(f"💥 Erreur globale : {e}")

    # Sauvegarde
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(resultat, f, ensure_ascii=False, indent=4)
        
        dossier_parent = os.path.dirname(os.path.abspath(output_filename))
        nom_propre = format_filename(resultat["title"])
        fichier_titre = os.path.join(dossier_parent, f"{nom_propre}.json")
        
        with open(fichier_titre, "w", encoding="utf-8") as f2:
            json.dump(resultat, f2, ensure_ascii=False, indent=4)
            
        print("✅ Terminé !")
    except Exception as e:
        print(f"❌ Erreur écriture fichier : {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "fallback.json", sys.argv[3] if len(sys.argv) > 3 else 1)