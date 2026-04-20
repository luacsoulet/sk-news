import time
import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_article_file(url):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    # On extrait le "slug" de l'article pour filtrer les fichiers réseau
    # Exemple: "une-decision-definitive-..."
    path = urlparse(url).path
    slug = path.split('/')[-1].replace('.php', '')
    if not slug: # cas où l'url finit par /
        slug = path.split('/')[-2]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context()
        page = context.new_page()

        def handle_response(response):
            # On cherche le fichier qui contient le nom de l'article
            if slug in response.url and response.status == 200:
                print(f"🎯 Fichier source détecté : {response.url}")
                try:
                    data = response.text()
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(data)
                    print(f"✅ Fichier sauvegardé.")
                except: pass

        page.on("response", handle_response)

        try:
            print(f"🚀 Navigation vers : {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(10) 
        except Exception as e:
            print(f"❌ Erreur : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    target_url = "https://www.sudouest.fr/lieux/lot-et-garonne/fargues-sur-ourbise/usine-geante-de-swiss-krono-dans-les-landes-de-gascogne-un-projet-comme-ca-c-est-inespere-24877465.php"
    intercept_article_file(target_url)