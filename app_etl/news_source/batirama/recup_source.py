import time
import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_batirama_file(url):
    # Chemin du fichier local pour stocker la source
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    # --- ADAPTATION POUR BATIRAMA.COM ---
    # On extrait le nom du fichier de l'URL (le slug avec l'ID)
    path = urlparse(url).path
    slug = path.split('/')[-1].replace('.html', '')
    
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
            # On cherche l'URL qui contient le slug de l'article dans le domaine batirama
            if slug in response.url and "batirama.com" in response.url and not state["captured"]:
                if response.status == 200:
                    print(f"🎯 Fichier source détecté : {response.url[:100]}...")
                    try:
                        data = response.text()
                        with open(filename, "w", encoding="utf-8") as f:
                            f.write(data)
                        print(f"✅ Fichier source sauvegardé dans : {filename}")
                        state["captured"] = True
                    except Exception as e:
                        print(f"⚠️ Erreur de lecture : {e}")

        # Activation de l'écouteur de réponses réseau
        page.on("response", handle_response)

        print(f"🚀 Navigation vers : {url}")
        try:
            # On attend networkidle pour laisser les requêtes de données passer
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
    target_url = "https://www.batirama.com/article/53757-l-industrie-lourde-du-bois-cherche-la-parade-energetique.html"
    intercept_batirama_file(target_url)