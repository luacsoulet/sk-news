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
    text = html.unescape(text)
    try:
        text = text.encode('latin-1').decode('utf-8')
    except: pass
    return text.replace('Â', '').replace('\xa0', ' ').strip()

def decrypter_et_nettoyer(raw_text):
    """Décode les entités HTML, gère l'encodage et structure les titres en Markdown."""
    if not raw_text: return ""
    
    # 1. Décodage et structure (h2 -> ##)
    text = html.unescape(raw_text)
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n\n## \1\n\n', text, flags=re.IGNORECASE)
    
    # 2. Nettoyage balises et Mojibake
    text = re.sub(r'<[^>]+>', '', text)
    text = reparer_encodage(text)
    
    # 3. Normalisation des lignes
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def extraire_donnees_batiweb(html_content, url, source_id):
    """Logique d'extraction spécifique Batiweb optimisée pour Supabase."""
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

    # 1. TITRE
    titre_tag = soup.find('h1', itemprop='headline') or soup.find('h1')
    if titre_tag:
        article_data["title"] = reparer_encodage(titre_tag.get_text())

    # 2. RÉSUMÉ (chapoRaw)
    chapo_tag = soup.find('div', class_='chapoRaw')
    if chapo_tag:
        article_data["description"] = decrypter_et_nettoyer(chapo_tag.get_text())

    # 3. DATE DE PUBLICATION RÉELLE
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
        except: pass

    # 4. CORPS ET PAYWALL
    corps_tag = soup.find('div', class_='contentRaw')
    if corps_tag:
        article_data["content"] = decrypter_et_nettoyer(str(corps_tag))
        if soup.find(class_=re.compile(r'paywall|premium|abonnement|lock')):
            article_data["is_paywall"] = True
    else:
        # Absence de contentRaw = Paywall probable sur Batiweb
        article_data["is_paywall"] = True 

    # Validation du succès
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"

    return article_data

# --- 2. LOGIQUE DE NAVIGATION (Performance Maximale) ---

def process_batiweb_fast(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Flash Batiweb : {google_url}")
    
    with sync_playwright() as p:
        # Headless=True pour la vitesse pure
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(locale="fr-FR", user_agent="Mozilla/5.0...")
        page = context.new_page()

        # OPTIMISATION 1 : Bloquer images, polices et trackers
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
            resultat = extraire_donnees_batiweb(page.content(), normalize_url(page.url), source_id)

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
        process_batiweb_fast(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 1)