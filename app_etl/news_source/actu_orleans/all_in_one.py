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
    try:
        text = text.encode('latin-1').decode('utf-8')
    except: pass
    return text.replace('Â', '').replace('\xa0', ' ').strip()

def nettoyer_texte(raw_text):
    """Nettoyage final : Décodage HTML + Suppression balises + Filtres Actu.fr"""
    if not raw_text: return ""
    text = html.unescape(raw_text)
    text = reparer_encodage(text)
    text = re.sub(r'<[^>]+>', '', text)
    
    # Suppression des résidus de partage social spécifiques à Actu.fr
    forbidden = [
        "Partagez sur Facebook", "Partagez sur Twitter", "Partagez par Mail", 
        "Copiez/Collez le Lien", "Copié !", "Enregistrer l'article",
        "Suivez toute l’actualité de vos villes et médias favoris"
    ]
    for phrase in forbidden:
        text = text.replace(phrase, "")

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def extraire_donnees_actu(html_content, url, source_id):
    """Logique d'extraction chirurgicale Actu.fr adaptée Supabase."""
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

    # Nettoyage préventif du DOM
    classes_a_supprimer = ["ac-article-actions", "ac-article-actions__share", "ac-banner-ad", "ac-article-footer"]
    for tag in soup.find_all(class_=classes_a_supprimer):
        tag.decompose()

    # 1. TITRE
    title_tag = soup.find('h1')
    if title_tag:
        article_data["title"] = nettoyer_texte(title_tag.get_text())

    # 2. RÉSUMÉ
    desc_meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
    if desc_meta:
        article_data["description"] = nettoyer_texte(desc_meta.get('content', ''))
    
    # 3. DATE DE PUBLICATION RÉELLE
    date_tag = soup.find('time') or soup.find(class_='ac-article-date')
    if date_tag:
        raw_date = date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
        except: pass

    # 4. PAYWALL
    if soup.find(class_=re.compile(r'premium|paywall|register-gate|restricted')):
        article_data["is_paywall"] = True

    # 5. CORPS DE L'ARTICLE (Logique js-article-inner)
    body_container = soup.find('article', class_='js-article-inner') or soup.find('div', class_='ac-article-content')
    contenu_final = []

    if body_container:
        elements = body_container.find_all(['p', 'h2', 'li'])
        skip_next = 0  
        for element in elements:
            txt_brut = element.get_text().strip()
            if "Personnalisez votre actualité" in txt_brut: break
            
            # Filtrage des blocs de recommandation internes
            if "À lire aussi" in txt_brut or "À LIRE AUSSI" in txt_brut:
                skip_next = 2
                continue
            if skip_next > 0:
                skip_next -= 1
                continue

            propre = nettoyer_texte(txt_brut)
            if propre and len(propre) > 5:
                if element.name == 'h2': contenu_final.append(f"## {propre}")
                elif element.name == 'li': contenu_final.append(f"* {propre}")
                else: contenu_final.append(propre)
    
    article_data["content"] = "\n\n".join(contenu_final)
    
    # Validation
    if len(article_data["content"]) > 100:
        article_data["status"] = "success"

    return article_data

# --- 2. LOGIQUE DE NAVIGATION (Performance Maximale) ---

def process_actu_fast(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement Flash Actu.fr : {google_url}")
    
    with sync_playwright() as p:
        # Headless=True pour la vitesse pure
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(locale="fr-FR", user_agent="Mozilla/5.0...")
        page = context.new_page()

        # OPTIMISATION 1 : Bloquer les images et polices (Massif pour Actu.fr)
        page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda route: route.abort())

        try:
            # OPTIMISATION 2 : wait_until="commit" (navigation éclair)
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
            resultat = extraire_donnees_actu(page.content(), normalize_url(page.url), source_id)

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
        process_actu_fast(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 1)