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
        text = text.encode('latin-1').decode('utf-8')
    except Exception:
        pass
    text = text.replace('Â', '')
    text = text.replace('\xa0', ' ')
    return text

def nettoyer_texte(raw_text, est_titre=False):
    """Nettoyage final : Décodage HTML + Encodage + Suppression balises"""
    if not raw_text: return ""
    text = html.unescape(raw_text)
    text = reparer_encodage(text)
    # Suppression des balises HTML résiduelles
    text = re.sub(r'<[^>]+>', '', text)
    
    if est_titre:
        return text.strip()
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique BFM (incluant Contenu Partenaire).
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION BFM : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. NETTOYAGE PRÉALABLE
    for tag in soup.find_all(['script', 'style', 'iframe']):
        tag.decompose()

    # 2. EXTRACTION DU TITRE PRINCIPAL (h1 id="contain_title")
    titre_tag = soup.find('h1', id='contain_title') or soup.find('h1')
    titre_final = nettoyer_texte(titre_tag.get_text(), est_titre=True) if titre_tag else "Titre non trouvé"
    print(f"📌 Titre : {titre_final[:50]}...")

    # 3. EXTRACTION DU RÉSUMÉ / CHAPO
    chapo_tag = soup.find('div', class_='chapo')
    description = ""
    if chapo_tag:
        description = nettoyer_texte(chapo_tag.get_text())
        # Nettoyage du tag spécifique BFM
        description = description.replace("[CONTENU PARTENAIRE]", "").replace("[COTNENU PARTENAIRE]", "").strip()

    # 4. EXTRACTION DU CORPS (Identification intelligente par wrapper)
    wrapper = soup.find('div', class_='content_body_wrapper')
    corps_elements = []
    is_paywall = False

    if wrapper:
        print("✅ Wrapper de contenu détecté.")
        # On parcourt tous les éléments de premier niveau demandés
        for elem in wrapper.find_all(['p', 'ul', 'h2', 'h3']):
            txt_brut = elem.get_text().strip()
            
            # Exclusion des signatures (Ta logique)
            if "réalisé avec SCRIBEO" in txt_brut or "La rédaction de" in txt_brut:
                continue

            # CAS 1 : C'est une question ou un titre en gras (Ta logique strong)
            strong_tag = elem.find('strong', recursive=False)
            if strong_tag and len(txt_brut) == len(strong_tag.get_text().strip()):
                corps_elements.append(f"## {nettoyer_texte(txt_brut, True)}")
            
            # CAS 2 : C'est une liste à puces
            elif elem.name == 'ul':
                for li in elem.find_all('li'):
                    corps_elements.append(f"* {nettoyer_texte(li.get_text(), True)}")
            
            # CAS 3 : C'est un paragraphe normal ou un titre h2/h3
            else:
                txt_propre = nettoyer_texte(txt_brut)
                if txt_propre and len(txt_propre) > 5:
                    prefix = "## " if elem.name in ['h2', 'h3'] else ""
                    corps_elements.append(f"{prefix}{txt_propre}")
    else:
        print("❌ Erreur : Zone 'content_body_wrapper' introuvable.")

    # 5. EXTRACTION DE LA DATE
    # Recherche dans les meta tags (BFM utilise souvent 'article:published_time')
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    date_str = ""
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            date_str = dt.strftime("%d-%m-%Y %H:%M")
        except:
            date_str = nettoyer_texte(raw_date, est_titre=True)
    
    if not date_str:
        date_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    # Détection Paywall (BFM premium ou redirection login)
    if soup.find(class_=re.compile(r'premium|paywall|abonnement|login-gate')):
        is_paywall = True
    
    print(f"💰 Paywall : {'OUI' if is_paywall else 'NON'}")
    
    corps_final_texte = "\n\n".join(corps_elements)
    print(f"📏 Taille finale : {len(corps_final_texte)} caractères.")

    # 6. RÉSULTAT EXPORTABLE
    print(f"--- ✅ FIN EXTRACTION BFM ---\n")
    
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
            res = get_article_data(f.read(), "https://www.bfmtv.com/economie/test", 1)
            import pprint
            pprint.pprint(res)