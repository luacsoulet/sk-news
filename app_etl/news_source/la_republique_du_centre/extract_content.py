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
        # Tente de corriger le Mojibake (UTF-8 lu comme du Latin-1)
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    text = text.replace('Â', '')
    text = text.replace('\xa0', ' ')
    return text

def structurer_le_corps(text):
    """
    Transforme le bloc compact en paragraphes aérés 
    et place les ## au bon endroit (Ta logique Regex).
    """
    if not text: return ""

    # 1. REPERAGE DES SOUS-TITRES
    # On cherche : un point + espace + guillemet + texte + guillemet + espace + Majuscule
    text = re.sub(r'\.\s+["«]([^"»]{5,80})["»]\s+([A-Z])', r'.\n\n## \1\n\n\2', text)

    # 2. SÉPARATION DES PARAGRAPHES COLLÉS
    # Un point (ou ! ou ?) suivi d'un espace et d'une lettre Majuscule
    text = re.sub(r'([\.!\?])\s+([A-Z])', r'\1\n\n\2', text)
    
    # 3. GESTION DES CITATIONS LONGUES
    text = re.sub(r'["»]\s+([A-Z])', r'"\n\n\1', text)

    # 4. NETTOYAGE DES ESPACES
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def get_article_data(html_content, url, source_id):
    """
    Extrait les données exclusivement depuis le bloc JSON-LD 'articleJsonLd'.
    Retourne un dictionnaire exportable pour Supabase avec logs terminal.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION JSON-LD : {url} ---")
    
    # Initialisation des variables
    article_data = {
        "title": "Titre non trouvé",
        "description": "",
        "content": "",
        "article_url": url,
        "is_paywall": False,
        "news_source_id": int(source_id),
        "created_at": datetime.now().strftime("%d-%m-%Y %H:%M")
    }

    try:
        # 1. Extraction du bloc JSON-LD spécifique par Regex (Ta logique)
        match = re.search(r'<script id="articleJsonLd" type="application/ld\+json">(.*?)</script>', html_content, re.DOTALL)
        
        if not match:
            print("❌ Erreur : Impossible de trouver le script id='articleJsonLd'.")
            return article_data

        # 2. Parsing du JSON
        data = json.loads(match.group(1).strip())
        print("✅ Bloc JSON-LD trouvé et décodé.")

        # 3. Extraction et Nettoyage
        article_data["title"] = reparer_encodage(html.unescape(data.get("headline", "")))
        article_data["description"] = reparer_encodage(html.unescape(data.get("description", "")))
        
        # Paywall (Clé standard isAccessibleForFree)
        if data.get("isAccessibleForFree") is False:
            article_data["is_paywall"] = True
            
        # Date (Formatage JJ-MM-AAAA HH:MM)
        date_raw = data.get("datePublished") or data.get("dateCreated")
        if date_raw:
            try:
                dt = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
                article_data["created_at"] = dt.strftime("%d-%m-%Y %H:%M")
            except:
                pass

        # 4. Structuration du corps
        corps_brut = html.unescape(data.get("articleBody", ""))
        article_data["content"] = structurer_le_corps(reparer_encodage(corps_brut))

        print(f"📌 Titre : {article_data['title'][:50]}...")
        print(f"💰 Paywall : {'OUI' if article_data['is_paywall'] else 'NON'}")
        print(f"📏 Taille finale : {len(article_data['content'])} caractères.")

    except Exception as e:
        print(f"💥 Erreur lors de l'extraction JSON-LD : {e}")

    print(f"--- ✅ FIN EXTRACTION JSON-LD ---\n")
    return article_data

# --- TEST LOCAL ---
if __name__ == "__main__":
    import os
    file_test = os.path.join(os.path.dirname(__file__), "source_article_brute.txt")
    if os.path.exists(file_test):
        with open(file_test, "r", encoding="utf-8") as f:
            res = get_article_data(f.read(), "https://journal-json.com/test", 1)
            import pprint
            pprint.pprint(res)