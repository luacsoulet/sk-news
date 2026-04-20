import json
import re
import os
import html
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def reparer_encodage(text):
    """Répare les problèmes d'affichage Mojibake (ex: Ã© -> é)"""
    if not text: return ""
    try:
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    text = text.replace('Â', '')
    text = text.replace('\xa0', ' ')
    return text.strip()

def nettoyer_fragment(raw_text):
    """Nettoie le texte sans ajouter de sauts de ligne (Ta logique)"""
    if not raw_text: return ""
    text = html.unescape(raw_text)
    text = reparer_encodage(text)
    # On enlève les balises HTML résiduelles
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique pour Watson.
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION WATSON : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Structure de retour
    article_data = {
        "title": "Titre non trouvé",
        "description": "",
        "content": "",
        "article_url": url,
        "is_paywall": False,
        "news_source_id": int(source_id),
        "created_at": ""
    }

    # --- 1. EXTRACTION TITRE, RÉSUMÉ ET DATE (JSON-LD) ---
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            data = json.loads(script.string.strip())
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "NewsArticle":
                    article_data["title"] = nettoyer_fragment(item.get("headline", ""))
                    article_data["description"] = nettoyer_fragment(item.get("description", ""))
                    
                    # Date publiée : JJ-MM-AAAA HH:MM
                    date_raw = item.get("datePublished")
                    if date_raw:
                        dt = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
                        article_data["created_at"] = dt.strftime("%d-%m-%Y %H:%M")
                    
                    # Paywall (Watson est souvent gratuit, mais on vérifie)
                    if item.get("isAccessibleForFree") is False:
                        article_data["is_paywall"] = True
                    break
        except: continue

    # Fallback Titre/Desc si JSON-LD échoue
    if article_data["title"] == "Titre non trouvé":
        t_tag = soup.find('meta', property='og:title')
        article_data["title"] = nettoyer_fragment(t_tag['content']) if t_tag else "Titre non trouvé"
    
    print(f"📌 Titre : {article_data['title'][:50]}...")

    # --- 2. EXTRACTION DU CORPS (HTML sélectif) ---
    corps_final = []
    # Watson utilise watson-story__content pour le texte principal
    article_body = soup.find('article', class_='watson-story__content')
    
    if article_body:
        print("✅ Conteneur 'watson-story__content' détecté.")
        # On cherche les paragraphes et les titres
        for elem in article_body.find_all(['p', 'h2', 'h3'], recursive=True):
            
            # Ignorer les recommandations ou les encarts publicitaires (Ta logique)
            if elem.find_parent(['aside', 'div'], class_=['MoreAbout__MoreAboutWrapper', 'insert']):
                continue
            
            txt = nettoyer_fragment(elem.get_text())
            if not txt or len(txt) < 5:
                continue

            if elem.name in ['h2', 'h3']:
                corps_final.append(f"## {txt}")
            else:
                # On ignore les signatures d'agences courtes (sda/ats)
                if re.match(r'^\(.*\)$', txt) and len(txt) < 15:
                    continue
                corps_final.append(txt)
    else:
        print("❌ Erreur : Conteneur Watson introuvable.")

    article_data["content"] = "\n\n".join(corps_final)
    
    # Sécurité date
    if not article_data["created_at"]:
        article_data["created_at"] = datetime.now().strftime("%d-%m-%Y %H:%M")

    print(f"💰 Paywall : {'OUI' if article_data['is_paywall'] else 'NON'}")
    print(f"📏 Taille finale : {len(article_data['content'])} caractères.")
    print(f"--- ✅ FIN EXTRACTION WATSON ---\n")

    return article_data

# --- TEST LOCAL ---
if __name__ == "__main__":
    import os
    file_test = os.path.join(os.path.dirname(__file__), "source_article_brute.txt")
    if os.path.exists(file_test):
        with open(file_test, "r", encoding="utf-8") as f:
            res = get_article_data(f.read(), "https://www.watson.ch/fr/test", 1)
            import pprint
            pprint.pprint(res)