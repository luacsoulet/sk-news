import re
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
    return text

def nettoyer_texte(raw_text):
    """Nettoyage final : Décodage + Suppression balises + Espaces"""
    if not raw_text: return ""
    text = html.unescape(raw_text)
    text = reparer_encodage(text)
    text = re.sub(r'<[^>]+>', '', text)
    
    forbidden = ["Partagez sur Facebook", "Partagez sur Twitter", "Partagez par Mail", 
                 "Copiez/Collez le Lien", "Copié !", "Enregistrer l'article"]
    for phrase in forbidden:
        text = text.replace(phrase, "")

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction Actu.fr retournant un dictionnaire.
    Affiche les logs de progression dans le terminal.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. NETTOYAGE DES BLOCS (Ta logique)
    classes_a_supprimer = [
        "ac-article-actions", "ac-article-actions__share", 
        "ac-banner-ad", "ac-article-tag", "ac-article-date",
        "sr", "ac-article-social__msg", "ac-article-footer"
    ]
    for tag in soup.find_all(class_=classes_a_supprimer):
        tag.decompose()

    # 2. TITRE
    title_tag = soup.find('h1')
    titre_final = nettoyer_texte(title_tag.get_text()) if title_tag else "Titre non trouvé"
    print(f"📌 Titre : {titre_final[:50]}...")

    # 3. MÉTADONNÉES (Description, Date, Paywall)
    # Description
    desc_meta = soup.find('meta', attrs={'name': 'description'})
    description = nettoyer_texte(desc_meta.get('content')) if desc_meta else ""
    
    # Date (recherche balise time ou classe date)
    date_tag = soup.find('time') or soup.find(class_='ac-article-date')
    date_str = ""
    if date_tag:
        raw_date = date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            date_str = dt.strftime("%d-%m-%Y %H:%M")
        except:
            date_str = nettoyer_texte(raw_date)
    
    if not date_str:
        date_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    # Paywall (Détection par classe premium)
    is_paywall = False
    if soup.find(class_=re.compile(r'premium|paywall|register-gate')):
        is_paywall = True
    print(f"💰 Paywall : {'OUI' if is_paywall else 'NON'}")

    # 4. CORPS DE L'ARTICLE (Ta logique ## et *)
    body_container = soup.find('article', class_='js-article-inner') or soup.find('div', class_='ac-article-content')
    
    contenu_final = []
    if body_container:
        elements = body_container.find_all(['p', 'h2', 'li'])
        print(f"📖 Analyse de {len(elements)} éléments HTML...")
        
        skip_count = 0  
        for element in elements:
            txt_brut = element.get_text().strip()

            if "Personnalisez votre actualité" in txt_brut:
                break

            if "À lire aussi" in txt_brut or "À LIRE AUSSI" in txt_brut:
                skip_count = 2 
                continue

            if skip_count > 0:
                skip_count -= 1
                continue

            propre = nettoyer_texte(txt_brut)
            if propre and len(propre) > 5:
                if element.name == 'h2':
                    contenu_final.append(f"## {propre}")
                elif element.name == 'li':
                    contenu_final.append(f"* {propre}")
                else:
                    contenu_final.append(propre)
    
    corps_final_texte = "\n\n".join(contenu_final)
    print(f"📏 Taille du contenu : {len(corps_final_texte)} caractères.")

    # 5. RÉSULTAT EXPORTABLE
    print(f"--- ✅ FIN EXTRACTION ---\n")
    
    return {
        "title": titre_final,
        "description": description,
        "content": corps_final_texte,
        "article_url": url,
        "is_paywall": is_paywall,
        "news_source_id": int(source_id),
        "created_at": date_str
    }

# --- TEST LOCAL ---
if __name__ == "__main__":
    # Si tu lances ce fichier seul, il cherche ton fichier source_article_brute.txt
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_in = os.path.join(current_dir, "source_article_brute.txt")
    
    if os.path.exists(file_in):
        with open(file_in, "r", encoding="utf-8") as f:
            html_test = f.read()
            res = get_article_data(html_test, "https://actu.fr/test", 1)
            # Log final du dictionnaire pour vérification
            import pprint
            pprint.pprint(res)