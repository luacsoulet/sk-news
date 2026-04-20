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

# --- 1. FONCTIONS DE NETTOYAGE ET D'EXTRACTION ---

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

def nettoyer_texte(raw_text):
    """Décode l'HTML, répare l'encodage et normalise les espaces."""
    if not raw_text: return ""
    text = html.unescape(raw_text)
    text = reparer_encodage(text)
    # Suppression des caractères de contrôle invisibles
    text = "".join(ch for ch in text if ord(ch) >= 32 or ch in "\n\r")
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def extraire_donnees_20min(html_content, url, source_id):
    """Logique d'extraction spécifique 20 Minutes (JSON-LD + Fallback HTML)."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    article_data = {
        "title": "Titre inconnu",
        "description": "",
        "content": "",
        "article_url": url,
        "is_paywall": False,
        "news_source_id": int(source_id),
        "created_at": datetime.now().isoformat(),
        "status": "fail"
    }

    # --- ÉTAPE 1 : JSON-LD (Source la plus rapide et fiable) ---
    scripts = soup.find_all('script', type='application/ld+json')
    corps_json = ""
    for script in scripts:
        try:
            raw_data = json.loads(script.string.strip())
            items = raw_data if isinstance(raw_data, list) else [raw_data]
            for item in items:
                if item.get("@type") == "NewsArticle":
                    article_data["title"] = nettoyer_texte(item.get("headline", ""))
                    article_data["description"] = nettoyer_texte(item.get("description", ""))
                    if item.get("isAccessibleForFree") is False:
                        article_data["is_paywall"] = True
                    
                    date_raw = item.get("datePublished") or item.get("dateCreated")
                    if date_raw:
                        try:
                            dt = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
                            article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
                        except: pass
                    corps_json = item.get("articleBody", "")
                    break
        except: continue

    # --- ÉTAPE 2 : CORPS (Priorité HTML si paragraphs détectés, sinon JSON) ---
    paragraphes_html = soup.find_all('p', class_=re.compile(r'iaMroo|article-content'))
    if paragraphes_html:
        corps_liste = [p.get_text().strip() for p in paragraphes_html if len(p.get_text()) > 25]
        article_data["content"] = nettoyer_texte("\n\n".join(corps_liste))
    
    # Fallback sur le corps du JSON si l'HTML est pauvre
    if (not article_data["content"] or len(article_data["content"]) < 200) and corps_json:
        article_data["content"] = nettoyer_texte(corps_json)

    # Validation
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"

    return article_data

# --- 2. LOGIQUE DE NAVIGATION (Performance Maximale) ---

def process_20min_fast(google_url, output_filename, source_id=12):
    print(f"🚀 Lancement Flash 20 Minutes : {google_url}")
    
    with sync_playwright() as p:
        # Headless=True indispensable pour la vitesse
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(locale="fr-FR", user_agent="Mozilla/5.0...")
        page = context.new_page()

        # OPTIMISATION 1 : Bloquer les images et polices (Massif pour 20min qui est très lourd)
        page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda route: route.abort())

        try:
            # OPTIMISATION 2 : wait_until="commit" (navigation flash)
            page.goto(google_url, wait_until="commit", timeout=15000)

            # OPTIMISATION 3 : Bypass Google Consent Flash
            if "google." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|J'accepte", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).click(timeout=2000, no_wait_after=True)
                except: pass

            # OPTIMISATION 4 : Boucle de redirection flash (200ms)
            start_redir = time.time()
            while time.time() - start_redir < 8:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.2)

            # OPTIMISATION 5 : Attendre uniquement le titre H1
            page.wait_for_selector("h1", timeout=7000)
            
            # Extraction finale
            resultat = extraire_donnees_20min(page.content(), normalize_url(page.url), source_id)

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
        # Args: google_url, output_filename, source_id
        process_20min_fast(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 12)