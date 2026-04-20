
import os
import html
import re
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime
def reparer_encodage(text):
    """Répare les problèmes d'affichage et nettoie les espaces spéciaux"""
    if not text: return ""
    try:
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    text = text.replace('\xa0', ' ')
    text = text.replace('Â', '')
    return text
def nettoyer_texte(raw_text):
    """Décodage HTML + Nettoyage des balises"""
    if not raw_text: return ""
    text = html.unescape(raw_text)
    text = reparer_encodage(text)
    text = re.sub(r'<[^>]+>', '', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()
def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique Zepros (Drupal).
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION ZEPROS : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')
    # 1. EXTRACTION DU TITRE (H1)
    titre_tag = soup.find('h1')
    titre_final = nettoyer_texte(titre_tag.get_text()) if titre_tag else "Titre non trouvé"
    print(f"📌 Titre : {titre_final[:50]}...")
    # 2. EXTRACTION DU CORPS ET DU CHAPO (field--name-field-texte)
    blocs_texte = soup.find_all('div', class_='field--name-field-texte')
    
    corps_final = []
    description = ""
    is_paywall = False
    if blocs_texte:
        print(f"📖 Analyse de {len(blocs_texte)} blocs de contenu...")
        for i, bloc in enumerate(blocs_texte):
            # Le premier bloc est le Chapo (Ta logique)
            if i == 0:
                description = nettoyer_texte(bloc.get_text())
            else:
                # On parcourt les paragraphes à l'intérieur du bloc
                for p in bloc.find_all(['p', 'h2']):
                    txt = p.get_text().strip()
                    if not txt: continue
                    
                    # Logique spéciale "Question" (Ta logique)
                    if "Zepros Bâti" in txt:
                        corps_final.append(f"## QUESTION : {nettoyer_texte(txt)}")
                    else:
                        # Gestion des sous-titres h2 classiques
                        prefix = "## " if p.name == 'h2' else ""
                        corps_final.append(prefix + nettoyer_texte(txt))
        
        # Détection Paywall (Classes Drupal/Zepros courantes)
        if soup.find(class_=re.compile(r'paywall|login-required|restricted')):
            is_paywall = True
    else:
        print("❌ Erreur : Blocs 'field--name-field-texte' introuvables.")
    # 3. EXTRACTION DE LA DATE
    # Recherche dans les meta tags ou balises time de Drupal
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
    print(f"💰 Paywall : {'OUI' if is_paywall else 'NON'}")
    
    corps_final_texte = "\n\n".join(corps_final)
    print(f"📏 Taille finale : {len(corps_final_texte)} caractères.")
    # 4. RÉSULTAT EXPORTABLE
    print(f"--- ✅ FIN EXTRACTION ZEPROS ---\n")
    
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
            res = get_article_data(f.read(), "https://zepros.fr/test", 1)
            import pprint
            pprint.pprint(res)
