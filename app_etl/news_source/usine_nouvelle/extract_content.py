import json
import re
import os
import html
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def decrypter_texte(raw_text):
    """Décode les entités HTML et nettoie les résidus (Ta logique)"""
    if not raw_text: return ""
    # Suppression des balises HTML éventuellement présentes dans les chaînes JSON
    text = re.sub(r'<[^>]+>', '', raw_text)
    text = html.unescape(text)
    # Nettoyage des espaces insécables et normalisation
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def est_un_titre_deguise(texte):
    """Détecte si un bloc de texte est un titre (court et sans point final)"""
    t = texte.strip()
    if len(t) < 85 and not t.endswith('.') and len(t) > 3:
        return True
    return False

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique L'Usine Nouvelle (Fusion Engine).
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION L'USINE NOUVELLE : {url} ---")
    
    # Structure de retour par défaut
    article_data = {
        "title": "Titre non trouvé",
        "description": "",
        "content": "",
        "article_url": url,
        "is_paywall": False,
        "news_source_id": int(source_id),
        "created_at": ""
    }

    try:
        # 1. RÉCUPÉRATION DU JSON CACHÉ (Fusion.globalContent)
        print("🔍 Recherche des données Fusion JSON...")
        pattern = re.compile(r'Fusion\.globalContent\s*=\s*(\{.*?\});', re.DOTALL)
        match = pattern.search(html_content)
        
        if not match:
            print("❌ Impossible de trouver le bloc Fusion.globalContent.")
            # Fallback Date si le JSON échoue
            article_data["created_at"] = datetime.now().strftime("%d-%m-%Y %H:%M")
            return article_data

        data = json.loads(match.group(1))
        print("✅ Données Fusion décodées avec succès.")

        # 2. EXTRACTION DU TITRE ET RÉSUMÉ
        article_data["title"] = decrypter_texte(data.get("headlines", {}).get("basic", ""))
        article_data["description"] = decrypter_texte(data.get("subheadlines", {}).get("basic", ""))
        print(f"📌 Titre : {article_data['title'][:50]}...")

        # 3. DATE (display_date ou publish_date chez Fusion)
        date_raw = data.get("display_date") or data.get("publish_date")
        if date_raw:
            try:
                # Format ISO (ex: 2024-03-17T08:00:00Z)
                dt = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
                article_data["created_at"] = dt.strftime("%d-%m-%Y %H:%M")
            except: pass
        
        if not article_data["created_at"]:
            article_data["created_at"] = datetime.now().strftime("%d-%m-%Y %H:%M")

        # 4. DÉTECTION PAYWALL
        # Sur Fusion, l'info est souvent dans 'credits' ou des flags spécifiques
        if data.get("planning", {}).get("scheduling", {}).get("will_pub_be_locked"):
            article_data["is_paywall"] = True
        
        # 5. EXTRACTION DU CORPS (Parcours de content_elements)
        corps_final = []
        elements = data.get("content_elements", [])
        print(f"📖 Analyse de {len(elements)} éléments de contenu JSON...")

        for el in elements:
            if el.get("type") == "text":
                txt_propre = decrypter_texte(el.get("content", ""))
                
                if not txt_propre or len(txt_propre) < 3:
                    continue

                # Vérification si c'est un titre de sous-partie (Ta logique)
                if est_un_titre_deguise(txt_propre):
                    corps_final.append(f"## {txt_propre}")
                else:
                    corps_final.append(txt_propre)
        
        article_data["content"] = "\n\n".join(corps_final)
        print(f"📏 Taille finale : {len(article_data['content'])} caractères.")
        print(f"💰 Paywall : {'OUI' if article_data['is_paywall'] else 'NON'}")

    except Exception as e:
        print(f"💥 Erreur lors de l'extraction Fusion : {e}")
        if not article_data["created_at"]:
            article_data["created_at"] = datetime.now().strftime("%d-%m-%Y %H:%M")

    print(f"--- ✅ FIN EXTRACTION L'USINE NOUVELLE ---\n")
    return article_data

# --- TEST LOCAL ---
if __name__ == "__main__":
    import os
    file_test = os.path.join(os.path.dirname(__file__), "source_article_brute.txt")
    if os.path.exists(file_test):
        with open(file_test, "r", encoding="utf-8") as f:
            res = get_article_data(f.read(), "https://www.usinenouvelle.com/article/test", 1)
            import pprint
            pprint.pprint(res)