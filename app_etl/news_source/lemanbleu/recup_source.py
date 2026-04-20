import time
import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_lemanbleu_file(url):
    # Chemin du fichier local pour stocker la source
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    # --- ADAPTATION POUR LEMANBLEU.CH ---
    # On extrait le slug (ex: Incendie-dans-une-entreprise-a-Menznau-LU)
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
            # On cherche l'URL qui contient le slug de l'article
            if slug in response.url and "lemanbleu.ch" in response.url and not state["captured"]:
                if response.status == 200:
                    content_type = response.headers.get("content-type", "").lower()
                    # On cible le document principal
                    if "html" in content_type or "json" in content_type:
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
                print("⚠️ Le fichier spécifique n'a pas été intercepté séparément.")
                print("📦 Sauvegarde du HTML complet par défaut...")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page.content())
        except Exception as e:
            print(f"❌ Erreur : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    target_url = "https://www.lemanbleu.ch/fr/Actualite/Suisse/Incendie-dans-une-entreprise-a-Menznau-LU.html"
    intercept_lemanbleu_file(target_url)