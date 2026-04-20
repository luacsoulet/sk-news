import os
import html
import re
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def reparer_encodage(text):
    """Répare les problèmes d'affichage Mojibake (ex: Ã© -> é)"""
    if not text: return ""
    try:
        # Tente de corriger le mauvais décodage UTF-8/Latin-1
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    text = text.replace('Â', '')
    text = text.replace('\xa0', ' ')
    return text

def nettoyer_texte(raw_text):
    """Nettoyage final : Décodage HTML + Encodage + Suppression balises"""
    if not raw_text: return ""
    # 1. Décodage des entités HTML
    text = html.unescape(raw_text)
    # 2. Réparation de l'encodage
    text = reparer_encodage(text)
    # 3. Suppression des balises HTML
    text = re.sub(r'<[^>]+>', '', text)
    # 4. Normalisation des espaces
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique pour Bilan.ch.
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION BILAN.CH : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. EXTRACTION DU TITRE (Balise <title> ou <h1>)
    titre_tag = soup.find('title') or soup.find('h1')
    titre_final = nettoyer_texte(titre_tag.get_text()) if titre_tag else "Titre non trouvé"
    # On nettoie souvent le suffixe " - Bilan" des titres de page
    titre_final = titre_final.split(' - Bilan')[0].strip()
    print(f"📌 Titre : {titre_final[:50]}...")

    # 2. EXTRACTION DE LA DESCRIPTION (Meta description)
    desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    description = nettoyer_texte(desc_tag['content']) if desc_tag else ""

    # 3. EXTRACTION DE LA DATE (Meta article:published_time)
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    date_str = ""
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            # Format attendu : JJ-MM-AAAA HH:MM
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            date_str = dt.strftime("%d-%m-%Y %H:%M")
        except:
            date_str = nettoyer_texte(raw_date)
    
    if not date_str:
        date_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    # 4. EXTRACTION DU CORPS (p avec classe articleParagraph)
    paragraphes_tags = soup.find_all('p', class_='articleParagraph')
    
    corps_elements = []
    is_paywall = False

    # Détection Paywall (Bilan utilise souvent des classes "paywall" ou "restricted")
    if soup.find(class_=re.compile(r'paywall|restricted|premium|locked')):
        is_paywall = True
    print(f"💰 Paywall : {'OUI' if is_paywall else 'NON'}")

    if paragraphes_tags:
        print(f"📖 Analyse de {len(paragraphes_tags)} paragraphes 'articleParagraph'...")
        for p in paragraphes_tags:
            txt = p.get_text().strip()
            if txt:
                corps_elements.append(nettoyer_texte(txt))
    else:
        print("⚠️ Aucun paragraphe 'articleParagraph' trouvé. Tentative sur le corps standard...")
        # Fallback si la classe change
        article_body = soup.find('div', class_=re.compile(r'article-body|content'))
        if article_body:
            for p in article_body.find_all('p'):
                corps_elements.append(nettoyer_texte(p.get_text()))

    corps_final_texte = "\n\n".join(corps_elements)
    print(f"📏 Taille finale : {len(corps_final_texte)} caractères.")

    # 5. RÉSULTAT EXPORTABLE
    print(f"--- ✅ FIN EXTRACTION BILAN.CH ---\n")
    
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
    import os
    file_test = os.path.join(os.path.dirname(__file__), "source_article_brute.txt")
    if os.path.exists(file_test):
        with open(file_test, "r", encoding="utf-8") as f:
            res = get_article_data(f.read(), "https://www.bilan.ch/economie/test", 1)
            import pprint
            pprint.pprint(res)