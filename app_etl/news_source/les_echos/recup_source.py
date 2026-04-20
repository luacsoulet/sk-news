import sys
import time
import os
import re
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def intercept_lesechos_from_google(google_url):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="fr-FR"
        )
        page = context.new_page()

        print(f"📡 Navigation vers Google News...")
        try:
            # 1. On va sur le lien Google News
            page.goto(google_url)

            # 2. Gestion du mur de consentement Google
            if "consent.google" in page.url:
                print("🛡️ Validation du consentement Google...")
                try:
                    # On attend que le bouton soit visible et on clique
                    button = page.get_by_role("button", name=re.compile(r"Tout accepter|J'accepte|Tout autoriser", re.IGNORECASE))
                    button.wait_for(timeout=5000)
                    button.click()
                except:
                    print("⚠️ Bouton de consentement non cliquable, on attend la redirection auto...")

            # 3. ATTENTE CRITIQUE DE LA MISE À JOUR DE LA BARRE D'URL
            print("⏳ Attente que la barre d'adresse passe sur Les Echos...")
            try:
                # Cette fonction attend que l'URL change pour contenir 'lesechos.fr'
                page.wait_for_url(lambda url: "lesechos.fr" in url, timeout=20000)
                real_url = page.url
                print(f"✅ URL finale détectée dans la barre d'adresse : {real_url}")
            except Exception as e:
                print(f"⚠️ Timeout ou erreur de redirection : {page.url}")
                real_url = page.url

            # 4. EXTRACTION DE L'ID DEPUIS LA VRAIE URL
            path = urlparse(real_url).path.strip('/')
            match = re.search(r'(\d+)$', path)
            article_id = match.group(1) if match else "NOT_FOUND"
            print(f"🔍 ID Article : {article_id}")

            # 5. INTERCEPTION DES FLUX (Listener)
            state = {"captured": False}
            def handle_response(response):
                if article_id != "NOT_FOUND" and article_id in response.url and not state["captured"]:
                    if response.status == 200:
                        ctype = response.headers.get("content-type", "").lower()
                        if "html" in ctype or "json" in ctype:
                            print(f"🎯 Flux réseau intercepté !")
                            try:
                                with open(filename, "w", encoding="utf-8") as f:
                                    f.write(response.text())
                                state["captured"] = True
                            except: pass

            page.on("response", handle_response)

            # 6. RECHARGEMENT FINAL SUR L'URL RÉSOLUE
            # Maintenant qu'on est sur la bonne URL, on recharge pour déclencher le listener
            page.goto(real_url, wait_until="networkidle", timeout=60000)
            time.sleep(2)

            if not state["captured"]:
                print("⚠️ Flux spécifique non capturé, sauvegarde du HTML de la page actuelle...")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page.content())
            
            print(f"✅ Opération terminée. Fichier source : {filename}")

        except Exception as e:
            print(f"❌ Erreur générale : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        intercept_lesechos_from_google(sys.argv[1])
    else:
        print("❌ Paramètre manquant (URL Google News).")