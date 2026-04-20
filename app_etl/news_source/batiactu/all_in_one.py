import sys
import time
import os
import re
import json
import html
import random
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

# --- 2. EXTRACTION MULTI-NIVEAUX (Batiactu) ---

def extraire_donnees_batiactu(html_content, url, source_id):
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

    # NIVEAU 1 : SCRIPT JSON-LD (La mine d'or absolue pour Batiactu)
    scripts_json = soup.find_all('script', id='articleJsonLd') or soup.find_all('script', type='application/ld+json')
    
    for script in scripts_json:
        if script.string:
            try:
                data = json.loads(script.string)
                # Le JSON-LD de Batiactu est souvent une liste d'objets
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "NewsArticle":
                            article_data["title"] = nettoyer_texte(item.get("headline", ""))
                            article_data["description"] = nettoyer_texte(item.get("description", ""))
                            if "articleBody" in item:
                                # Le texte contient des espaces et parfois du HTML encodé, on le nettoie et on génère les paragraphes
                                texte_brut = item["articleBody"]
                                texte_propre = re.sub(r'(?:\s*&\#160;\s*)+', '\n\n', texte_brut) # Batiactu utilise souvent &#160; comme séparateur
                                
                                segments = [nettoyer_texte(p) for p in texte_propre.split('\n') if len(nettoyer_texte(p)) > 10]
                                article_data["content"] = "\n\n".join(segments)
                                
                            raw_date = item.get("datePublished")
                            if raw_date:
                                dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                                article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
                            break
            except: pass

    # NIVEAU 2 : DOM HTML CLASSIQUE (Fallback si le JSON-LD échoue)
    if not article_data["content"] or len(article_data["content"]) < 100:
        
        # Titre
        if not article_data["title"] or article_data["title"] == "Titre non trouvé":
            h1 = soup.find('h1', class_=re.compile(r'speakable-title')) or soup.find('h1')
            if h1: article_data["title"] = nettoyer_texte(h1.get_text())

        # Description
        if not article_data["description"]:
            desc = soup.find('div', class_='top-chapeau')
            if desc: article_data["description"] = nettoyer_texte(desc.get_text())

        # Date
        if article_data["created_at"] == datetime.now().isoformat():
            date_meta = soup.find('meta', attrs={'property': 'article:published_time'})
            if date_meta:
                try:
                    dt = datetime.fromisoformat(date_meta['content'].replace('Z', '+00:00'))
                    article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
                except: pass

        # Contenu
        corps_final = []
        if article_data["description"]: 
            corps_final.append(article_data["description"])
            
        text_container = soup.find('div', class_='text') or soup.find('div', class_='article-text')
        
        if text_container:
            # On supprime les blocs "À lire aussi" et la publicité
            for encart in text_container.find_all('div', class_=re.compile(r'regroupe-edito|smartphoneonly')):
                encart.decompose()
            for unwanted in text_container.find_all(['iframe', 'script', 'style']):
                unwanted.decompose()

            # Extraction séquentielle
            for elem in text_container.find_all(['p', 'h2', 'h3', 'div']):
                # Eviter d'extraire les div enfants s'ils ont déjà été traités dans la boucle (protection basique)
                if elem.name == 'div' and 'speakable-text' not in elem.get('class', []):
                    continue
                    
                txt = nettoyer_texte(elem.get_text())
                if len(txt) > 5 and not txt.startswith('À lire aussi'):
                    if elem.name in ['h2', 'h3'] or elem.find('strong', recursive=False):
                        corps_final.append(f"## {txt}")
                    else:
                        corps_final.append(txt)

        article_data["content"] = "\n\n".join(list(dict.fromkeys(corps_final)))

    # Détection de Paywall (Souvent visible dans l'URL, les metas, ou le bloc .free-nonconnected)
    if soup.find(class_='free-nonconnected') or soup.find(class_='picto-locked'):
        article_data["is_paywall"] = True

    # Validation
    if len(article_data["content"]) > 50:
        article_data["status"] = "success"
        
    return article_data

# --- 3. LOGIQUE DE NAVIGATION HUMAINE ---

def process_batiactu(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Navigation Humaine (Batiactu) : {google_url}")
    
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
                headless=False,
                args=["--disable-blink-features=AutomationControlled"] 
            ) 
            
            context = browser.new_context(
                locale="fr-FR",
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            print("⏳ Accès à l'URL...")
            page.goto(google_url, wait_until="domcontentloaded", timeout=60000)

            # Pause aléatoire (humaine)
            time.sleep(random.uniform(1.5, 3.0))

            # Bypass Consentement Google
            if "google." in page.url or "consent." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|Accept all|J'accepte|Accepter tout", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).first.click(timeout=3000)
                    time.sleep(random.uniform(1.5, 2.5)) 
                except: pass

            # Attente de la redirection vers Batiactu
            start_redir = time.time()
            while time.time() - start_redir < 10:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.5)

            # 🤖 Émulation du comportement humain pour éviter le blocage
            print("🚶 Simulation de comportement humain en cours...")
            time.sleep(random.uniform(1.0, 2.0))
            
            try:
                page.mouse.move(random.randint(300, 800), random.randint(200, 600))
                time.sleep(random.uniform(0.5, 1.0))
            except: pass

            # Bandeau Didomi / Cookie Bot (très courant sur Batiactu)
            try:
                page.locator("#didomi-notice-agree-button").click(timeout=2000)
                time.sleep(1)
            except: pass

            # Défilement lent pour déclencher le chargement des scripts/images
            for _ in range(3):
                try:
                    page.mouse.wheel(0, random.randint(250, 500))
                    time.sleep(random.uniform(1.0, 2.5))
                except: pass

            # Attente de l'apparition des éléments clés
            try:
                page.wait_for_selector(".text, h1, #articleJsonLd", timeout=8000)
            except Exception:
                print("⚠️ Temps d'attente pour les balises écoulé.")

            # Extraction
            html_content = page.content()
            resultat = extraire_donnees_batiactu(html_content, normalize_url(page.url), source_id)
            browser.close()
            
    except Exception as e:
        print(f"💥 Erreur globale : {e}")

    # --- SAUVEGARDE ---
    print(f"💾 Écriture des données dans : {output_filename}")
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(resultat, f, ensure_ascii=False, indent=4)
        
        dossier_parent = os.path.dirname(os.path.abspath(output_filename))
        nom_propre = format_filename(resultat["title"])
        fichier_titre = os.path.join(dossier_parent, f"{nom_propre}.json")
        
        with open(fichier_titre, "w", encoding="utf-8") as f2:
            json.dump(resultat, f2, ensure_ascii=False, indent=4)
            
        print("✅ Fichiers JSON créés avec succès !")
    except Exception as e:
        print(f"❌ Erreur écriture fichier : {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_batiactu(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "fallback.json", sys.argv[3] if len(sys.argv) > 3 else 1)