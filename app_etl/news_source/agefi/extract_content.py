import os
import html
import re
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def reparer_encodage(text):
    """Répare le Mojibake (ex: Ã© -> é)"""
    if not text: return ""
    try:
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    text = text.replace('Â', '')
    text = text.replace('\xa0', ' ')
    return text

def nettoyer_texte(raw_text):
    """Décodage HTML + Correction encodage + Nettoyage final"""
    if not raw_text: return ""
    text = html.unescape(raw_text)
    text = reparer_encodage(text)
    text = re.sub(r'<[^>]+>', '', text)
    
    # Nettoyage des espaces et lignes
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique Agefi.
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION AGEFI : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. RÉCUPÉRATION DU TITRE
    titre_tag = soup.find('h1') or soup.find('title')
    titre_final = nettoyer_texte(titre_tag.get_text()) if titre_tag else "Titre non trouvé"
    print(f"📌 Titre : {titre_final[:50]}...")

    # 2. RÉCUPÉRATION DE LA DESCRIPTION
    desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    description = nettoyer_texte(desc_tag['content']) if desc_tag else ""

    # 3. RÉCUPÉRATION DE LA DATE
    # On cherche d'abord dans les balises meta (souvent plus fiable sur Agefi)
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    date_str = ""
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            # Nettoyage pour format JJ-MM-AAAA HH:MM
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            date_str = dt.strftime("%d-%m-%Y %H:%M")
        except:
            date_str = nettoyer_texte(raw_date)
    
    if not date_str:
        date_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    # 4. RÉCUPÉRATION DU CORPS (Ta logique spécifique)
    corps_elements = []
    zone_contenu = soup.find('div', class_='non-paywall')
    
    # Détection Paywall
    # Si la zone 'non-paywall' est présente mais très courte, ou si une classe 'paywall' existe
    is_paywall = False
    if not zone_contenu or soup.find(class_=re.compile(r'paywall|premium|restricted')):
        is_paywall = True
    print(f"💰 Paywall détecté : {'OUI' if is_paywall else 'NON'}")

    if zone_contenu:
        print("✅ Zone 'non-paywall' détectée.")
        for p in zone_contenu.find_all(['p', 'h2']):
            txt = p.get_text().strip()
            if txt:
                # On ajoute ## si c'est un sous-titre h2
                prefix = "## " if p.name == 'h2' else ""
                corps_elements.append(prefix + nettoyer_texte(txt))
    else:
        print("⚠️ Essai avec 'articleParagraph'...")
        for p in soup.find_all('p', class_=re.compile(r'articleParagraph')):
            txt = p.get_text().strip()
            if txt:
                corps_elements.append(nettoyer_texte(txt))

    corps_final_texte = "\n\n".join(corps_elements)
    print(f"📏 Taille du contenu : {len(corps_final_texte)} caractères.")

    # 5. RÉSULTAT EXPORTABLE
    print(f"--- ✅ FIN EXTRACTION AGEFI ---\n")
    
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
    # Test autonome
    import os
    file_in = os.path.join(os.path.dirname(__file__), "source_article_brute.txt")
    if os.path.exists(file_in):
        with open(file_in, "r", encoding="utf-8") as f:
            test_res = get_article_data(f.read(), "https://agefi.fr/test", 1)
            import pprint
            pprint.pprint(test_res)