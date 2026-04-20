import json
import re
import os
import html
import time
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
URL_CIBLE = "https://www.sudouest.fr/lot-et-garonne/casteljaloux/usine-geante-de-panneaux-bois-dans-les-landes-de-gascogne-swiss-krono-veut-rassurer-sur-le-trafic-routier-24966739.php"
FICHIER_SORTIE = "article_final_propre_filouterie.txt"

def reparer_encodage(text):
    if not text: return ""
    try:
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    text = text.replace('Â', '')
    text = text.replace('\xa0', ' ')
    return text

def diviser_et_formater_corps(text):
    """Transforme le bloc compact en paragraphes Markdown avec titres ##"""
    if not text: return ""
    # Détection des titres de section entre guillemets
    text = re.sub(r'["«]([^"»]{5,80})["»]', r'\n\n## \1\n\n', text)
    # Séparation des phrases collées (Point suivi d'une majuscule)
    text = re.sub(r'([\.!\?])([A-Z])', r'\1\n\n\2', text)
    # Nettoyage final
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def intercepter_et_modifier(route):
    """Intercepte la requête Paywall et modifie userIsPremium à True"""
    request = route.request()
    if "paywall" in request.url and request.method == "POST":
        try:
            payload = request.post_data_json
            if payload:
                payload["userIsPremium"] = True
                print("🎯 SNIPER : userIsPremium passé à True dans le Payload.")
                route.continue_(post_data=json.dumps(payload))
                return
        except:
            pass
    route.continue_()

def extraire_contenu():
    with sync_playwright() as p:
        # 1. Lancement du navigateur
        browser = p.chromium.launch(headless=False) # Mettre True pour cacher la fenêtre
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # 2. Mise en place du Sniper réseau
        page.route("**/paywall*", intercepter_et_modifier)

        print(f"🚀 Navigation vers : {URL_CIBLE}")
        page.goto(URL_CIBLE, wait_until="networkidle", timeout=60000)

        # 3. Forcer le déblocage visuel (article.release)
        try:
            page.evaluate("_gsoi.require('article').then(a => a.release())")
            print("✅ Commande article.release() envoyée.")
        except:
            print("⚠️ Impossible d'exécuter article.release().")

        time.sleep(2) # Attente pour le rendu

        # 4. Extraction des données depuis le code source
        content = page.content()
        match = re.search(r'<script id="articleJsonLd" type="application/ld\+json">(.*?)</script>', content, re.DOTALL)

        if match:
            data = json.loads(match.group(1).strip())
            titre = reparer_encodage(html.unescape(data.get("headline", "")))
            resume = reparer_encodage(html.unescape(data.get("description", "")))
            corps_brut = html.unescape(data.get("articleBody", ""))
            corps_propre = diviser_et_formater_corps(reparer_encodage(corps_brut))

            # 5. Sauvegarde
            with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
                f.write(f"# {titre}\n\n")
                if resume:
                    f.write(f"RÉSUMÉ : {resume}\n\n")
                f.write("--- CORPS DE L'ARTICLE ---\n\n")
                f.write(corps_propre)
            
            print(f"✅ SUCCÈS ! L'article complet est dans : {FICHIER_SORTIE}")
        else:
            print("❌ Erreur : Bloc articleJsonLd introuvable.")

        browser.close()

if __name__ == "__main__":
    extraire_contenu()