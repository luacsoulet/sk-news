import os
import html
import re
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def reparer_encodage(text):
    """Répare les problèmes d'affichage (ex: &eacute; ou Mojibake)"""
    if not text: return ""
    # Décodage des entités HTML
    text = html.unescape(text)
    try:
        # Tente de corriger le Mojibake
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    # Nettoyage des résidus
    text = text.replace('Â', '').replace('\xa0', ' ')
    return text

def nettoyer_texte(raw_text):
    """Nettoyage final : suppression des balises et normalisation des espaces"""
    if not raw_text: return ""
    text = reparer_encodage(raw_text)
    # Suppression des balises HTML restantes
    text = re.sub(r'<[^>]+>', '', text)
    # Normalisation des sauts de ligne
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique Batirama.
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION BATIRAMA : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')

    # --- 1. NETTOYAGE PRÉALABLE (Ta logique) ---
    for publi in soup.find_all('div', id='carouselPubli'):
        publi.decompose()
    for ad in soup.find_all('div', id=re.compile(r'^sas_')):
        ad.decompose()

    # --- 2. EXTRACTION DU TITRE (h1 itemprop="headline") ---
    titre_tag = soup.find('h1', itemprop='headline')
    titre_final = nettoyer_texte(titre_tag.get_text()) if titre_tag else "Titre non trouvé"
    print(f"📌 Titre : {titre_final[:50]}...")

    # --- 3. EXTRACTION DE LA DESCRIPTION / INTRO (span itemprop="description") ---
    intro_tag = soup.find('span', itemprop='description')
    description = nettoyer_texte(intro_tag.get_text()) if intro_tag else ""

    # --- 4. EXTRACTION DE LA DATE ---
    # Recherche dans les meta tags ou balise time
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    date_str = ""
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            date_str = dt.strftime("%d-%m-%Y %H:%M")
        except:
            date_str = nettoyer_texte(raw_date)
    
    if not date_str:
        date_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    # --- 5. EXTRACTION DU CORPS (Ta logique ## et filtrage boutique) ---
    article_container = soup.find('div', class_='post-default') or soup.find('div', class_='cell-lg-11')
    
    corps_elements = []
    is_paywall = False

    if article_container:
        # Détection Paywall (Recherche de classes d'abonnement courantes sur Batirama)
        if soup.find(class_=re.compile(r'abo-content|paywall|premium')):
            is_paywall = True
        
        elements = article_container.find_all(['p', 'h2'])
        print(f"📖 Analyse de {len(elements)} éléments dans le corps...")
        
        for el in elements:
            txt = el.get_text().strip()
            # On ignore les paragraphes courts ou liés à la boutique (Ta logique)
            if txt and len(txt) > 20 and "boutique" not in el.get('class', []):
                if el.name == 'h2':
                    corps_elements.append(f"## {nettoyer_texte(txt)}")
                else:
                    corps_elements.append(nettoyer_texte(txt))
    else:
        print("❌ Erreur : Conteneur principal de l'article introuvable.")

    print(f"💰 Paywall : {'OUI' if is_paywall else 'NON'}")
    
    corps_final_texte = "\n\n".join(corps_elements)
    print(f"📏 Taille finale : {len(corps_final_texte)} caractères.")

    # --- 6. RÉSULTAT EXPORTABLE ---
    print(f"--- ✅ FIN EXTRACTION BATIRAMA ---\n")
    
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
            res = get_article_data(f.read(), "https://batirama.com/test", 1)
            import pprint
            pprint.pprint(res)