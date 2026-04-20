import time
import os
import re
from playwright.sync_api import sync_playwright

def extraire_id_url(url):
    """Extrait automatiquement l'identifiant numérique à la fin de l'URL"""
    # Cherche une suite de chiffres avant le .html ou à la fin de la chaîne
    match = re.search(r'(\d+)(?:\.html)?/?$', url)
    if match:
        return match.group(1)
    return None

def intercept_article_file(url):
    # Préparation des fichiers
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "source_article_brute.txt")
    
    # Extraction automatique de l'ID
    article_id = extraire_id_url(url)
    
    if not article_id:
        print("❌ Impossible de trouver un ID à la fin de l'URL fournie.")
        return

    print(f"🔍 ID détecté : {article_id}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Variable pour savoir si on a déjà capturé le fichier (évite les doublons)
        state = {"captured": False}

        def handle_response(response):
            # On cherche l'ID dans l'URL de la réponse réseau
            if article_id in response.url and not state["captured"]:
                # On vérifie que c'est bien du texte (HTML ou JSON) et pas une image/pub
                content_type = response.headers.get("content-type", "").lower()
                if "text" in content_type or "json" in content_type:
                    print(f"🎯 Fichier source intercepté : {response.url[:80]}...")
                    try:
                        data = response.text()
                        with open(filename, "w", encoding="utf-8") as f:
                            f.write(data)
                        print(f"✅ Contenu sauvegardé dans : {filename}")
                        state["captured"] = True
                    except Exception as e:
                        print(f"⚠️ Erreur lors de la lecture du fichier : {e}")

        page.on("response", handle_response)

        print(f"🚀 Navigation vers l'article...")
        try:
            # On attend que le réseau soit calme pour être sûr d'avoir tout intercepté
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Petite pause de sécurité si l'interception n'est pas encore faite
            if not state["captured"]:
                time.sleep(5)
                
            if not state["captured"]:
                print("⚠️ L'interception spécifique a échoué. Sauvegarde du contenu de la page par défaut.")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page.content())
                    
        except Exception as e:
            print(f"❌ Erreur de navigation : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    # Test avec une URL de La Rep ou Les Echos
    url_test = "https://www.larep.fr/chilleurs-aux-bois-45170/actualites/un-label-remis-aux-employeurs-partenaires-des-sapeurs-pompiers-du-loiret_14577296/"
    intercept_article_file(url_test)