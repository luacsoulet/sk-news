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
    """Répare les problèmes d'affichage Mojibake (ex: Ã© -> é)"""
    if not text: return ""
    try:
        text = text.encode('latin-1').decode('utf-8')
    except: pass
    return text.replace('Â', '').replace('\xa0', ' ').strip()

def nettoyer_fragment(raw_text):
    """Nettoie le texte (HTML unescape + strip tags)"""
    if not raw_text: return ""
    text = html.unescape(raw_text)
    text = reparer_encodage(text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def extraire_donnees_watson(html_content, url, source_id):
    """Logique d'extraction spécifique pour Watson."""
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

    # --- ÉTAPE 1 : MÉTADONNÉES (JSON-LD) ---
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            data = json.loads(script.string.strip())
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "NewsArticle":
                    article_data["title"] = nettoyer_fragment(item.get("headline", ""))
                    article_data["description"] = nettoyer_fragment(item.get("description", ""))
                    date_raw = item.get("datePublished")
                    if date_raw:
                        try:
                            dt = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
                            article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
                        except: pass
                    if item.get("isAccessibleForFree") is False:
                        article_data["is_paywall"] = True
                    break
        except: continue

    # Fallback Titre
    if article_data["title"] == "Titre non trouvé":
        t_tag = soup.find('meta', property='og:title')
        article_data["title"] = nettoyer_fragment(t_tag['content']) if t_tag else "Titre non trouvé"

    # --- ÉTAPE 2 : CORPS DE L'ARTICLE ---
    corps_final = []
    article_body = soup.find('article', class_='watson-story__content')
    if article_body:
        for elem in article_body.find_all(['p', 'h2', 'h3'], recursive=True):
            if elem.find_parent(['aside', 'div'], class_=['MoreAbout__MoreAboutWrapper', 'insert']):
                continue
            txt = nettoyer_fragment(elem.get_text())
            if not txt or len(txt) < 5: continue
            
            if elem.name in ['h2', 'h3']:
                corps_final.append(f"## {txt}")
            else:
                if re.match(r'^\(.*\)$', txt) and len(txt) < 15: continue
                corps_final.append(txt)
    
    article_data["content"] = "\n\n".join(corps_final)
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"
        
    return article_data

# --- 2. LOGIQUE DE NAVIGATION (Performance Maximale) ---

def process_watson_fast(google_url, output_filename, source_id=1):
    with sync_playwright() as p:
        # headless=True indispensable pour la vitesse
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="fr-FR", user_agent="Mozilla/5.0...")
        page = context.new_page()

        # OPTIMISATION 1 : Bloquer les images, polices et pubs
        page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda route: route.abort())

        try:
            # OPTIMISATION 2 : wait_until="commit" (n'attend pas le chargement total)
            page.goto(google_url, wait_until="commit", timeout=15000)

            # OPTIMISATION 3 : Bypass Google Flash
            if "google." in page.url:
                try:
                    page.get_by_role("button", name=re.compile(r"Tout accepter|J'accepte", re.IGNORECASE)).click(timeout=2000, no_wait_after=True)
                except: pass

            # OPTIMISATION 4 : Boucle de redirection flash (200ms)
            start_redir = time.time()
            while time.time() - start_redir < 8:
                if "google." not in page.url: break
                time.sleep(0.2)

            # OPTIMISATION 5 : Attendre uniquement le titre
            page.wait_for_selector("h1", timeout=7000)
            
            # Extraction finale
            resultat = extraire_donnees_watson(page.content(), normalize_url(page.url), source_id)

        except Exception as e:
            resultat = {
                "title": "Erreur de chargement",
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

    # Sauvegarde JSON compatible Supabase
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    if len(sys.argv) > 2:
        process_watson_fast(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 1)