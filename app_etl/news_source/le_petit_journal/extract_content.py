import sys
import time
import os
import re
import json
import html
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- 1. FONCTIONS DE NETTOYAGE (Ta Logique) ---

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
    with sync_playwright() as p:
        # headless=True pour l'intégration, False si tu veux débugger
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Cache le robot
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            # Navigation vers l'URL
            page.goto(google_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5) # Attend le chargement des scripts
            
            # Extraction
            resultat = extraire_donnees_lpj(page.content(), page.url, source_id)
        except Exception as e:
            resultat = {
                "title": "Erreur LPJ", "status": "fail", "content": str(e),
                "news_source_id": int(source_id), "article_url": google_url
            }
        finally:
            browser.close()

    # Sauvegarde JSON pour le processeur
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Gère les appels à 2 ou 4 arguments du processor.py
        u = sys.argv[1]
        out = sys.argv[4] if len(sys.argv) > 4 else sys.argv[2]
        sid = sys.argv[3] if len(sys.argv) > 3 else 1
        process_lpj(u, out, sid)