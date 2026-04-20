import time
import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_blick_file(url):
    # Dossier actuel
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    # --- ADAPTATION POUR BLICK.CH ---
    # On extrait le slug (ex: 12000-metres-carres-sont-en-feu...id18823163)
    path = urlparse(url).path
    slug = path.split('/')[-1].replace('.html', '')
    
    print(f"🔍 Cible réseau détectée : {slug}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Flag pour ne capturer que le premier fichier
        state = {"captured": False}

        def handle_response(response):
            # On cherche le fichier qui contient le slug dans l'URL
            if slug in response.url and not state["captured"]:
                if response.status == 200:
                    # On vérifie que c'est bien le document ou du JSON (Next.js data)
                    content_type = response.headers.get("content-type", "").lower()
                    if "html" in content_type or "json" in content_type:
                        print(f"🎯 Fichier source détecté : {response.url[:100]}...")
                        try:
                            data = response.text()
                            with open(filename, "w", encoding="utf-8") as f:
                                f.write(data)
                            print(f"✅ Fichier sauvegardé dans : {filename}")
                            state["captured"] = True
                        except: pass

        page.on("response", handle_response)

        print(f"🚀 Navigation vers : {url}")
        try:
            # On attend networkidle pour laisser Next.js charger ses données
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(5) 
            
            if not state["captured"]:
                print("⚠️ Interception réseau spécifique échouée. Sauvegarde du contenu de la page par défaut...")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page.content())
        except Exception as e:
            print(f"❌ Erreur : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    target_url = "https://www.blick.ch/fr/suisse/12000-metres-carres-sont-en-feu-incendie-dans-lusine-a-bois-swiss-krono-a-menznau-lu-id18823163.html"
    intercept_blick_file(target_url)