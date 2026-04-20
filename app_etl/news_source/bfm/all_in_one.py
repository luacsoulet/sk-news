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
    except Exception:
        pass
    return text.replace('Â', '').replace('\xa0', ' ').strip()

def nettoyer_texte(raw_text, est_titre=False):
    """Nettoyage complet du texte et suppression du HTML résiduel."""
    if not raw_text: return ""
    text = reparer_encodage(raw_text)
    text = re.sub(r'<[^>]+>', '', text)
    
    if est_titre:
        return text.strip()
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def extraire_donnees_bfm(html_content, url, source_id):
    """Logique d'extraction spécifique pour BFMTV adaptée Supabase."""
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

    # Nettoyage préventif
    for tag in soup.find_all(['script', 'style', 'iframe']):
        tag.decompose()

    # 1. TITRE
    titre_tag = soup.find('h1', id='contain_title') or soup.find('h1')
    if titre_tag:
        article_data["title"] = nettoyer_texte(titre_tag.get_text(), est_titre=True)

    # 2. RÉSUMÉ (Chapo)
    chapo_tag = soup.find('div', class_='chapo')
    if chapo_tag:
        desc = nettoyer_texte(chapo_tag.get_text())
        article_data["description"] = desc.replace("[CONTENU PARTENAIRE]", "").strip()

    # 3. DATE DE PUBLICATION RÉELLE
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
        except: pass

    # 4. CORPS DE L'ARTICLE
    wrapper = soup.find('div', class_='content_body_wrapper')
    corps_elements = []
    
    if wrapper:
        for elem in wrapper.find_all(['p', 'ul', 'h2', 'h3']):
            txt_brut = elem.get_text().strip()
            if "réalisé avec SCRIBEO" in txt_brut or "La rédaction de" in txt_brut:
                continue

            if elem.name == 'ul':
                for li in elem.find_all('li'):
                    corps_elements.append(f"* {nettoyer_texte(li.get_text(), True)}")
            else:
                txt_propre = nettoyer_texte(txt_brut)
                if txt_propre and len(txt_propre) > 5:
                    prefix = "## " if elem.name in ['h2', 'h3'] else ""
                    corps_elements.append(f"{prefix}{txt_propre}")
    
    article_data["content"] = "\n\n".join(corps_elements)

    # 5. VALIDATION ET PAYWALL
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"

    if soup.find(class_=re.compile(r'premium|paywall|abonnement|login-gate')):
        article_data["is_paywall"] = True

    return article_data

# --- 2. LOGIQUE DE NAVIGATION (Performance Maximale) ---

def process_bfmtv_fast(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Flash BFMTV : {google_url}")
    
    with sync_playwright() as p:
        # headless=True indispensable pour la vitesse
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(locale="fr-FR", user_agent="Mozilla/5.0...")
        page = context.new_page()

        # OPTIMISATION 1 : Bloquer les images et polices (Massif pour BFMTV)
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
            resultat = extraire_donnees_bfm(page.content(), normalize_url(page.url), source_id)

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
        process_bfmtv_fast(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 1)