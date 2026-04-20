import time
import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_latribune_file(url):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    # On extrait l'identifiant de l'article (ex: 1006204)
    path = urlparse(url).path
    slug = path.split('/')[-1].replace('.html', '')
    article_id = slug.split('-')[-1] if '-' in slug else slug

    print(f"🔍 Identifiant cible détecté : {article_id}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Flag pour ne prendre QUE le premier fichier
        state = {"captured": False}

        def handle_response(response):
            # On cherche le fichier qui contient l'ID et qui appartient au domaine latribune
            if article_id in response.url and "latribune.fr" in response.url and not state["captured"]:
                # On vérifie que c'est bien le document principal ou un fetch de données
                if response.status == 200:
                    print(f"🎯 Fichier principal détecté : {response.url[:100]}...")
                    try:
                        data = response.text()
                        with open(filename, "w", encoding="utf-8") as f:
                            f.write(data)
                        print(f"✅ Premier fichier source sauvegardé dans : {filename}")
                        state["captured"] = True
                    except:
                        pass

        page.on("response", handle_response)

        print(f"🚀 Navigation vers : {url}")
        try:
            # On attend networkidle pour être sûr que le chargement est complet
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(5) 
            
            if not state["captured"]:
                print("⚠️ Le fichier n'a pas été intercepté. Tentative de sauvegarde directe du contenu de la page...")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page.content())
                print("✅ Contenu HTML de la page sauvegardé par défaut.")
                
        except Exception as e:
            print(f"❌ Erreur : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    target_url = "https://www.latribune.fr/business/industrie/2024-09-16/dans-la-foret-des-landes-un-projet-d-usine-de-panneaux-sort-du-bois-1006204.html"
    intercept_latribune_file(target_url)