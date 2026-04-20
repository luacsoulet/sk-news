import json
import re
import os
import html
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def reparer_encodage(text):
    """Répare le Mojibake (confusion UTF-8/Latin-1)"""
    if not text: return ""
    try:
        # Tente de restaurer les accents brisés (ex: Ã© -> é)
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    text = text.replace('Â', '')
    text = text.replace('\xa0', ' ')
    return text

def nettoyer_texte_enrichi(raw_text):
    """
    Transforme les balises HTML en Markdown (##) avant de supprimer le reste.
    (Ta logique d'origine conservée)
    """
    if not raw_text: return ""
    
    # 1. Décodage HTML
    text = html.unescape(raw_text)
    
    # 2. RÉPARATION DES ACCENTS
    text = reparer_encodage(text)
    
    # 3. FORMATAGE DES TITRES (h2 -> ##, h3 -> ###)
    # On cherche <h2>Texte</h2> et on remplace par \n## Texte\n
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n\n## \1\n\n', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n\n### \1\n\n', text, flags=re.IGNORECASE | re.DOTALL)
    
    # 4. Nettoyage des balises restantes
    text = re.sub(r'<[^>]+>', '', text)
    
    # 5. Normalisation des espaces
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique La Tribune (Next.js + JSON-LD).
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION LA TRIBUNE : {url} ---")
    
    # Initialisation
    article_data = {
        "title": "Titre non trouvé",
        "description": "",
        "content": "",
        "article_url": url,
        "is_paywall": False,
        "news_source_id": int(source_id),
        "created_at": ""
    }

    # --- ÉTAPE 1 : MÉTADONNÉES (JSON-LD) ---
    json_ld_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html_content, re.DOTALL)
    for block in json_ld_blocks:
        try:
            data = json.loads(block.strip())
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "NewsArticle":
                    article_data["title"] = item.get("headline", "").upper()
                    article_data["description"] = item.get("description", "")
                    
                    # Date publiée : JJ-MM-AAAA HH:MM
                    date_raw = item.get("datePublished")
                    if date_raw:
                        try:
                            dt = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
                            article_data["created_at"] = dt.strftime("%d-%m-%Y %H:%M")
                        except: pass
                    
                    # Détection Paywall
                    if item.get("isAccessibleForFree") is False:
                        article_data["is_paywall"] = True
                    break
        except: continue

    print(f"📌 Titre : {article_data['title'][:50]}...")

    # --- ÉTAPE 2 : CORPS ENRICHI (Regex Next.js) ---
    # Ta logique : on cherche les champs "html" dans le JSON de la page
    print("🔍 Extraction des segments HTML dans le code source...")
    body_segments = []
    
    # Regex pour trouver tous les champs \"html\":\"...\"
    pattern_html = r'\\"html\\":\\"(.*?)\\"'
    segments = re.findall(pattern_html, html_content)
    
    for seg in segments:
        # Nettoyage des échappements Unicode et HTML (Ta logique)
        clean_seg = seg.replace('\\u003c', '<').replace('\\u003e', '>').replace('\\u0026', '&').replace('\\"', '"')
        body_segments.append(clean_seg)

    # Fusion et nettoyage final du corps
    corps_final = "\n\n".join([nettoyer_texte_enrichi(p) for p in body_segments])
    
    # Sécurité : si la méthode Next.js ne donne rien, on peut avoir un fallback ici
    if not corps_final:
        print("⚠️ Méthode Next.js vide, vérification du conteneur HTML classique...")
        soup = BeautifulSoup(html_content, 'html.parser')
        article_div = soup.find('div', class_='article-body')
        if article_div:
            corps_final = nettoyer_texte_enrichi(article_div.get_text())

    article_data["content"] = corps_final

    # Sécurité Date
    if not article_data["created_at"]:
        article_data["created_at"] = datetime.now().strftime("%d-%m-%Y %H:%M")

    print(f"💰 Paywall : {'OUI' if article_data['is_paywall'] else 'NON'}")
    print(f"📏 Taille finale : {len(article_data['content'])} caractères.")
    print(f"--- ✅ FIN EXTRACTION LA TRIBUNE ---\n")
    
    return article_data

# --- TEST LOCAL ---
if __name__ == "__main__":
    import os
    file_test = os.path.join(os.path.dirname(__file__), "source_article_brute.txt")
    if os.path.exists(file_test):
        with open(file_test, "r", encoding="utf-8") as f:
            res = get_article_data(f.read(), "https://www.latribune.fr/test", 1)
            import pprint
            pprint.pprint(res)