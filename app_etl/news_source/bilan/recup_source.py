import time
import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_first_story_file(url):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    # On extrait l'ID pour être sûr de ne pas rater le fichier
    path = urlparse(url).path
    article_id = path.split('-')[-1] if '-' in path else path.split('/')[-1]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context()
        page = context.new_page()

        # Variable pour arrêter l'interception après le premier succès
        state = {"captured": False}

        def handle_response(response):
            # CONDITION : Dossier "story" + ID de l'article + Pas encore capturé
            if "/story/" in response.url and article_id in response.url and not state["captured"]:
                if response.status == 200:
                    print(f"🎯 Cible prioritaire détectée : {response.url}")
                    try:
                        data = response.text()
                        with open(filename, "w", encoding="utf-8") as f:
                            f.write(data)
                        print(f"✅ Premier fichier 'story' sauvegardé.")
                        state["captured"] = True # On verrouille pour ne plus rien prendre
                    except Exception as e:
                        print(f"⚠️ Erreur lecture : {e}")

        page.on("response", handle_response)

        print(f"🚀 Navigation vers l'article...")
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Petite sécurité : on attend 3 secondes pour être sûr que l'écriture est finie
            time.sleep(3) 
            
            if not state["captured"]:
                print("❌ Le fichier spécifié n'a pas été trouvé dans le flux réseau.")
            else:
                print("🏁 Mission terminée. Vous pouvez fermer.")
                
        except Exception as e:
            print(f"❌ Erreur : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    target_url = "https://www.bilan.ch/story/ines-kaindl-benes-300-plus-riches-995884082798"
    intercept_first_story_file(target_url)