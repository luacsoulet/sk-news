import time
import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_article_file(url):
    # On définit le chemin du fichier dans le dossier actuel du script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    # --- ADAPTATION POUR ACTU.FR ---
    # On extrait le nom du fichier de l'URL (le slug)
    path = urlparse(url).path
    # On enlève le ".html" et on récupère le dernier morceau après le "/"
    slug = path.split('/')[-1].replace('.html', '')
    
    # Si l'URL finit par un "/", on prend l'élément précédent
    if not slug:
        slug = path.split('/')[-2]
    
    # On garde seulement la partie après le dernier "_" (souvent l'ID unique) 
    # ou un morceau significatif pour le filtre
    filter_keyword = slug.split('_')[-1] if '_' in slug else slug

    print(f"🔍 Mot-clé de filtrage détecté : {filter_keyword}")

    with sync_playwright() as p:
        # On lance le navigateur (headless=False pour passer les sécurités)
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Cache le mode automate
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        def handle_response(response):
            # On cherche la réponse réseau qui contient l'ID ou le slug de l'article
            if filter_keyword in response.url and response.status == 200:
                print(f"🎯 Source détectée : {response.url[:100]}...")
                try:
                    data = response.text()
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(data)
                    print(f"✅ Fichier brut sauvegardé dans : {filename}")
                except Exception as e:
                    print(f"⚠️ Erreur lors de la lecture de la source : {e}")

        # On active l'écouteur
        page.on("response", handle_response)

        print(f"🚀 Navigation vers : {url}")
        try:
            # On attend que le réseau soit calme pour être sûr d'avoir capturé le fichier
            page.goto(url, wait_until="networkidle", timeout=60000)
            print("⏳ Attente finale pour captures réseaux...")
            time.sleep(5) 
        except Exception as e:
            print(f"❌ Erreur de navigation : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    # URL de l'article Actu.fr
    target_url = "https://actu.fr/nouvelle-aquitaine/fargues-sur-ourbise_47093/un-geant-mondial-de-la-fabrication-en-bois-abandonne-son-projet-dusine-titanesque-en-lot-et-garonne_63748734.html"
    intercept_article_file(target_url)