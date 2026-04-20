import os
import html
import re
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def decrypter_final_anti_bug(raw_text):
    """
    Décode le HTML, répare le Mojibake (Ã© -> é) 
    et nettoie les symboles résiduels en gardant la structure.
    """
    if not raw_text: return ""
    
    # 1. Décodage des entités HTML
    text = html.unescape(raw_text)
    
    # 2. RÉPARATION DU MOJIBAKE
    try:
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    
    text = text.replace('\xa0', ' ')
    text = text.replace('Â', '')
    
    # 3. STRUCTURE : Transformation des balises avant suppression (Ta logique)
    # On transforme les paragraphes de sous-titre en ##
    text = re.sub(r'<p class=[\'"]wysiwyg-h2[\'"]>(.*?)</p>', r'\n\n## \1\n\n', text, flags=re.IGNORECASE)
    # On garde le gras en Markdown
    text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text, flags=re.IGNORECASE)
    
    # 4. Nettoyage final des balises
    text = re.sub(r'<[^>]+>', '', text)
    
    # 5. Normalisation des lignes
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique Léman Bleu.
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION LÉMAN BLEU : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. TITRE ET RÉSUMÉ
    titre_tag = soup.find('h1', class_='pageTitle') or soup.find('h1')
    titre_txt = titre_tag.get_text() if titre_tag else "Titre non trouvé"
    
    desc_meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
    description = desc_meta['content'] if desc_meta else ""
    
    print(f"📌 Titre : {titre_txt[:50]}...")

    # 2. DATE D'EXTRACTION
    # Léman Bleu utilise souvent des balises meta standards
    date_tag = soup.find('meta', property='article:published_time') or soup.find('time')
    date_str = ""
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            date_str = dt.strftime("%d-%m-%Y %H:%M")
        except:
            date_str = decrypter_final_anti_bug(raw_date)
            
    if not date_str:
        date_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    # 3. EXTRACTION DU CORPS (Ciblage EZ_InternalPlaceHolder / BlocText)
    corps_complet_html = []
    is_paywall = False
    
    container = soup.find('div', class_='EZ_InternalPlaceHolder')
    if container:
        print("✅ Conteneur 'EZ_InternalPlaceHolder' trouvé.")
        blocs = container.find_all('div', class_='BlocText')
        for bloc in blocs:
            # On ignore les légendes de photos (Ta logique)
            if bloc.find('p', class_='photoLegend'):
                continue
            
            # On stocke le HTML pour que decrypter_final puisse traiter les classes CSS
            corps_complet_html.append(str(bloc))
    else:
        print("⚠️ Conteneur principal non trouvé, tentative alternative...")
        # Fallback si la structure change légèrement
        alternative = soup.find('article') or soup.find('div', class_='article-content')
        if alternative:
            corps_complet_html.append(str(alternative))

    # Détection Paywall
    if soup.find(class_=re.compile(r'paywall|premium|abonnement|restricted')):
        is_paywall = True

    # Nettoyage final du corps
    corps_final_texte = "\n\n".join([decrypter_final_anti_bug(b) for b in corps_complet_html])
    
    print(f"💰 Paywall : {'OUI' if is_paywall else 'NON'}")
    print(f"📏 Taille finale : {len(corps_final_texte)} caractères.")
    print(f"--- ✅ FIN EXTRACTION LÉMAN BLEU ---\n")

    return {
        "title": decrypter_final_anti_bug(titre_txt),
        "description": decrypter_final_anti_bug(description),
        "content": corps_final_texte,
        "article_url": url,
        "is_paywall": is_paywall,
        "news_source_id": int(source_id),
        "created_at": date_str
    }

# --- TEST LOCAL ---
if __name__ == "__main__":
    import os
    file_test = os.path.join(os.path.dirname(__file__), "source_article_brute.txt")
    if os.path.exists(file_test):
        with open(file_test, "r", encoding="utf-8") as f:
            res = get_article_data(f.read(), "https://www.lemanbleu.ch/fr/test", 1)
            import pprint
            pprint.pprint(res)