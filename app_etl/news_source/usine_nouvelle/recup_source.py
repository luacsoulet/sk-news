import time
import os
from playwright.sync_api import sync_playwright

def intercept_usinenouvelle_file(url):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Laisse à False pour voir si le captcha s'affiche
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print(f"🚀 Navigation vers : {url}")
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # --- VÉRIFICATION ANTI-BOT ---
            if "Device check" in page.title():
                print("⚠️ Blocage DataDome détecté. Résolvez le captcha manuellement dans la fenêtre...")
                # On attend que l'URL change ou que le titre ne soit plus "Device check"
                page.wait_for_function("document.title !== 'Device check | Usine Nouvelle'", timeout=120000)
            
            time.sleep(5) # Laisser le contenu final s'afficher

            # Sauvegarde de TOUT le code source
            html_content = page.content()
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            print(f"✅ Source réelle sauvegardée dans : {filename}")
        except Exception as e:
            print(f"❌ Erreur : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    target_url = "https://www.usinenouvelle.com/article/dans-le-loiret-swiss-krono-inaugure-de-nouvelles-installations-decarbonees.N2218063"
    intercept_usinenouvelle_file(target_url)