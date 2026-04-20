# generic_fallback.py - VERSION ULTRA-STABLE
import sys
import time
import json
import re
import os
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from playwright.sync_api import sync_playwright, Error as PlaywrightError

def normalize_url(url):
    """Nettoie l'URL des paramètres de tracking."""
    if not url or "google.com" in url: return url
    u = urlparse(url)
    return urlunparse((u.scheme, u.netloc, u.path, '', '', ''))

def extract_generic(google_url, default_title, source_id, output_file):
    article_data = {
        "title": default_title,
        "description": "",
        "content": None,
        "article_url": google_url,
        "is_paywall": True,
        "news_source_id": int(source_id) if source_id and source_id != "0" else None,
        "created_at": datetime.now().isoformat(),
        "status": "fail"
    }

    with sync_playwright() as p:
        # Passage en headless=False pour voir l'action
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="fr-FR")
        page = context.new_page()
        
        try:
            # 1. Navigation Google News (domcontentloaded pour voir les boutons plus vite)
            page.goto(google_url, wait_until="domcontentloaded", timeout=30000)
            
            # 2. Gestion blindée du consentement Google
            if "google." in page.url:
                try:
                    # Regex élargie pour attraper toutes les variations de boutons
                    regex_consent = re.compile(r"Tout accepter|J'accepte|Accepter tout|Accept all|I agree", re.IGNORECASE)
                    
                    # On attend que le bouton soit cliquable
                    accept_btn = page.get_by_role("button", name=regex_consent)
                    
                    if accept_btn.count() > 0:
                        # On clique sur le premier trouvé sans attendre la suite (no_wait_after)
                        accept_btn.first.click(timeout=5000, no_wait_after=True)
                        print("✅ Google Consent cliqué.")
                except Exception as e:
                    print(f"⚠️ Bouton non cliqué : {e}")

            # 3. Boucle de surveillance de la redirection finale (15 secondes max)
            start_time = time.time()
            while time.time() - start_time < 15:
                if page.is_closed(): break
                curr_url = page.url
                if "google." not in curr_url and "consent." not in curr_url:
                    # Redirection réussie : on attend que la page cible se stabilise
                    time.sleep(4) 
                    article_data["article_url"] = normalize_url(page.url)
                    article_data["status"] = "success"
                    break
                time.sleep(1)

            # 4. EXTRACTION SÉCURISÉE DU CONTENU
            try:
                if not page.is_closed() and article_data["status"] == "success":
                    from bs4 import BeautifulSoup
                    
                    # On attend que le body soit là avant de capturer le HTML
                    page.wait_for_selector("body", timeout=5000)
                    html_content = page.content()
                    
                    soup = BeautifulSoup(html_content, 'html.parser')
                    # Extraction meta-description pour le résumé
                    desc = soup.find('meta', attrs={'name': 'description'}) or \
                           soup.find('meta', attrs={'property': 'og:description'})
                    
                    if desc:
                        article_data["description"] = desc.get('content', '').strip()
            except Exception:
                print("Note: Extraction limitée (page complexe), URL sauvegardée.")

        except Exception as e:
            print(f"Note: Incident durant la navigation : {e}")
        finally:
            if 'browser' in locals():
                try:
                    browser.close()
                except:
                    pass
            
    # Sécurité : Si on est resté bloqué sur Google, on marque l'échec
    if "google." in article_data["article_url"]:
        article_data["status"] = "fail"

    # Sauvegarde du JSON pour app_etl.py
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(article_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    if len(sys.argv) > 4:
        # Args: google_url, title, source_id, output_filename
        extract_generic(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])