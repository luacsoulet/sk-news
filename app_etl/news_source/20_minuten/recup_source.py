import time
import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_20min_file(url):
    # Chemin du fichier local
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    # --- ADAPTATION POUR 20MIN.CH ---
    # On extrait le slug complet de l'URL (ex: une-usine-de-bois-lucernoise-ravagee-par-un-incendie-811787226586)
    path = urlparse(url).path
    slug = path.split('/')[-1]
    
    print(f"🔍 Cible réseau détectée : {slug}")

    with sync_playwright() as p:
        # Lancement du navigateur
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Flag pour ne capturer que le premier fichier correspondant
        state = {"captured": False}

        def handle_response(response):
            # On cherche l'URL qui contient le dossier /story/ et le slug de l'article
            if "/story/" in response.url and slug in response.url and not state["captured"]:
                if response.status == 200:
                    print(f"🎯 Fichier source intercepté : {response.url[:100]}...")
                    try:
                        data = response.text()
                        with open(filename, "w", encoding="utf-8") as f:
                            f.write(data)
                        print(f"✅ Fichier brut sauvegardé dans : {filename}")
                        state["captured"] = True
                    except Exception as e:
                        print(f"⚠️ Erreur de lecture : {e}")

        # Activation de l'écouteur
        page.on("response", handle_response)

        print(f"🚀 Navigation vers : {url}")
        try:
            # On attend networkidle pour capturer les flux de données
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(5) 
            
            if not state["captured"]:
                print("⚠️ Le fichier spécifique n'a pas été intercepté.")
                print("📦 Sauvegarde du HTML complet par défaut...")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page.content())
        except Exception as e:
            print(f"❌ Erreur : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    target_url = "https://www.20min.ch/fr/story/une-usine-de-bois-lucernoise-ravagee-par-un-incendie-811787226586"
    intercept_20min_file(target_url)