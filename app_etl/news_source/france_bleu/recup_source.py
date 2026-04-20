import time
import os
from playwright.sync_api import sync_playwright

def capturer_source_html(url):
    # Dossier et nom du fichier de sortie
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    with sync_playwright() as p:
        # Lancement du navigateur
        # headless=False permet de voir ce qui se passe
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Cache le fait que c'est un robot (évite les blocages PHP/JS)
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print(f"🚀 Connexion au site : {url}")
        
        try:
            # Navigation vers l'URL
            # "networkidle" attend que tout soit chargé (scripts, images, etc.)
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Petite pause pour laisser les scripts PHP s'exécuter
            time.sleep(5) 
            
            # RÉCUPÉRATION DU CODE SOURCE COMPLET (DOM Sérialisé)
            # C'est ici que l'on prend TOUT le code HTML de la page
            full_html_source = page.content()
            
            # Écriture dans le fichier texte
            with open(filename, "w", encoding="utf-8") as f:
                f.write(full_html_source)
            
            print(f"✅ SUCCÈS ! Le code source complet est sauvegardé.")
            print(f"📂 Fichier : {filename}")
            print(f"📏 Taille du fichier : {len(full_html_source)} caractères.")

        except Exception as e:
            print(f"❌ Erreur lors de la capture : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    # URL cible
    target_url = "https://www.francebleu.fr/centre-val-de-loire/loiret-45/sully-sur-loire/de-nombreux-pompiers-deployes-a-sully-sur-loire-pour-un-incendie-sur-le-site-de-swiss-krono-9311247"
    capturer_source_html(target_url)