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
    """Décode l'HTML et répare les accents Mojibake (ex: Ã© -> é)"""
    if not text: return ""
    text = html.unescape(text)
    try:
        text = text.encode('latin-1').decode('utf-8')
    except: pass
    return text.replace('\xa0', ' ').replace('\u202f', ' ').strip()

def extraire_donnees_sudouest(html_content, url, source_id):
    """Logique d'extraction spécifique Sud Ouest."""
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

    # 1. TITRE ET RÉSUMÉ
    titre_tag = soup.find('h1', class_='page-title') or soup.find('h1')
    article_data["title"] = reparer_encodage(titre_tag.get_text()) if titre_tag else "Titre non trouvé"

    chapo_tag = soup.find('div', id='excerpt-block')
    article_data["description"] = reparer_encodage(chapo_tag.get_text()) if chapo_tag else ""

    # 2. DATE DE PUBLICATION RÉELLE
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
        except: pass

    # 3. CORPS DE L'ARTICLE
    corps_final = []
    zones_contenu = soup.find_all('div', class_='article-article')
    
    if zones_contenu:
        for zone in zones_contenu:
            # Nettoyage des parasites internes
            for parasite in zone.find_all(['div', 'section'], class_=['related-article', 'article-wrapper', 'pub', 'encart']):
                parasite.decompose()

            # Détection Paywall
            if soup.find(class_=re.compile(r'paywall|premium|abonnement|locked')):
                article_data["is_paywall"] = True

            # Extraction paragraphes et titres
            for elem in zone.find_all(['p', 'h2']):
                txt = reparer_encodage(elem.get_text())
                if not txt or len(txt) < 10: continue
                
                if elem.name == 'h2':
                    corps_final.append(f"## {txt}")
                else:
                    corps_final.append(txt)
    
    article_data["content"] = "\n\n".join(corps_final)
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"
        
    return article_data

# --- 2. LOGIQUE DE NAVIGATION (Performance Maximale) ---

def process_sudouest_fast(google_url, output_filename, source_id=1):
    with sync_playwright() as p:
        # Headless=True pour la vitesse
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="fr-FR", user_agent="Mozilla/5.0...")
        page = context.new_page()

        # OPTIMISATION 1 : Bloquer les ressources lourdes (Images, Fonts)
        page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda route: route.abort())

        try:
            # OPTIMISATION 2 : wait_until="commit"
            page.goto(google_url, wait_until="commit", timeout=15000)

            # OPTIMISATION 3 : Bypass Google Flash
            if "google." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|J'accepte", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).click(timeout=2000, no_wait_after=True)
                except: pass

            # OPTIMISATION 4 : Surveillance redirection flash (200ms)
            start_redir = time.time()
            while time.time() - start_redir < 8:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.2)

            # OPTIMISATION 5 : Attendre uniquement l'élément h1
            page.wait_for_selector("h1", timeout=7000)
            
            # Extraction finale
            resultat = extraire_donnees_sudouest(page.content(), normalize_url(page.url), source_id)

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
        process_sudouest_fast(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 1)