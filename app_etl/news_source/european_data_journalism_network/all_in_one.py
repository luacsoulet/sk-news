import sys
import time
import os
import re
import json
import html
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- 1. FONCTIONS DE NETTOYAGE ET DÉCRYPTAGE ---

def normalize_url(url):
    """Supprime les paramètres de tracking (?utm...)"""
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
    return reparer_encodage(html.unescape(text)).strip()

def structurer_le_corps(text):
    if not text: return ""
    text = re.sub(r'\.\s+["«]([^"»]{5,80})["»]\s+([A-Z])', r'.\n\n## \1\n\n\2', text)
    text = re.sub(r'([\.!\?])\s+([A-Z])', r'\1\n\n\2', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

# --- 2. EXTRACTION SPÉCIFIQUE (European Data Journalism Network) ---

def extraire_donnees_edjnet(html_content, url, source_id):
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

    # 1. Extraction du Titre (h1)
    h1 = soup.find('h1')
    if h1: 
        article_data["title"] = nettoyer_texte(h1.get_text())

    # 2. Extraction de la Description (Classe 'abstract')
    abstract = soup.find('div', class_='abstract')
    if abstract:
        article_data["description"] = nettoyer_texte(abstract.get_text())
    else:
        # Fallback SEO
        desc = soup.find('meta', attrs={'property': 'og:description'})
        if desc: article_data["description"] = nettoyer_texte(desc.get('content', ''))

    # 3. Extraction du Contenu (Classe 'body-source-credits')
    corps_final = []
    body_container = soup.find('div', class_='body-source-credits')
    
    if body_container:
        desc_div = body_container.find('div', class_='description') or body_container
        for p in desc_div.find_all(['p', 'h2', 'h3']):
            txt = nettoyer_texte(p.get_text())
            if not txt or len(txt) < 5: continue
            
            # Mise en forme des sous-titres
            if p.name in ['h2', 'h3']:
                corps_final.append(f"## {txt}")
            else:
                corps_final.append(txt)
                
        article_data["content"] = "\n\n".join(corps_final)
        
    # 4. Extraction de la Date
    meta_date = soup.find('meta', attrs={'property': 'article:published_time'})
    if meta_date:
        try:
            dt = datetime.fromisoformat(meta_date['content'].replace('Z', '+00:00'))
            article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
        except: pass

    # Validation finale
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"
        
    return article_data

# --- 3. LOGIQUE DE NAVIGATION (Playwright Anti-Bot Furtif) ---

def process_edjnet(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Furtif (EDJNet) : {google_url}")
    
    with sync_playwright() as p:
        # ANTI-BOT 1 : Désactiver la détection d'automatisation
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"] 
        ) 
        
        # ANTI-BOT 2 : Headers et User Agent humain
        context = browser.new_context(
            locale="fr-FR",
            timezone_id="Europe/Paris",
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Upgrade-Insecure-Requests": "1"
            }
        )
        page = context.new_page()

        # ANTI-BOT 3 : Masquer la signature "webdriver"
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Bloquer les ressources lourdes
        page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,css,mp4,mp3}", lambda route: route.abort())

        try:
            # Navigation
            page.goto(google_url, wait_until="commit", timeout=30000)

            # Bypass Consentement éventuel (Google ou Cookie Banner)
            if "google." in page.url or "consent." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|J'accepte|Accept", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).first.click(timeout=2000, no_wait_after=True)
                except: pass

            # Attente de la redirection
            start_redir = time.time()
            while time.time() - start_redir < 8:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.2)

            # Sécurité : attente de la balise principale
            try:
                page.wait_for_selector("h1, .body-source-credits", timeout=10000)
            except:
                time.sleep(2)
            
            # Extraction finale
            resultat = extraire_donnees_edjnet(page.content(), normalize_url(page.url), source_id)

        except Exception as e:
            resultat = {
                "title": "Erreur de chargement / Bloqué par sécurité",
                "description": "",
                "content": str(e),
                "article_url": google_url,
                "is_paywall": False,
                "news_source_id": int(source_id),
                "created_at": datetime.now().isoformat(),
                "status": "fail"
            }
        finally:
            browser.close()

    # --- 4. SAUVEGARDE INTELLIGENTE ---
    print(f"💾 Écriture des données dans : {output_filename}")
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(resultat, f, ensure_ascii=False, indent=4)
        print("✅ Fichier JSON créé avec succès !")
    except Exception as e:
        print(f"❌ Impossible de créer le fichier : {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
        output_file = "fallback_error.json"
        source_id = "1"
        
        # Détection robuste des arguments envoyés par le script processor.py
        for arg in sys.argv[2:]:
            arg_clean = arg.strip(' "\'') 
            if arg_clean.lower().endswith(".json"):
                output_file = arg_clean
            elif arg_clean.isdigit() and len(arg_clean) < 5:
                source_id = arg_clean
                
        process_edjnet(url, output_file, source_id)
    else:
        print("❌ Erreur : Nombre d'arguments invalide.")