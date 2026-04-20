import time
import os
from playwright.sync_api import sync_playwright

def intercept_article_file(url):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # On injecte le code pour cacher le robot
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print(f"🚀 Navigation vers : {url}")
        try:
            # Sur ce site, on récupère directement le HTML de la page car 
            # les données structurées y sont souvent injectées.
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5) 
            
            html_content = page.content()
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            print(f"✅ Page sauvegardée dans : {filename}")
        except Exception as e:
            print(f"❌ Erreur : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    target_url = "https://www.lepetitjournal.net/47-lot-et-garonne/2024/09/23/swiss-krono-presente-son-projet-orpinia/"
    intercept_article_file(target_url)