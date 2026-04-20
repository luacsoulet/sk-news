import time
import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_bfmtv_file(url):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    # --- ADAPTATION POUR BFMTV ---
    # On extrait l'identifiant à la fin du slug (ex: AB-202402270023)
    path = urlparse(url).path
    slug = path.split('/')[-1].replace('.html', '')
    article_id = slug.split('_')[-1] if '_' in slug else slug

    print(f"🔍 Identifiant BFMTV détecté : {article_id}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Flag pour ne capturer que le premier fichier pertinent
        state = {"captured": False}

        def handle_response(response):
            # On cherche le fichier qui contient l'ID final dans son URL
            if article_id in response.url and not state["captured"]:
                if response.status == 200:
                    print(f"🎯 Fichier source détecté : {response.url[:100]}...")
                    try:
                        data = response.text()
                        with open(filename, "w", encoding="utf-8") as f:
                            f.write(data)
                        print(f"✅ Source sauvegardée dans : {filename}")
                        state["captured"] = True
                    except:
                        pass

        page.on("response", handle_response)

        print(f"🚀 Navigation vers : {url}")
        try:
            # On attend networkidle pour laisser les requêtes de données passer
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(5) 
            
            if not state["captured"]:
                print("⚠️ Interception réseau échouée. Sauvegarde directe du HTML de la page...")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page.content())
        except Exception as e:
            print(f"❌ Erreur : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    target_url = "https://www.bfmtv.com/economie/replay-emissions/hashtag-jmleco/swiss-krono-expert-mondial-dans-le-domaine-de-la-construction-bois_AB-202402270023.html"
    intercept_bfmtv_file(target_url)