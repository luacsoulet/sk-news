import time
import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_batiweb_file(url):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    # --- ADAPTATION POUR BATIWEB.COM ---
    # On extrait le slug (ex: swiss-krono-mise-tout-sur-le-developpement-durable-30839)
    path = urlparse(url).path
    slug = path.split('/')[-1]
    
    print(f"🔍 Cible réseau détectée : {slug}")

    with sync_playwright() as p:
        # Lancement du navigateur (headless=False pour voir la navigation)
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Flag pour ne capturer que le premier fichier pertinent
        state = {"captured": False}

        def handle_response(response):
            # On cherche l'URL qui contient le slug de l'article sur batiweb
            if slug in response.url and "batiweb.com" in response.url and not state["captured"]:
                if response.status == 200:
                    content_type = response.headers.get("content-type", "").lower()
                    # On cible le document principal ou les données JSON
                    if "html" in content_type or "json" in content_type:
                        print(f"🎯 Source interceptée : {response.url[:100]}...")
                        try:
                            data = response.text()
                            with open(filename, "w", encoding="utf-8") as f:
                                f.write(data)
                            print(f"✅ Source brute sauvegardée dans : {filename}")
                            state["captured"] = True
                        except: pass

        page.on("response", handle_response)

        print(f"🚀 Navigation vers : {url}")
        try:
            # On attend que le réseau soit inactif pour capturer les données dynamiques
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(5) 
            
            if not state["captured"]:
                print("⚠️ Interception spécifique échouée. Sauvegarde directe du HTML...")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page.content())
                print(f"✅ Contenu HTML sauvegardé par défaut.")
                
        except Exception as e:
            print(f"❌ Erreur : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    target_url = "https://www.batiweb.com/actualites/vie-des-societes/swiss-krono-mise-tout-sur-le-developpement-durable-30839"
    intercept_batiweb_file(target_url)