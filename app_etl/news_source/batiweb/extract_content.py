import os
import html
import re
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def decrypter_et_nettoyer(raw_text):
    """
    Décode les entités HTML, gère l'encodage et structure les titres.
    (Ta logique Regex pour les h2 est conservée ici)
    """
    if not raw_text: return ""
    
    # 1. Décodage des entités HTML
    text = html.unescape(raw_text)
    
    # 2. Identification des SOUS-TITRES (h2) via ta Regex
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n\n## \1\n\n', text, flags=re.IGNORECASE)
    
    # 3. Suppression des balises HTML restantes
    text = re.sub(r'<[^>]+>', '', text)
    
    # 4. Réparation de l'encodage (Mojibake)
    try:
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    
    # 5. Nettoyage final des espaces
    text = text.replace('\xa0', ' ')
    # Suppression des caractères de contrôle invisibles
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\r")
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique Batiweb.
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION BATIWEB : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. EXTRACTION DU TITRE (h1 itemprop="headline")
    titre_tag = soup.find('h1', itemprop='headline') or soup.find('h1')
    titre_final = decrypter_et_nettoyer(titre_tag.get_text()) if titre_tag else "Titre non trouvé"
    print(f"📌 Titre : {titre_final[:50]}...")

    # 2. EXTRACTION DE LA DESCRIPTION (chapoRaw)
    chapo_tag = soup.find('div', class_='chapoRaw')
    description = decrypter_et_nettoyer(chapo_tag.get_text()) if chapo_tag else ""

    # 3. EXTRACTION DE LA DATE
    # On cherche dans les meta tags classiques de Batiweb
    date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
    date_str = ""
    if date_tag:
        raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            date_str = dt.strftime("%d-%m-%Y %H:%M")
        except:
            date_str = decrypter_et_nettoyer(raw_date)
    
    if not date_str:
        date_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    # 4. EXTRACTION DU CORPS (contentRaw)
    corps_tag = soup.find('div', class_='contentRaw')
    is_paywall = False
    corps_final_texte = ""

    if corps_tag:
        print("✅ Zone 'contentRaw' détectée.")
        # On passe le HTML brut à ta fonction pour que la Regex H2 fonctionne
        corps_final_texte = decrypter_et_nettoyer(str(corps_tag))
        
        # Détection Paywall (Batiweb utilise souvent des classes comme 'lock' ou 'restricted')
        if soup.find(class_=re.compile(r'paywall|premium|abonnement|lock')):
            is_paywall = True
    else:
        print("❌ Erreur : Zone 'contentRaw' introuvable.")
        is_paywall = True # Souvent signe que le contenu est protégé

    print(f"💰 Paywall : {'OUI' if is_paywall else 'NON'}")
    print(f"📏 Taille finale : {len(corps_final_texte)} caractères.")

    # 5. RÉSULTAT EXPORTABLE
    print(f"--- ✅ FIN EXTRACTION BATIWEB ---\n")
    
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
            res = get_article_data(f.read(), "https://batiweb.com/test", 1)
            import pprint
            pprint.pprint(res)