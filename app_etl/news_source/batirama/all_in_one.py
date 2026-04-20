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
    """Supprime les paramètres de tracking (?utm...) pour la BDD."""
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

def nettoyer_texte(raw_text):
    """Nettoyage final : Décodage HTML + Encodage + Suppression balises"""
    if not raw_text: return ""
    text = reparer_encodage(raw_text)
    text = re.sub(r'<[^>]+>', '', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def extraire_donnees_batirama(html_content, url, source_id):
    """Logique d'extraction spécifique Batirama (BeautifulSoup)."""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Nettoyage des éléments publicitaires/boutique avant extraction
    for tag in soup.find_all(['div', 'aside'], id=re.compile(r'carouselPubli|^sas_|boutique')):
        tag.decompose()

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
    article_data["title"] = nettoyer_texte(titre_tag.get_text()) if titre_tag else "Titre non trouvé"

    # 2. RÉSUMÉ
    intro_tag = soup.find('span', itemprop='description') or soup.find('meta', attrs={'name': 'description'})
    if intro_tag:
        content = intro_tag.get('content') if intro_tag.name == 'meta' else intro_tag.get_text()
        article_data["description"] = nettoyer_texte(content)

    # 3. DATE DE PUBLICATION RÉELLE
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
        except: pass

    # 4. CORPS DE L'ARTICLE
    corps_elements = []
    article_container = soup.find('div', class_='post-default') or soup.find('div', class_='cell-lg-11')
    
    if article_container:
        # Détection Paywall
        if soup.find(class_=re.compile(r'abo-content|paywall|premium|locked')):
            article_data["is_paywall"] = True
        
        elements = article_container.find_all(['p', 'h2'])
        for el in elements:
            # On ignore les textes trop courts (souvent des légendes ou boutons)
            txt = el.get_text().strip()
            if txt and len(txt) > 20:
                prefix = "## " if el.name == 'h2' else ""
                corps_elements.append(prefix + nettoyer_texte(txt))
    
    article_data["content"] = "\n\n".join(corps_elements)
    
    # Validation du succès
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"

    return article_data

# --- 2. LOGIQUE DE NAVIGATION (Performance Maximale) ---

def process_batirama_fast(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Flash Batirama : {google_url}")
    
    with sync_playwright() as p:
        # headless=True est crucial pour la vitesse
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(locale="fr-FR", user_agent="Mozilla/5.0...")
        page = context.new_page()

        # OPTIMISATION 1 : Bloquer les images et les polices
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
            resultat = extraire_donnees_batirama(page.content(), normalize_url(page.url), source_id)

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
        process_batirama_fast(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 1)