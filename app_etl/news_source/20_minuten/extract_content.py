import json
import re
import html
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def nettoyer_texte(raw_text):
    """Nettoyage final et normalisation des espaces"""
    if not raw_text: return ""
    # Décodage HTML (ex: &nbsp; -> espace)
    text = html.unescape(raw_text)
    # Suppression des caractères de contrôle et normalisation
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\r")
    # Nettoyage des lignes
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def extraire_donnees_article(html_content, article_url, news_source_id):
    """
    Extrait les données structurées depuis le HTML brut.
    Retourne un dictionnaire prêt pour l'insertion en base de données.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # --- INITIALISATION DES VARIABLES ---
    data_final = {
        "title": "Titre inconnu",
        "description": "",
        "content": "",
        "article_url": article_url,
        "is_paywall": False,
        "news_source_id": news_source_id,
        "created_at": datetime.now().strftime("%d-%m-%Y %H:%M") # Date par défaut
    }

    # --- 1. EXTRACTION DEPUIS LE JSON-LD (Métadonnées) ---
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            raw_data = json.loads(script.string.strip())
            items = raw_data if isinstance(raw_data, list) else [raw_data]
            
            for item in items:
                if item.get("@type") == "NewsArticle":
                    # Titre et Description
                    data_final["title"] = nettoyer_texte(item.get("headline", ""))
                    data_final["description"] = nettoyer_texte(item.get("description", ""))
                    
                    # Paywall (Souvent indiqué par isAccessibleForFree)
                    # Si False, c'est un paywall
                    if item.get("isAccessibleForFree") is False:
                        data_final["is_paywall"] = True
                    
                    # Date de création
                    date_raw = item.get("datePublished") or item.get("dateCreated")
                    if date_raw:
                        # Parsing de la date ISO (ex: 2024-03-20T08:30:00Z)
                        dt = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
                        data_final["created_at"] = dt.strftime("%d-%m-%Y %H:%M")
                    
                    # Corps de secours (si le HTML échoue)
                    corps_json = item.get("articleBody", "")
                    break
        except:
            continue

    # --- 2. EXTRACTION DU CORPS DEPUIS LE HTML (Pour la structure) ---
    # Recherche des paragraphes (adapté à l'exemple 20min précédent)
    paragraphes_html = soup.find_all('p', class_=re.compile(r'iaMroo'))
    
    if paragraphes_html:
        corps_liste = [p.get_text().strip() for p in paragraphes_html if len(p.get_text()) > 20]
        data_final["content"] = nettoyer_texte("\n\n".join(corps_liste))
    elif 'corps_json' in locals() and corps_json:
        # Si pas de paragraphes HTML, on utilise le bloc compact du JSON
        # On peut réutiliser ta fonction aérer_bloc_compact ici si besoin
        data_final["content"] = nettoyer_texte(corps_json)

    return data_final

# --- EXEMPLE D'UTILISATION ---
if __name__ == "__main__":
    # Simulation de lecture du fichier brut
    with open("source_article_brute.txt", "r", encoding="utf-8") as f:
        html_brut = f.read()

    # Appel de la fonction
    resultat = extraire_donnees_article(
        html_content=html_brut, 
        article_url="https://www.20min.ch/fr/story/...", 
        news_source_id=12  # L'ID récupéré sur Supabase
    )

    # Affichage du dictionnaire final
    print(json.dumps(resultat, indent=4, ensure_ascii=False))