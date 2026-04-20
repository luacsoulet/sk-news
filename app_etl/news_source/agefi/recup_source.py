import time
import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_agefi_file(url):
    # Définition du chemin du fichier local
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    # --- ADAPTATION POUR AGEFI.COM ---
    # On extrait le slug de l'URL
    path = urlparse(url).path
    slug = path.split('/')[-1]
    
    # Si l'URL finit par un slash, on prend le segment précédent
    if not slug:
        slug = path.split('/')[-2]

    print(f"🔍 Cible réseau détectée : {slug}")

    with sync_playwright() as p:
        # Lancement du navigateur (headless=False pour éviter les blocages basiques)
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Flag pour ne capturer que le premier fichier (le plus important)
        state = {"captured": False}

        def handle_response(response):
            # On cherche l'URL qui contient exactement le nom de l'article
            # et qui provient bien du domaine agefi.com
            if slug in response.url and "agefi.com" in response.url and not state["captured"]:
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

        # On active l'écouteur de réponses réseau
        page.on("response", handle_response)

        print(f"🚀 Navigation vers : {url}")
        try:
            # On attend que le réseau soit inactif (networkidle) 
            # pour laisser le temps aux fichiers de données de se charger
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(5) 
            
            if not state["captured"]:
                print("⚠️ Le fichier spécifique n'a pas été vu par l'intercepteur.")
                print("📦 Tentative de sauvegarde du HTML complet par sécurité...")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page.content())
                print(f"✅ HTML de la page sauvegardé dans : {filename}")
                
        except Exception as e:
            print(f"❌ Erreur de navigation : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    target_url = "https://agefi.com/actualites/entreprises/peter-wijnbergen-nomme-directeur-general-de-swiss-krono"
    intercept_agefi_file(target_url)