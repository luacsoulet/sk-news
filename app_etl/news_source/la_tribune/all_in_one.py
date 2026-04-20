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
    """Répare les problèmes d'affichage Mojibake (confusion UTF-8/Latin-1)"""
    if not text: return ""
    text = html.unescape(text)
    try:
        text = text.encode('latin-1').decode('utf-8')
    except: pass
    return text.replace('Â', '').replace('\xa0', ' ')

def nettoyer_texte_enrichi(raw_text):
    """Transforme les balises HTML en Markdown et nettoie le texte."""
    if not raw_text: return ""
    text = html.unescape(raw_text)
    text = reparer_encodage(text)
    
    # Formatage des titres en Markdown
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n\n## \1\n\n', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n\n### \1\n\n', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Suppression des balises restantes et normalisation
    text = re.sub(r'<[^>]+>', '', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def extraire_donnees_latribune(html_content, url, source_id):
    """Logique d'extraction spécifique La Tribune pour Supabase."""
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

    # 1. MÉTADONNÉES (JSON-LD)
    json_ld_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html_content, re.DOTALL)
    for block in json_ld_blocks:
        try:
            data = json.loads(block.strip())
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "NewsArticle":
                    article_data["title"] = item.get("headline", "").upper()
                    article_data["description"] = item.get("description", "")
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

    # 2. CORPS ENRICHI (Regex Segments Next.js)
    body_segments = []
    # Recherche des champs \"html\":\"...\" dans le JSON interne de La Tribune
    pattern_html = r'\\"html\\":\\"(.*?)\\"'
    segments = re.findall(pattern_html, html_content)
    
    for seg in segments:
        # Nettoyage des escapes unicode de Next.js
        clean_seg = seg.replace('\\u003c', '<').replace('\\u003e', '>').replace('\\u0026', '&').replace('\\"', '"')
        body_segments.append(clean_seg)

    corps_final = "\n\n".join([nettoyer_texte_enrichi(p) for p in body_segments])
    
    # Fallback BeautifulSoup si Next.js échoue
    if not corps_final or len(corps_final) < 200:
        soup = BeautifulSoup(html_content, 'html.parser')
        article_div = soup.find('div', class_='article-body') or soup.find('div', class_='content')
        if article_div:
            corps_final = nettoyer_texte_enrichi(article_div.get_text())

    article_data["content"] = corps_final
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"
        
    return article_data

# --- 2. LOGIQUE DE NAVIGATION (Performance Maximale) ---

def process_latribune_fast(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Flash La Tribune : {google_url}")
    
    with sync_playwright() as p:
        # Headless=True indispensable pour la vitesse
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(locale="fr-FR", user_agent="Mozilla/5.0...")
        page = context.new_page()

        # OPTIMISATION 1 : Bloquer les ressources lourdes (Images, Fonts, Pubs)
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
            resultat = extraire_donnees_latribune(page.content(), normalize_url(page.url), source_id)

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
        process_latribune_fast(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 1)