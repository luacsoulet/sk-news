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
    """Décode le HTML, répare le Mojibake et nettoie les symboles."""
    if not raw_text: return ""
    text = html.unescape(raw_text)
    try:
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    text = text.replace('\xa0', ' ').replace('Â', '')
    text = re.sub(r'<[^>]+>', '', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def extraire_donnees_ctb(html_content, url, source_id):
    """Logique d'extraction spécifique CTB (HTML + Fallback JSON-LD)."""
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

    # --- ÉTAPE 1 : TENTATIVE PAR LE HTML ---
    titre_tag = soup.find('h1', class_='titreType7') or soup.find('h1')
    chapo_tag = soup.find('div', class_='chapo')
    corps_tag = soup.find('div', class_='textArt')

    titre = titre_tag.get_text() if titre_tag else ""
    chapo = chapo_tag.get_text() if chapo_tag else ""
    
    corps_segments = []
    if corps_tag:
        for el in corps_tag.find_all(['p', 'h2']):
            txt = el.get_text().strip()
            if txt:
                prefix = "## " if el.name == 'h2' else ""
                corps_segments.append(prefix + txt)
    
    corps = "\n\n".join(corps_segments)

    # --- ÉTAPE 2 : SÉCURITÉ JSON-LD (Si HTML incomplet) ---
    if not corps or len(corps) < 200:
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string.strip())
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "NewsArticle":
                        if not titre: titre = item.get("headline", "")
                        if not chapo: chapo = item.get("description", "")
                        if not corps: corps = item.get("articleBody", "")
                        
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

    # --- ÉTAPE 3 : DATE COMPLÉMENTAIRE ---
    if not article_data.get("created_at") or "T" not in article_data["created_at"]:
        date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
        if date_tag:
            raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
            try:
                dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
            except: pass

    if soup.find(class_=re.compile(r'paywall|abo-only|premium|lock')):
        article_data["is_paywall"] = True

    # --- ÉTAPE 4 : NETTOYAGE FINAL ---
    article_data["title"] = decrypter_final_anti_bug(titre)
    article_data["description"] = decrypter_final_anti_bug(chapo)
    article_data["content"] = decrypter_final_anti_bug(corps)

    if len(article_data["content"]) > 100:
        article_data["status"] = "success"

    return article_data

# --- 2. LOGIQUE DE NAVIGATION (Performance Maximale) ---

def process_ctb_fast(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Flash CTB : {google_url}")
    
    with sync_playwright() as p:
        # headless=True indispensable pour la vitesse
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(locale="fr-FR", user_agent="Mozilla/5.0...")
        page = context.new_page()

        # OPTIMISATION 1 : Bloquer les images, polices et trackers
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
            resultat = extraire_donnees_ctb(page.content(), normalize_url(page.url), source_id)

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
        process_ctb_fast(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 1)