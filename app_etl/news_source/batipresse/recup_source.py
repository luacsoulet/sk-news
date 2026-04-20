import time
import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_batipresse_file(url):
    # Dossier actuel pour la sauvegarde
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    # --- ADAPTATION POUR BATIPRESSE.COM ---
    # On extrait le nom du fichier de l'URL (le slug après la date)
    path = urlparse(url).path
    segments = [s for s in path.split('/') if s]
    # On prend le dernier segment qui correspond au nom du fichier dans l'onglet Sources
    slug = segments[-1]
    
    print(f"🔍 Cible réseau détectée : {slug}")

    with sync_playwright() as p:
        # Lancement du navigateur
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Flag pour ne capturer que le fichier principal
        state = {"captured": False}

        def handle_response(response):
            # On cherche l'URL qui contient le slug de l'article sur batipresse.com
            if slug in response.url and "batipresse.com" in response.url and not state["captured"]:
                if response.status == 200:
                    content_type = response.headers.get("content-type", "").lower()
                    # On cible le document HTML ou les données JSON
                    if "html" in content_type or "json" in content_type:
                        print(f"🎯 Source interceptée : {response.url[:100]}...")
                        try:
                            data = response.text()
                            with open(filename, "w", encoding="utf-8") as f:
                                f.write(data)
                            print(f"✅ Fichier source sauvegardé dans : {filename}")
                            state["captured"] = True
                        except Exception as e:
                            print(f"⚠️ Erreur de lecture : {e}")

        # Activation de l'écouteur
        page.on("response", handle_response)

        print(f"🚀 Navigation vers : {url}")
        try:
            # On attend networkidle pour laisser les requêtes de contenu passer
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(5) 
            
            if not state["captured"]:
                print("⚠️ Interception réseau spécifique échouée.")
                print("📦 Sauvegarde du contenu HTML de la page par défaut...")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page.content())
                print(f"✅ Contenu sauvegardé.")
                
        except Exception as e:
            print(f"❌ Erreur : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    target_url = "https://www.batipresse.com/2017/05/02/la-collection-one-world-de-swiss-krono-senrichit-32-decors-inedits-pour-creer-des-univers-a-linfini/"
    intercept_batipresse_file(target_url)