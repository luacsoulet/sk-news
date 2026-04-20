import sys
import time
import os
import re
import json
import html
import unicodedata
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- 1. FONCTIONS DE NETTOYAGE ---

def normalize_url(url):
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

def format_filename(title):
    """Transforme un titre en nom de fichier valide pour Windows"""
    if not title or title == "Titre non trouvé":
        return f"article_sans_titre_{int(time.time())}"
    t = ''.join(c for c in unicodedata.normalize('NFD', title.lower()) if unicodedata.category(c) != 'Mn')
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    return t[:100]

# --- 2. EXTRACTION SPÉCIFIQUE (Décideurs Magazine) ---

def extraire_donnees_decideurs(html_content, url, source_id):
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

    # 1. Extraction du Titre
    h1 = soup.find('h1', class_='article-title') or soup.find('h1')
    if h1: 
        article_data["title"] = nettoyer_texte(h1.get_text())

    # 2. Extraction de la Description (Meta SEO)
    desc = soup.find('meta', attrs={'property': 'og:description'}) or soup.find('meta', attrs={'name': 'description'})
    if desc:
        article_data["description"] = nettoyer_texte(desc.get('content', ''))

    # 3. Extraction du Contenu
    corps_final = []
    
    # Décideurs Magazine sépare parfois le résumé et le texte en deux blocs ayant tous deux itemprop="articleBody"
    body_blocks = soup.find_all(attrs={'itemprop': 'articleBody'})
    
    for block in body_blocks:
        # NETTOYAGE : On détruit les blocs de partage social intégrés au milieu du texte
        for unwanted in block.find_all('div', id=re.compile(r'ampz_inline')):
            unwanted.decompose()

        # Récupération des paragraphes
        elements = block.find_all(['p', 'h2', 'h3'])
        
        if elements:
            for elem in elements:
                txt = nettoyer_texte(elem.get_text())
                if len(txt) > 3:
                    # Astuce : Si le paragraphe contient uniquement du texte en gras, c'est un sous-titre !
                    is_strong = elem.name == 'p' and elem.find('strong') and len(txt) < 80 and elem.text.strip() == elem.find('strong').text.strip()
                    
                    if elem.name in ['h2', 'h3'] or is_strong:
                        corps_final.append(f"## {txt}")
                    else:
                        corps_final.append(txt)
        else:
            # Fallback pour le premier bloc d'intro qui n'a parfois pas de balise <p>
            txt = nettoyer_texte(block.get_text())
            if len(txt) > 10 and txt not in corps_final:
                corps_final.append(txt)

    article_data["content"] = "\n\n".join(corps_final)

    # Date de publication via SEO
    date_meta = soup.find('meta', attrs={'property': 'article:published_time'})
    if date_meta:
        try:
            dt = datetime.fromisoformat(date_meta['content'].replace('Z', '+00:00'))
            article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
        except: pass

    # Validation finale
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"
        
    return article_data

# --- 3. LOGIQUE DE NAVIGATION ANTI-CRASH ---

def process_decideurs(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Flash (Décideurs Magazine) : {google_url}")
    
    resultat = {
        "title": "Crash Critique Playwright",
        "description": "",
        "content": "Le script a planté avant même de pouvoir lire la page.",
        "article_url": google_url,
        "is_paywall": False,
        "news_source_id": int(source_id),
        "created_at": datetime.now().isoformat(),
        "status": "fail"
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, # L'application l'ouvrira en fond sans te déranger !
                args=["--disable-blink-features=AutomationControlled"] 
            ) 
            
            context = browser.new_context(
                locale="fr-FR",
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # Optimisation de la vitesse de chargement
            page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,css,mp4,mp3}", lambda route: route.abort())

            page.goto(google_url, wait_until="commit", timeout=30000)

            # --- CONTOURNEMENT GOOGLE ---
            if "google." in page.url or "consent." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|Accept all|J'accepte", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).first.click(timeout=3000)
                    time.sleep(1) 
                except: pass

            # Attente de la redirection depuis Google
            start_redir = time.time()
            while time.time() - start_redir < 8:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.2)

            # Sécurité : On attend que le titre ou le corps de l'article apparaisse
            try:
                page.wait_for_selector("h1, [itemprop='articleBody']", timeout=10000)
                time.sleep(1) 
            except Exception:
                print("⚠️ Attention : L'article a mis trop de temps à charger.")

            # Extraction
            resultat = extraire_donnees_decideurs(page.content(), normalize_url(page.url), source_id)
            browser.close()
            
    except Exception as e:
        print(f"💥 Erreur globale détectée : {e}")
        resultat["content"] = f"Erreur fatale de chargement : {str(e)}"

    # --- DOUBLE SAUVEGARDE GARANTIE ---
    print(f"💾 Écriture des données temporaires dans : {output_filename}")
    try:
        # Fichier 1 : Pour processor.py (temp_res_XXX.json)
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(resultat, f, ensure_ascii=False, indent=4)
        
        # Fichier 2 : Sauvegarde avec le vrai nom de l'article pour historique
        dossier_parent = os.path.dirname(os.path.abspath(output_filename))
        nom_propre = format_filename(resultat["title"])
        fichier_titre = os.path.join(dossier_parent, f"{nom_propre}.json")
        
        with open(fichier_titre, "w", encoding="utf-8") as f2:
            json.dump(resultat, f2, ensure_ascii=False, indent=4)
            
        print(f"✅ Fichiers JSON créés avec succès !")
    except Exception as e:
        print(f"❌ Impossible de créer le fichier : {e}")

# --- SYSTÈME ROBUSTE DE GESTION DES ARGUMENTS ---
if __name__ == "__main__":
    if len(sys.argv) > 1:
        url_cible = sys.argv[1]
        fichier_sortie = "fallback_error.json"
        id_source = "1"
        
        for arg in sys.argv[2:]:
            arg_clean = arg.strip(' "\'') 
            if arg_clean.lower().endswith(".json"):
                fichier_sortie = arg_clean
            elif arg_clean.isdigit() and len(arg_clean) < 5:
                id_source = arg_clean
                
        process_decideurs(url_cible, fichier_sortie, id_source)
    else:
        print("❌ Erreur : Nombre d'arguments invalide.")