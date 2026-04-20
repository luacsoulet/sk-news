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
    """Répare les problèmes d'affichage comme Ã© -> é"""
    if not text: return ""
    try:
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    text = text.replace('Â', '').replace('\xa0', ' ')
    return text

def nettoyer_texte(text):
    """Nettoyage de base du texte brut"""
    if not text: return ""
    text = html.unescape(text)
    text = reparer_encodage(text)
    return text.strip()

def extraire_donnees_lpj(html_content, url, source_id):
    """Logique d'extraction spécifique Le Petit Journal"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Titre (entry-title)
    titre_tag = soup.find(['h1', 'h2'], class_='entry-title')
    titre_final = nettoyer_texte(titre_tag.get_text()) if titre_tag else "Titre non trouvé"

    # 2. Résumé
    resume_tag = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
    description = nettoyer_texte(resume_tag['content']) if resume_tag else ""

    # 3. Date
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    date_str = datetime.now().isoformat()
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            date_str = dt.isoformat()
        except:
            date_str = raw_date

    # 4. Corps (entry-content)
    corps_final = []
    is_paywall = False
    container = soup.find('div', class_='entry-content')
    
    if container:
        # Détection Paywall
        if soup.find(class_=re.compile(r'paywall|premium|lock|restricted')):
            is_paywall = True

        elements = container.find_all(['p', 'h2', 'h3'])
        for elem in elements:
            if 'signature' in elem.get('class', []) or elem.find('script'):
                continue
            
            txt = nettoyer_texte(elem.get_text())
            if not txt or len(txt) < 5:
                continue

            is_subtitle = elem.name in ['h2', 'h3']
            if not is_subtitle and len(txt) < 80:
                if (txt.startswith('"') and txt.endswith('"')) or (txt.startswith('«') and txt.endswith('»')):
                    is_subtitle = True
                    txt = txt.strip('"').strip('«').strip('»')

            if is_subtitle:
                corps_final.append(f"## {txt}")
            else:
                # Séparation des phrases collées via ta Regex
                txt = re.sub(r'([\.!\?])([A-Z])', r'\1\n\n\2', txt)
                corps_final.append(txt)
    
    return {
        "title": titre_final,
        "description": description,
        "content": "\n\n".join(corps_final),
        "article_url": url,
        "is_paywall": is_paywall,
        "news_source_id": int(source_id),
        "created_at": date_str,
        "status": "success" if len(corps_final) > 0 else "fail"
    }

# --- 2. NAVIGATION (Ta Logique Playwright) ---

def process_lpj(google_url, output_filename, source_id):
    print(f"🚀 Lancement Flash (Le Petit Journal) : {google_url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(
            locale="fr-FR", 
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Cache le robot
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Bloquer les images/css/fonts pour accélérer énormément le scraping
        page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,css,mp4,mp3}", lambda route: route.abort())

        try:
            # Navigation ultra rapide
            page.goto(google_url, wait_until="commit", timeout=30000)

            # Bypass Consentement Google News si on passe par là
            if "google." in page.url or "consent." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|J'accepte", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).click(timeout=2000, no_wait_after=True)
                except: pass

            # Boucle de redirection (200ms) pour quitter Google News
            start_redir = time.time()
            while time.time() - start_redir < 8:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.2)

            # On attend que l'article charge concrètement (ton h1 ou .entry-title)
            try:
                page.wait_for_selector(".entry-title, h1", timeout=8000)
            except:
                time.sleep(2) # Fallback court
            
            # Extraction finale
            resultat = extraire_donnees_lpj(page.content(), normalize_url(page.url), source_id)

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

    # --- SÉCURITÉ DE SAUVEGARDE ---
    print(f"💾 Écriture des données dans : {output_filename}")
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(resultat, f, ensure_ascii=False, indent=4)
        print("✅ Fichier JSON créé avec succès !")
    except Exception as e:
        print(f"❌ Impossible de créer le fichier : {e}")

# --- LA MAGIE EST ICI ---
if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
        output_file = "fallback_error.json"
        source_id = "1"
        
        # Le script fouille TOUS les arguments envoyés par processor.py
        for arg in sys.argv[2:]:
            if arg.endswith(".json"):
                output_file = arg  # Si ça finit par .json, c'est le fichier !
            elif arg.isdigit() and len(arg) < 5:
                source_id = arg    # Si c'est un petit chiffre, c'est l'ID de la source !
                
        # On exécute avec les bons arguments, en ignorant le Titre !
        process_lpj(url, output_file, source_id)