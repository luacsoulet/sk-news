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

def nettoyer_texte(raw_text):
    """Nettoyage complet du texte et suppression du HTML résiduel."""
    if not raw_text: return ""
    text = reparer_encodage(raw_text)
    text = re.sub(r'<[^>]+>', '', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def extraire_donnees_agefi(html_content, url, source_id):
    """Logique d'extraction spécifique Agefi (Structure non-paywall / articleParagraph)."""
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
    titre_tag = soup.find('h1') or soup.find('title')
    if titre_tag:
        article_data["title"] = nettoyer_texte(titre_tag.get_text().split(' | Agefi')[0])

    # 2. RÉSUMÉ
    desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    if desc_tag:
        article_data["description"] = nettoyer_texte(desc_tag.get('content', ''))

    # 3. DATE DE PUBLICATION RÉELLE
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
        except: pass

    # 4. CORPS ET DÉTECTION PAYWALL
    # L'Agefi utilise souvent 'non-paywall' pour la partie gratuite
    zone_contenu = soup.find('div', class_='non-paywall')
    
    if not zone_contenu or soup.find(class_=re.compile(r'paywall|premium|restricted')):
        article_data["is_paywall"] = True

    corps_elements = []
    # Tentative sur la zone gratuite
    if zone_contenu:
        for p in zone_contenu.find_all(['p', 'h2']):
            txt = p.get_text().strip()
            if len(txt) > 5:
                prefix = "## " if p.name == 'h2' else ""
                corps_elements.append(prefix + nettoyer_texte(txt))
    
    # Si vide, on tente le fallback par classe de paragraphe
    if not corps_elements:
        for p in soup.find_all('p', class_=re.compile(r'articleParagraph')):
            txt = p.get_text().strip()
            if len(txt) > 20:
                corps_elements.append(nettoyer_texte(txt))

    article_data["content"] = "\n\n".join(corps_elements)
    
    # 5. VALIDATION DU SUCCÈS
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"

    return article_data

# --- 2. LOGIQUE DE NAVIGATION (Performance Maximale) ---

def process_agefi_fast(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Flash Agefi : {google_url}")
    
    with sync_playwright() as p:
        # Headless=True indispensable pour la vitesse
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(locale="fr-FR", user_agent="Mozilla/5.0...")
        page = context.new_page()

        # OPTIMISATION 1 : Bloquer les images, polices et trackers (Massif pour les sites financiers)
        page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda route: route.abort())

        try:
            # OPTIMISATION 2 : wait_until="commit" (navigation flash)
            page.goto(google_url, wait_until="commit", timeout=15000)

            # OPTIMISATION 3 : Bypass Google Consent Flash
            if "google." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|J'accepte|Accepter tout", re.IGNORECASE)
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
            resultat = extraire_donnees_agefi(page.content(), normalize_url(page.url), source_id)

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
        process_agefi_fast(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 1)