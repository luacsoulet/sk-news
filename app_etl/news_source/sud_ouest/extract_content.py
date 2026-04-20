import os
import html
import re
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def reparer_encodage(text):
    """Décode l'HTML et répare les accents (Ta logique)"""
    if not text: return ""
    text = html.unescape(text)
    try:
        # Tente de corriger le Mojibake si nécessaire
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    # Nettoyage des espaces spéciaux
    text = text.replace('\xa0', ' ').replace('\u202f', ' ').strip()
    return text

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique Sud Ouest.
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION SUD OUEST : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. EXTRACTION DU TITRE (h1 class='page-title')
    titre_tag = soup.find('h1', class_='page-title') or soup.find('h1')
    titre_final = reparer_encodage(titre_tag.get_text()) if titre_tag else "Titre non trouvé"
    print(f"📌 Titre : {titre_final[:50]}...")

    # 2. EXTRACTION DU RÉSUMÉ (id='excerpt-block')
    chapo_tag = soup.find('div', id='excerpt-block')
    description = reparer_encodage(chapo_tag.get_text()) if chapo_tag else ""

    # 3. EXTRACTION DE LA DATE
    # Sud Ouest utilise souvent 'article:published_time' dans les meta
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

    # 4. EXTRACTION DU CORPS (div class='article-article')
    corps_final = []
    is_paywall = False
    
    zones_contenu = soup.find_all('div', class_='article-article')
    
    if zones_contenu:
        print(f"📖 Analyse de {len(zones_contenu)} zones de contenu...")
        for zone in zones_contenu:
            # NETTOYAGE DES PARASITES (Ta logique decompose)
            for parasite in zone.find_all(['div', 'section'], class_=['related-article', 'article-wrapper', 'pub', 'encart']):
                parasite.decompose()

            # Détection Paywall (Présence de classes premium ou lock)
            if soup.find(class_=re.compile(r'paywall|premium|abonnement|locked')):
                is_paywall = True

            # Extraction proprement dite (p et h2)
            for elem in zone.find_all(['p', 'h2']):
                txt = reparer_encodage(elem.get_text())
                # Filtre sur la longueur pour éviter les résidus (Ta logique)
                if not txt or len(txt) < 10:
                    continue
                
                if elem.name == 'h2':
                    corps_final.append(f"## {txt}")
                else:
                    corps_final.append(txt)
    else:
        print("❌ Erreur : Zone 'article-article' introuvable.")

    print(f"💰 Paywall : {'OUI' if is_paywall else 'NON'}")
    
    corps_final_texte = "\n\n".join(corps_final)
    print(f"📏 Taille finale : {len(corps_final_texte)} caractères.")

    # 5. RÉSULTAT EXPORTABLE
    print(f"--- ✅ FIN EXTRACTION SUD OUEST ---\n")
    
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
            res = get_article_data(f.read(), "https://www.sudouest.fr/test", 1)
            import pprint
            pprint.pprint(res)