import sys
import time
import os
import re
import json
import html
import random
import unicodedata
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- 1. FONCTIONS DE NETTOYAGE ---

def normalize_url(url):
    """Supprime les paramètres de tracking (?utm...)"""
    if not url or "google." in url: return url
    u = urlparse(url)
    return urlunparse((u.scheme, u.netloc, u.path, '', '', ''))

def reparer_encodage(text):
    """Répare les problèmes d'affichage (espaces insécables, etc.)"""
    if not text: return ""
    try:
        text = text.encode('latin-1').decode('utf-8')
    except: pass
    return text.replace('Â', '').replace('\xa0', ' ')

def nettoyer_texte(text):
    if not text: return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text) # Nettoie le HTML résiduel
    text = re.sub(r'\s+', ' ', text)
    return reparer_encodage(text).strip()

def format_filename(title):
    if not title or title == "Titre non trouvé":
        return f"article_sans_titre_{int(time.time())}"
    t = ''.join(c for c in unicodedata.normalize('NFD', title.lower()) if unicodedata.category(c) != 'Mn')
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    return t[:100]

# --- 2. EXTRACTION SPÉCIFIQUE (Actu-Environnement) ---

def extraire_donnees_actu_environnement(html_content, url, source_id):
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

    # On cible en priorité le conteneur du communiqué/article
    conteneur = soup.find('div', class_='communique') or soup.find('div', id='pdt') or soup
    
    # 1. Extraction du Titre
    h1 = conteneur.find('h1')
    if h1:
        article_data["title"] = nettoyer_texte(h1.get_text())
    else:
        meta_title = soup.find('meta', attrs={'property': 'og:title'})
        if meta_title: article_data["title"] = nettoyer_texte(meta_title.get('content', ''))

    # 2. Date de publication (On la cherche dans la barre d'infos "Communiqué | Energie | 09/09/2024")
    infos = conteneur.find('div', class_='infos')
    if infos:
        match_date = re.search(r'(\d{2})/(\d{2})/(\d{4})', infos.get_text())
        if match_date:
            jour, mois, annee = match_date.groups()
            article_data["created_at"] = f"{annee}-{mois}-{jour}T12:00:00"

    # Si pas de date trouvée, on teste les metas SEO
    if "T" not in article_data["created_at"]:
        date_meta = soup.find('meta', attrs={'property': 'article:published_time'})
        if date_meta:
            try:
                dt = datetime.fromisoformat(date_meta['content'].replace('Z', '+00:00'))
                article_data["created_at"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
            except: pass

    # 3. Extraction du Contenu Principal
    corps_final = []
    texte_div = conteneur.find('div', class_='texte')
    
    if texte_div:
        # Transformation des balises <b> en sous-titres markdown (##)
        for b_tag in texte_div.find_all(['b', 'strong']):
            txt_b = nettoyer_texte(b_tag.get_text())
            if len(txt_b) > 5:
                b_tag.replace_with(f"\n\n## {txt_b}\n\n")
                
        # Transformation des retours à la ligne <br> en vrais sauts de ligne
        for br in texte_div.find_all('br'):
            br.replace_with('\n')

        # On récupère le texte brut avec nos nouveaux sauts de lignes et sous-titres
        raw_text = texte_div.get_text()
        
        # On découpe le texte ligne par ligne pour recréer les paragraphes
        for ligne in raw_text.split('\n'):
            ligne_propre = nettoyer_texte(ligne)
            if len(ligne_propre) > 5:
                corps_final.append(ligne_propre)
                
    # 4. Ajout de la section "Présentation entreprise" (Signature)
    presentation = conteneur.find('div', class_='presentation_entreprise')
    if presentation:
        txt_presentation = nettoyer_texte(presentation.get_text())
        if txt_presentation:
            corps_final.append("## À propos")
            corps_final.append(txt_presentation)

    # 5. Description (Fallback sur le premier paragraphe si meta absente)
    desc_meta = soup.find('meta', attrs={'property': 'og:description'}) or soup.find('meta', attrs={'name': 'description'})
    if desc_meta:
        article_data["description"] = nettoyer_texte(desc_meta.get('content', ''))
    elif corps_final:
        # On prend le premier paragraphe qui n'est pas un titre comme description
        for p in corps_final:
            if not p.startswith("##"):
                article_data["description"] = p
                break

    # Nettoyage des doublons éventuels
    corps_final_sans_doublons = list(dict.fromkeys(corps_final))
    article_data["content"] = "\n\n".join(corps_final_sans_doublons)

    # Validation
    if len(article_data["content"]) > 50:
        article_data["status"] = "success"
        
    return article_data

# --- 3. LOGIQUE DE NAVIGATION ANTI-BOT CLOUDFLARE ---

def process_actu_environnement(google_url, output_filename, source_id=1):
    print(f"🚀 Lancement (Actu-Environnement) : {google_url}")
    
    resultat = {
        "title": "Crash",
        "description": "",
        "content": "Erreur lors du chargement de la page.",
        "article_url": google_url,
        "is_paywall": False,
        "news_source_id": int(source_id),
        "created_at": datetime.now().isoformat(),
        "status": "fail"
    }

    try:
        with sync_playwright() as p:
            # 👁️ HEADLESS = FALSE : Indispensable pour passer Cloudflare Turnstile
            browser = p.chromium.launch(
                headless=False, 
                args=["--disable-blink-features=AutomationControlled"] 
            ) 
            
            context = browser.new_context(
                locale="fr-FR",
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            print("⏳ Accès à l'URL...")
            page.goto(google_url, wait_until="domcontentloaded", timeout=45000)

            # Bypass Google News
            if "google." in page.url or "consent." in page.url:
                try:
                    regex_consent = re.compile(r"Tout accepter|Accept all|J'accepte|Accepter tout", re.IGNORECASE)
                    page.get_by_role("button", name=regex_consent).first.click(timeout=3000)
                except: pass

            # Attente de la redirection depuis Google
            start_redir = time.time()
            while time.time() - start_redir < 10:
                if "google." not in page.url and "consent." not in page.url:
                    break
                time.sleep(0.5)

            # 🤖 Émulation humaine (Pour valider Cloudflare Turnstile)
            print("🚶 Simulation de lecture pour Cloudflare...")
            time.sleep(random.uniform(1.0, 2.0))
            
            # Mouvement de souris
            try:
                page.mouse.move(random.randint(300, 800), random.randint(200, 600))
                time.sleep(random.uniform(0.5, 1.0))
            except: pass

            # Scroll
            for _ in range(2):
                try:
                    page.mouse.wheel(0, random.randint(250, 400))
                    time.sleep(random.uniform(1.0, 2.0))
                except: pass

            # On attend la balise contenant le texte du communiqué
            try:
                page.wait_for_selector(".communique, .texte, h1", timeout=8000)
            except Exception:
                print("⚠️ Temps d'attente pour les balises écoulé.")

            # Extraction
            html_content = page.content()
            resultat = extraire_donnees_actu_environnement(html_content, normalize_url(page.url), source_id)
            browser.close()
            
    except Exception as e:
        print(f"💥 Erreur globale : {e}")

    # Sauvegarde
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(resultat, f, ensure_ascii=False, indent=4)
        
        dossier_parent = os.path.dirname(os.path.abspath(output_filename))
        nom_propre = format_filename(resultat["title"])
        fichier_titre = os.path.join(dossier_parent, f"{nom_propre}.json")
        
        with open(fichier_titre, "w", encoding="utf-8") as f2:
            json.dump(resultat, f2, ensure_ascii=False, indent=4)
            
        print("✅ Terminé !")
    except Exception as e:
        print(f"❌ Erreur écriture fichier : {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_actu_environnement(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "fallback.json", sys.argv[3] if len(sys.argv) > 3 else 1)