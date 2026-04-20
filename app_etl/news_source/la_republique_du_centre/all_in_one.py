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
    if not text: return ""
    try:
        text = text.encode('latin-1').decode('utf-8')
    except: pass
    return text.replace('Â', '').replace('\xa0', ' ')

def nettoyer_texte(text):
    if not text: return ""
    return reparer_encodage(html.unescape(text)).strip()

def structurer_le_corps(text):
    """
    Le JSON-LD donne le texte sous forme d'un seul bloc (articleBody).
    Cette fonction recrée des paragraphes aérés à chaque fin de phrase.
    """
    if not text: return ""
    
    # 1. On insère des sauts de ligne après un point suivi d'une majuscule
    text = re.sub(r'([\.!\?])\s+([A-ZÉÀÈ])', r'\1\n\n\2', text)
    
    # 2. Nettoyage des espaces et lignes vides multiples
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

# --- 2. EXTRACTION SPÉCIFIQUE (La République du Centre) ---

def extraire_donnees_larep(html_content, url, source_id):
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

    # 1. PLAN A : Recherche chirurgicale du bloc JSON-LD
    json_ld_script = soup.find('script', id='articleJsonLd')
    
    # Fallback : s'il n'a pas l'ID, on cherche celui qui contient "articleBody"
    if not json_ld_script:
        scripts = soup.find_all('script', type='application/ld+json')
        for s in scripts:
            if s.text and 'articleBody' in s.text:
                json_ld_script = s
                break

    if json_ld_script and json_ld_script.text:
        try:
            # strict=False empêche le plantage sur les caractères invisibles
            data = json.loads(json_ld_script.text.strip(), strict=False)
            
            article_data["title"] = nettoyer_texte(data.get("headline", article_data["title"]))
            article_data["description"] = nettoyer_texte(data.get("description", ""))
            
            date_raw = data.get("datePublished") or data.get("dateCreated")
            if date_raw:
                try:
                    dt = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
                    article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
                except: pass
                
            if data.get("isAccessibleForFree") is False:
                article_data["is_paywall"] = True
                
            # Extraction magique du texte brut
            body = data.get("articleBody", "")
            if body:
                article_data["content"] = structurer_le_corps(nettoyer_texte(body))
                
        except Exception as e:
            print(f"💥 Erreur de parsing du JSON-LD : {e}")

    # 2. PLAN B : Fallback HTML Classique (Si le JSON a échoué)
    if len(article_data["content"]) < 100:
        print("⚠️ JSON-LD vide ou défectueux, activation du Plan B (HTML)")
        
        if article_data["title"] == "Titre non trouvé":
            h1 = soup.find('h1')
            if h1: article_data["title"] = nettoyer_texte(h1.get_text())
            
        if not article_data["description"]:
            desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if desc: article_data["description"] = nettoyer_texte(desc.get('content', ''))

        body_container = soup.find('div', itemprop='articleBody') or soup.find('div', class_=re.compile(r'article.*body', re.I))
        if body_container:
            corps_final = []
            for p in body_container.find_all(['p', 'h2', 'h3']):
                txt = nettoyer_texte(p.get_text())
                if len(txt) > 5:
                    corps_final.append(f"## {txt}" if p.name in ['h2', 'h3'] else txt)
            article_data["content"] = "\n\n".join(corps_final)

    # Validation finale
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"
        
    return article_data

# --- 3. LOGIQUE DE NAVIGATION (Furtive et Rapide) ---

def process_larep(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Flash (La Rep) : {google_url}")
    
    with sync_playwright() as p:
        # Anti-Bot très strict pour le groupe Centre France
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"] 
        ) 
        
        context = browser.new_context(
            locale="fr-FR",
            timezone_id="Europe/Paris",
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Upgrade-Insecure-Requests": "1"
            }
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Bloquer images/css pour aller très vite, mais laisser les scripts JS
        page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,css,mp4,mp3}", lambda route: route.abort())

        try:
            page.goto(google_url, wait_until="commit", timeout=30000)

            # Bypass Consentement
            if "google." in page.url or "consent." in page.url or "didomi" in page.content():
                try:
                    regex_consent = re.compile(r"Tout accepter|J'accepte", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).first.click(timeout=2000, no_wait_after=True)
                except: pass

            # Sortie de la redirection
            start_redir = time.time()
            while time.time() - start_redir < 8:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.2)

            # On attend que le script JSON-LD apparaisse !
            try:
                page.wait_for_selector("#articleJsonLd, h1", timeout=8000)
            except:
                time.sleep(1)
            
            # Extraction finale
            resultat = extraire_donnees_larep(page.content(), normalize_url(page.url), source_id)

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

    # --- SÉCURITÉ SAUVEGARDE ---
    print(f"💾 Écriture des données dans : {output_filename}")
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(resultat, f, ensure_ascii=False, indent=4)
        print("✅ Fichier JSON créé avec succès !")
    except Exception as e:
        print(f"❌ Impossible de créer le fichier : {e}")

# --- SYSTÈME ROBUSTE DE GESTION DES ARGUMENTS ---
if __name__ == "__main__":
    if len(sys.argv) >= 4:
        url_cible = sys.argv[1]
        fichier_sortie = "fallback_error.json"
        id_source = "1"
        
        # Le système ULTRA robuste pour éviter les bugs avec app_etl.py
        for arg in sys.argv[2:]:
            arg_clean = arg.strip(' "\'') 
            
            if arg_clean.lower().endswith(".json"):
                fichier_sortie = arg_clean
            elif arg_clean.isdigit() and len(arg_clean) < 5:
                id_source = arg_clean
                
        process_larep(url_cible, fichier_sortie, id_source)
        
    elif len(sys.argv) == 2:
        process_larep(sys.argv[1], "test_local.json", "1")
        
    else:
        print("❌ Erreur : Nombre d'arguments invalide.")