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
    if not url or "google." in url: return url
    u = urlparse(url)
    return urlunparse((u.scheme, u.netloc, u.path, '', '', ''))

def decrypter_texte(raw_text):
    if not raw_text: return ""
    text = re.sub(r'<[^>]+>', '', raw_text)
    text = html.unescape(text)
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def est_un_titre_deguise(texte):
    t = texte.strip()
    return len(t) < 85 and not t.endswith('.') and len(t) > 3

def extraire_donnees_fusion(html_content, url, source_id):
    """Extrait les données depuis le bloc Fusion.globalContent."""
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

    try:
        pattern = re.compile(r'Fusion\.globalContent\s*=\s*(\{.*?\});', re.DOTALL)
        match = pattern.search(html_content)
        
        if match:
            data = json.loads(match.group(1))
            article_data["title"] = decrypter_texte(data.get("headlines", {}).get("basic", ""))
            article_data["description"] = decrypter_texte(data.get("subheadlines", {}).get("basic", ""))
            
            date_raw = data.get("display_date") or data.get("publish_date")
            if date_raw:
                try:
                    dt = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
                    article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
                except: pass

            if data.get("planning", {}).get("scheduling", {}).get("will_pub_be_locked"):
                article_data["is_paywall"] = True

            corps_final = []
            elements = data.get("content_elements", [])
            for el in elements:
                if el.get("type") == "text":
                    txt_propre = decrypter_texte(el.get("content", ""))
                    if not txt_propre or len(txt_propre) < 3: continue
                    if est_un_titre_deguise(txt_propre):
                        corps_final.append(f"## {txt_propre}")
                    else:
                        corps_final.append(txt_propre)
            
            article_data["content"] = "\n\n".join(corps_final)
            if len(article_data["content"]) > 100:
                article_data["status"] = "success"
                
    except Exception as e:
        print(f"💥 Erreur parsing Fusion : {e}")

    return article_data

# --- 2. LOGIQUE DE NAVIGATION (Performance Maximale) ---

def process_usinenouvelle_fast(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Flash L'Usine Nouvelle : {google_url}")
    
    with sync_playwright() as p:
        # Headless=True pour la vitesse pure
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="fr-FR"
        )
        page = context.new_page()

        # OPTIMISATION 1 : Bloquer les ressources lourdes
        page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda route: route.abort())

        try:
            # OPTIMISATION 2 : wait_until="commit"
            page.goto(google_url, wait_until="commit", timeout=15000)

            # OPTIMISATION 3 : Bypass Google Flash
            if "google." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|J'accepte|Accepter tout|Accept all", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).first.click(timeout=2000, no_wait_after=True)
                except: pass

            # OPTIMISATION 4 : Boucle de redirection flash (200ms)
            start_redir = time.time()
            while time.time() - start_redir < 8:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.2)

            # OPTIMISATION 5 : Attendre juste le titre H1
            page.wait_for_selector("h1", timeout=7000)
            
            # Extraction via le bloc Fusion (très rapide car c'est du texte brut dans le HTML)
            resultat = extraire_donnees_fusion(page.content(), normalize_url(page.url), source_id)

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

    # Sauvegarde JSON unique pour Supabase
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    if len(sys.argv) > 2:
        # Args: google_url, output_filename, source_id
        process_usinenouvelle_fast(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 1)