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

# --- 2. EXTRACTION CHIRURGICALE (France 3 Régions) ---

def extraire_donnees_france3(html_content, url, source_id):
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

    # 1. Extraction SEO prioritaire (JSON-LD)
    scripts_json_ld = soup.find_all('script', type='application/ld+json')
    for script in scripts_json_ld:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, list): data = data[0]
                if data.get("@type") in ["NewsArticle", "Article"]:
                    article_data["title"] = nettoyer_texte(data.get("headline", ""))
                    article_data["description"] = nettoyer_texte(data.get("description", ""))
                    raw_date = data.get("datePublished")
                    if raw_date:
                        dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                        article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
            except: pass

    # 2. Fallback Titre & Description via HTML
    if article_data["title"] == "Titre non trouvé":
        h1 = soup.find('h1')
        if h1: article_data["title"] = nettoyer_texte(h1.get_text())

    if not article_data["description"]:
        intro = soup.find('p', class_=re.compile(r'article__intro'))
        if intro: article_data["description"] = nettoyer_texte(intro.get_text())

    # 3. Extraction du Contenu Principal
    corps_final = []
    
    # On ajoute l'intro au début pour la cohérence
    if article_data["description"]:
        corps_final.append(article_data["description"])
        
    article_body = soup.find('div', class_='article__body')
    
    if article_body:
        # NETTOYAGE EXTRÊME : On détruit toutes les pollutions (Newsletter, Boutons, Vidéos)
        classes_a_detruire = [
            'optin-newsletter', 'optin-newsletter-main', 'optin-newsletter-mobile-bottom',
            'article-video__container', 'jt-card-container', 'article-share--alt',
            'scroll-tracker', 'mediavideo'
        ]
        for unwanted in article_body.find_all(['div', 'ul', 'form'], class_=re.compile('|'.join(classes_a_detruire))):
            unwanted.decompose()
        for iframe in article_body.find_all(['iframe', 'script', 'style']):
            iframe.decompose()

        # FORMATAGE MARKDOWN
        # France 3 n'utilise pas toujours de <p>. Le texte est souvent séparé par des <br>
        for br in article_body.find_all('br'):
            br.replace_with('\n')
            
        for h in article_body.find_all(['h2', 'h3', 'h4', 'h5']):
            h.replace_with(f"\n\n## {nettoyer_texte(h.get_text())}\n\n")
            
        for ul in article_body.find_all(['ul', 'ol']):
            list_text = ""
            for li in ul.find_all('li'):
                txt_li = nettoyer_texte(li.get_text())
                if txt_li: list_text += f"- {txt_li}\n"
            ul.replace_with(f"\n\n{list_text}\n\n")

        # Extraction du texte final ligne par ligne
        raw_text = article_body.get_text(separator='\n')
        
        for ligne in raw_text.split('\n'):
            ligne_propre = nettoyer_texte(ligne)
            # On vérifie que la ligne n'est pas déjà dans l'intro pour éviter les doublons
            if len(ligne_propre) > 5 and ligne_propre not in article_data["description"]:
                corps_final.append(ligne_propre)

    # Nettoyage des doublons
    corps_final_sans_doublons = list(dict.fromkeys(corps_final))
    article_data["content"] = "\n\n".join(corps_final_sans_doublons)

    # Validation
    if len(article_data["content"]) > 50:
        article_data["status"] = "success"
        
    return article_data

# --- 3. LOGIQUE DE NAVIGATION ---

def process_france3(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement (France 3 Régions) : {google_url}")
    
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
            # Headless=False en cas de protection ou pour le débug
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
            page.goto(google_url, wait_until="domcontentloaded", timeout=45000)

            # Bypass Google News
            if "google." in page.url or "consent." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|Accept all|J'accepte|Accepter tout", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).first.click(timeout=3000)
                except: pass

            # Attente de la redirection
            start_redir = time.time()
            while time.time() - start_redir < 10:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.5)

            # 🤖 Émulation humaine
            print("🚶 Simulation de lecture en cours...")
            time.sleep(random.uniform(1.0, 2.0))
            
            try:
                page.mouse.move(random.randint(300, 800), random.randint(200, 600))
            except: pass

            for _ in range(3):
                try:
                    page.mouse.wheel(0, random.randint(250, 500))
                    time.sleep(random.uniform(1.0, 2.0))
                except: pass

            # On attend la présence du conteneur de texte
            try:
                page.wait_for_selector(".article__body, h1", timeout=8000)
            except Exception:
                print("⚠️ Temps d'attente pour les balises écoulé.")

            # Extraction
            html_content = page.content()
            resultat = extraire_donnees_france3(html_content, normalize_url(page.url), source_id)
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
            
        print("✅ Fichiers JSON créés avec succès !")
    except Exception as e:
        print(f"❌ Erreur écriture fichier : {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_france3(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "fallback.json", sys.argv[3] if len(sys.argv) > 3 else 1)