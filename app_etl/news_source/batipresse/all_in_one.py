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

# --- 1. FONCTIONS DE NETTOYAGE ET DÉCRYPTAGE ---

def normalize_url(url):
    """Supprime les paramètres de tracking (?utm...)"""
    if not url or "google." in url: return url
    u = urlparse(url)
    return urlunparse((u.scheme, u.netloc, u.path, '', '', ''))

def reparer_encodage(text):
    """Répare les problèmes d'affichage Mojibake."""
    if not text: return ""
    try:
        text = text.encode('latin-1').decode('utf-8')
    except: pass
    return text.replace('Â', '').replace('\xa0', ' ')

def nettoyer_et_decrypter(raw_text):
    """Décode les entités HTML, nettoie les balises et répare l'encodage."""
    if not raw_text: return ""
    text = html.unescape(raw_text)
    text = re.sub(r'<[^>]+>', '', text)
    text = reparer_encodage(text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def format_filename(title):
    """Transforme un titre en nom de fichier valide pour Windows"""
    if not title or title == "Titre non trouvé":
        return f"article_sans_titre_{int(time.time())}"
    t = ''.join(c for c in unicodedata.normalize('NFD', title.lower()) if unicodedata.category(c) != 'Mn')
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    return t[:100]

# --- 2. EXTRACTION SPÉCIFIQUE (Batipresse) ---

def extraire_donnees_batipresse(html_content, url, source_id):
    """Logique d'extraction spécifique Batipresse (WordPress) pour Supabase."""
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
    titre_tag = soup.find('h1', class_='entry-title') or soup.find('h1')
    if titre_tag:
        article_data["title"] = nettoyer_et_decrypter(titre_tag.get_text())

    # 2. DATE DE PUBLICATION RÉELLE
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        if raw_date:
            try:
                dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
            except: pass

    # 3. CONTENU PRINCIPAL (entry-content)
    content_div = soup.find('div', class_='entry-content')
    corps_elements = []

    if content_div:
        # Détection Paywall
        if content_div.find(class_=re.compile(r'lock|premium|restricted-content|paywall')):
            article_data["is_paywall"] = True

        paragraphs = content_div.find_all(['p', 'h2', 'h3'])
        for i, p in enumerate(paragraphs):
            txt = p.get_text().strip()
            if not txt or len(txt) < 10: continue
            
            # On utilise le premier paragraphe comme description si meta absente
            if i == 0 and not article_data["description"]:
                article_data["description"] = nettoyer_et_decrypter(txt)
            
            # Transformation en Markdown
            if p.name in ['h2', 'h3'] or (p.find('strong', recursive=False) and len(txt) < 100):
                corps_elements.append(f"## {nettoyer_et_decrypter(txt)}")
            else:
                corps_elements.append(nettoyer_et_decrypter(txt))
    
    article_data["content"] = "\n\n".join(corps_elements)

    # 4. STATUS
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"

    return article_data

# --- 3. LOGIQUE DE NAVIGATION ANTI-CRASH ---

def process_batipresse(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Flash (Batipresse) : {google_url}")
    
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
                headless=True,
                args=["--disable-blink-features=AutomationControlled"] 
            ) 
            
            context = browser.new_context(
                locale="fr-FR",
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # OPTIMISATION : Bloquer les images et polices
            page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,css,mp4,mp3}", lambda route: route.abort())

            page.goto(google_url, wait_until="commit", timeout=30000)

            # Bypass Google Consent Flash
            if "google." in page.url or "consent." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|Accept all|J'accepte|Accepter tout", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).first.click(timeout=3000)
                    time.sleep(1) 
                except: pass

            # Boucle de redirection
            start_redir = time.time()
            while time.time() - start_redir < 8:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.2)

            # Attendre uniquement le titre ou le contenu
            try:
                page.wait_for_selector("h1, .entry-content", timeout=10000)
                time.sleep(1)
            except Exception:
                print("⚠️ Attention : La page a mis trop de temps à charger.")

            # Extraction finale
            resultat = extraire_donnees_batipresse(page.content(), normalize_url(page.url), source_id)
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
                
        process_batipresse(url_cible, fichier_sortie, id_source)
    else:
        print("❌ Erreur : Nombre d'arguments invalide.")