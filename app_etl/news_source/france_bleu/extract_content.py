import os
import html
import re
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def reparer_encodage(text):
    """Nettoie les caractères et les entités HTML (Ta logique)"""
    if not text: return ""
    # Décodage des entités HTML
    text = html.unescape(text)
    # Répare les problèmes d'accents courants (Mojibake)
    try:
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    # Nettoyage des espaces spéciaux
    text = text.replace('\xa0', ' ').replace('\u202f', ' ').strip()
    return text

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique (Structure IciBody / standfirst).
    Retourne un dictionnaire exportable pour Supabase avec logs terminal.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION ICI : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. EXTRACTION DU TITRE
    # Priorité H1, puis Meta og:title
    titre_tag = soup.find('h1')
    titre = reparer_encodage(titre_tag.get_text()) if titre_tag else ""
    
    if not titre or titre == "Titre non trouvé":
        meta_t = soup.find('meta', property='og:title')
        if meta_t: titre = reparer_encodage(meta_t['content'])
    
    if not titre: titre = "Titre non trouvé"
    print(f"📌 Titre : {titre[:50]}...")

    # 2. EXTRACTION DU RÉSUMÉ (standfirst)
    chapo_tag = soup.find('p', class_='standfirst')
    description = reparer_encodage(chapo_tag.get_text()) if chapo_tag else ""

    # 3. EXTRACTION DE LA DATE
    # Recherche dans les meta tags standards
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    date_str = ""
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            # Format attendu : JJ-MM-AAAA HH:MM
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            date_str = dt.strftime("%d-%m-%Y %H:%M")
        except:
            date_str = reparer_encodage(raw_date)
    
    if not date_str:
        date_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    # 4. EXTRACTION DU CORPS (IciBody)
    corps_final = []
    is_paywall = False
    body_container = soup.find('div', class_='IciBody')
    
    if body_container:
        print("✅ Conteneur 'IciBody' détecté.")
        
        # Suppression des pubs AdsSlot (Ta logique)
        for ads in body_container.find_all(class_='AdsSlot'):
            ads.decompose()

        # Détection Paywall (Classes courantes sur ces structures)
        if soup.find(class_=re.compile(r'paywall|premium|subscription|restricted')):
            is_paywall = True

        # Extraction des éléments textuels
        elements = body_container.find_all(['p', 'h2'])
        print(f"📖 Analyse de {len(elements)} paragraphes et sous-titres...")
        
        for elem in elements:
            txt = reparer_encodage(elem.get_text())
            if not txt or len(txt) < 5:
                continue

            if elem.name == 'h2':
                # Formatage titre de section
                corps_final.append(f"## {txt}")
            else:
                corps_final.append(txt)
    else:
        print("❌ Erreur : Zone 'IciBody' introuvable.")

    print(f"💰 Paywall : {'OUI' if is_paywall else 'NON'}")
    
    corps_final_texte = "\n\n".join(corps_final)
    print(f"📏 Taille finale : {len(corps_final_texte)} caractères.")

    # 5. RÉSULTAT EXPORTABLE
    print(f"--- ✅ FIN EXTRACTION ICI ---\n")
    
    return {
        "title": titre,
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
            res = get_article_data(f.read(), "https://ici.test/article", 1)
            import pprint
            pprint.pprint(res)