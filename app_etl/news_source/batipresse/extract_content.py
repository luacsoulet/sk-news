import os
import html
import re
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def nettoyer_et_decrypter(raw_text):
    """
    Décode les entités HTML, nettoie les balises et les espaces.
    (Ta logique d'origine conservée)
    """
    if not raw_text: return ""
    # 1. Décodage des entités
    text = html.unescape(raw_text)
    # 2. Suppression des balises HTML
    text = re.sub(r'<[^>]+>', '', text)
    # 3. Réparation de l'encodage (Mojibake)
    try:
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    # 4. Nettoyage des espaces
    text = text.replace('\xa0', ' ')
    # Suppression des caractères de contrôle invisibles
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\r")
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique Batipresse (thème Hestia).
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION BATIPRESSE : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. EXTRACTION DU TITRE (h1.entry-title)
    titre_tag = soup.find('h1', class_='entry-title')
    titre_final = nettoyer_et_decrypter(titre_tag.get_text()) if titre_tag else "Titre non trouvé"
    print(f"📌 Titre : {titre_final[:50]}...")

    # 2. ACCÈS AU CONTENU PRINCIPAL (div.entry-content)
    content_div = soup.find('div', class_='entry-content')
    
    corps_elements = []
    description = ""
    is_paywall = False

    if content_div:
        # On récupère tous les paragraphes
        paragraphs = content_div.find_all('p')
        print(f"📖 Analyse de {len(paragraphs)} paragraphes...")
        
        for i, p in enumerate(paragraphs):
            txt = p.get_text().strip()
            if not txt: continue
            
            # --- LOGIQUE D'IDENTIFICATION (Ta version) ---
            
            # Le premier paragraphe est la description
            if i == 0:
                description = nettoyer_et_decrypter(txt)
            else:
                # Détection des sous-titres (strong seul et court)
                if p.find('strong', recursive=False) and len(txt) < 100:
                    corps_elements.append(f"## {nettoyer_et_decrypter(txt)}")
                else:
                    corps_elements.append(nettoyer_et_decrypter(txt))
        
        # Détection Paywall (Classes WordPress/Hestia courantes)
        if soup.find(class_=re.compile(r'lock|premium|restricted-content|paywall')):
            is_paywall = True
    else:
        print("❌ Erreur : Zone 'entry-content' introuvable.")

    # 3. EXTRACTION DE LA DATE
    # Recherche dans les meta tags WordPress ou balise time
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    date_str = ""
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            date_str = dt.strftime("%d-%m-%Y %H:%M")
        except:
            date_str = nettoyer_et_decrypter(raw_date)
    
    if not date_str:
        date_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    print(f"💰 Paywall : {'OUI' if is_paywall else 'NON'}")
    
    corps_final_texte = "\n\n".join(corps_elements)
    print(f"📏 Taille finale : {len(corps_final_texte)} caractères.")

    # 4. RÉSULTAT EXPORTABLE
    print(f"--- ✅ FIN EXTRACTION BATIPRESSE ---\n")
    
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
            res = get_article_data(f.read(), "https://batipresse.com/test", 1)
            import pprint
            pprint.pprint(res)