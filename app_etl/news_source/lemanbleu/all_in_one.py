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

def decrypter_final_anti_bug(raw_text):
    """Décode le HTML, répare le Mojibake et structure le Markdown."""
    if not raw_text: return ""
    
    # 1. Décodage des entités HTML
    text = html.unescape(raw_text)
    
    # 2. Réparation du Mojibake
    try:
        text = text.encode('latin-1').decode('utf-8')
    except: pass
    
    text = text.replace('\xa0', ' ').replace('Â', '')
    
    # 3. Structure : Transformation des balises spécifiques Léman Bleu
    text = re.sub(r'<p class=[\'"]wysiwyg-h2[\'"]>(.*?)</p>', r'\n\n## \1\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text, flags=re.IGNORECASE)
    
    # 4. Nettoyage final des balises HTML
    text = re.sub(r'<[^>]+>', '', text)
    
    # 5. Normalisation des lignes
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def extraire_donnees_lemanbleu(html_content, url, source_id):
    """Analyse le HTML de Léman Bleu et prépare le dictionnaire final pour Supabase."""
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
    titre_tag = soup.find('h1', class_='pageTitle') or soup.find('h1')
    if titre_tag:
        article_data["title"] = decrypter_final_anti_bug(titre_tag.get_text())
    
    # 2. RÉSUMÉ
    desc_meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
    if desc_meta:
        article_data["description"] = decrypter_final_anti_bug(desc_meta.get('content', ''))

    # 3. DATE DE PUBLICATION RÉELLE
    date_tag = soup.find('meta', property='article:published_time') or soup.find('time')
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
        except: pass

    # 4. CORPS DE L'ARTICLE
    corps_html_list = []
    container = soup.find('div', class_='EZ_InternalPlaceHolder')
    
    if container:
        blocs = container.find_all('div', class_='BlocText')
        for bloc in blocs:
            if bloc.find('p', class_='photoLegend'): continue
            corps_html_list.append(str(bloc))
    else:
        alternative = soup.find('article') or soup.find('div', class_='article-content')
        if alternative:
            corps_html_list.append(str(alternative))

    article_data["content"] = "\n\n".join([decrypter_final_anti_bug(b) for b in corps_html_list])

    # 5. STATUS ET PAYWALL
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"
    
    if soup.find(class_=re.compile(r'paywall|premium|abonnement|restricted')):
        article_data["is_paywall"] = True

    return article_data

# --- 2. LOGIQUE DE NAVIGATION (Performance Maximale) ---

def process_lemanbleu_fast(google_url, output_filename, source_id=1):
    with sync_playwright() as p:
        # headless=True pour la vitesse
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(locale="fr-FR", user_agent="Mozilla/5.0...")
        page = context.new_page()

        # OPTIMISATION 1 : Bloquer les images et polices (Massif pour Léman Bleu)
        page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda route: route.abort())

        try:
            # OPTIMISATION 2 : wait_until="commit" (navigation flash)
            page.goto(google_url, wait_until="commit", timeout=15000)

            # OPTIMISATION 3 : Bypass Google Flash
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

            # OPTIMISATION 5 : Attendre uniquement le titre
            page.wait_for_selector("h1", timeout=7000)
            
            # Pause minime pour le JS de Léman Bleu (EZ_InternalPlaceHolder)
            time.sleep(1.5)
            
            # Extraction finale
            resultat = extraire_donnees_lemanbleu(page.content(), normalize_url(page.url), source_id)

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
        process_lemanbleu_fast(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 1)