import json
import re
import os
import html
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def nettoyer_bloc_texte(raw_text):
    """Nettoie spécifiquement les fragments de texte extraits du JSON (Ta logique)"""
    if not raw_text: return ""
    
    # 1. Décodage des entités HTML
    text = html.unescape(raw_text)
    
    # 2. Remplacement des balises par des sauts de ligne (Ta logique Regex)
    text = re.sub(r'<(p|br|div|h1|h2|h3)[^>]*>', '\n\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    
    # 3. Réparation de l'encodage si nécessaire
    try:
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass

    # 4. Nettoyage des espaces et sauts de ligne
    text = text.replace('\xa0', ' ')
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique Blick (Scan JSON __NEXT_DATA__).
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION BLICK : {url} ---")
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

    # 1. EXTRACTION DU TITRE ET DESCRIPTION (Balises Meta)
    title_tag = soup.find('title')
    if title_tag:
        article_data["title"] = nettoyer_bloc_texte(title_tag.get_text().split(' - Blick')[0])
    
    desc_meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    if desc_meta:
        article_data["description"] = nettoyer_bloc_texte(desc_meta.get('content'))

    print(f"📌 Titre : {article_data['title'][:50]}...")

    # 2. EXTRACTION DU CORPS (Scan du JSON __NEXT_DATA__)
    corps_complet = []
    script_next = soup.find('script', id='__NEXT_DATA__')
    
    if script_next:
        try:
            print("🔍 Analyse du bloc Next.js pour reconstruire l'article...")
            data = json.loads(script_next.string)
            
            # Fonction récursive pour trouver tous les champs "text" (Ta logique)
            def chercher_corps(obj):
                if isinstance(obj, dict):
                    # Détection du paywall dans le JSON si possible
                    if "isPaid" in obj: 
                        article_data["is_paywall"] = obj["isPaid"]
                    
                    # On vérifie si c'est un widget de texte
                    kind = obj.get("kind", [])
                    if isinstance(kind, list) and "text-body" in kind:
                        if "text" in obj:
                            corps_complet.append(obj["text"])
                    
                    for k, v in obj.items():
                        chercher_corps(v)
                elif isinstance(obj, list):
                    for item in obj:
                        chercher_corps(item)

            chercher_corps(data)
        except Exception as e:
            print(f"❌ Erreur lors du parsing JSON : {e}")
    else:
        print("⚠️ Bloc __NEXT_DATA__ introuvable. Extraction HTML classique impossible pour ce journal.")

    # 3. EXTRACTION DE LA DATE
    # Recherche dans les meta tags (Blick utilise souvent 'article:published_time')
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    date_str = ""
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            date_str = dt.strftime("%d-%m-%Y %H:%M")
        except:
            date_str = nettoyer_bloc_texte(raw_date)
    
    if not date_str:
        date_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    article_data["created_at"] = date_str
    article_data["content"] = "\n\n".join([nettoyer_bloc_texte(bloc) for bloc in corps_complet])
    
    print(f"💰 Paywall : {'OUI' if article_data['is_paywall'] else 'NON'}")
    print(f"📏 Taille finale : {len(article_data['content'])} caractères.")
    print(f"--- ✅ FIN EXTRACTION BLICK ---\n")
    
    return article_data

# --- TEST LOCAL ---
if __name__ == "__main__":
    import os
    file_test = os.path.join(os.path.dirname(__file__), "source_article_brute.txt")
    if os.path.exists(file_test):
        with open(file_test, "r", encoding="utf-8") as f:
            res = get_article_data(f.read(), "https://www.blick.ch/fr/test", 1)
            import pprint
            pprint.pprint(res)