import time
import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_watson_file(url):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    # --- ADAPTATION POUR WATSON.CH ---
    # On extrait le slug ou l'ID de l'URL (713675795)
    path = urlparse(url).path
    slug = path.split('/')[-1]
    article_id = slug.split('-')[0] if '-' in slug else slug

    print(f"🔍 Identifiant Watson détecté : {article_id}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        state = {"captured": False}

        def handle_response(response):
            # On cherche le fichier qui contient l'ID dans l'URL
            if article_id in response.url and not state["captured"]:
                if response.status == 200:
                    content_type = response.headers.get("content-type", "").lower()
                    # On cible le HTML ou le JSON de données
                    if "html" in content_type or "json" in content_type:
                        print(f"🎯 Source interceptée : {response.url[:100]}...")
                        try:
                            data = response.text()
                            with open(filename, "w", encoding="utf-8") as f:
                                f.write(data)
                            print(f"✅ Fichier sauvegardé.")
                            state["captured"] = True
                        except: pass

        page.on("response", handle_response)

        print(f"🚀 Navigation vers : {url}")
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(5) 
            
            if not state["captured"]:
                print("⚠️ Interception réseau échouée. Sauvegarde du contenu de la page par défaut...")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page.content())
        except Exception as e:
            print(f"❌ Erreur : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    target_url = "https://www.watson.ch/fr/suisse/incendie/713675795-menznau-lu-le-site-de-la-societe-swiss-krono-est-en-flammes"
    intercept_watson_file(target_url)