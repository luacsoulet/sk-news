import os
import html
import re
import json
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def decrypter_final_anti_bug(raw_text):
    """
    Décode le HTML, répare le Mojibake et nettoie les symboles.
    (Ta logique d'origine conservée)
    """
    if not raw_text: return ""

    # 1. Décodage des entités HTML
    text = html.unescape(raw_text)

    # 2. Réparation du Mojibake
    try:
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass

    # 3. Nettoyage des résidus
    text = text.replace('\xa0', ' ')
    text = text.replace('Â', '')
    
    # 4. Suppression des balises HTML
    text = re.sub(r'<[^>]+>', '', text)

    # 5. Normalisation des sauts de ligne
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique CTB (Cahiers Techniques du Bâtiment).
    Structure : HTML avec fallback JSON-LD.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION CTB : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')
    
    titre = ""
    chapo = ""
    corps = ""
    is_paywall = False
    date_str = ""

    # --- 1. TENTATIVE PAR LE HTML (Structure visuelle) ---
    # Titre
    titre_tag = soup.find('h1', class_='titreType7') or soup.find('h1')
    if titre_tag: titre = titre_tag.get_text()

    # Chapo (Intro)
    chapo_tag = soup.find('div', class_='chapo')
    if chapo_tag: chapo = chapo_tag.get_text()

    # Corps de l'article (div textArt)
    corps_tag = soup.find('div', class_='textArt')
    if corps_tag:
        paragraphes = []
        # On récupère p et h2 pour la structure
        for el in corps_tag.find_all(['p', 'h2']):
            txt = el.get_text().strip()
            if txt:
                prefix = "## " if el.name == 'h2' else ""
                paragraphes.append(prefix + txt)
        corps = "\n\n".join(paragraphes)

    # --- 2. SÉCURITÉ : TENTATIVE PAR LE JSON-LD (Si le HTML est incomplet) ---
    if not corps or len(corps) < 150:
        print("🔍 Le HTML semble incomplet, passage au scan JSON-LD...")
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string.strip())
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "NewsArticle":
                        if not titre: titre = item.get("headline", "")
                        if not chapo: chapo = item.get("description", "")
                        if not corps: corps = item.get("articleBody", "")
                        
                        # Récupération de la date dans le JSON
                        date_raw = item.get("datePublished")
                        if date_raw:
                            try:
                                dt = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
                                date_str = dt.strftime("%d-%m-%Y %H:%M")
                            except: pass
                        
                        # Détection Paywall
                        if item.get("isAccessibleForFree") is False:
                            is_paywall = True
                        break
            except: continue

    # --- 3. EXTRACTION DE LA DATE (Si non trouvée dans le JSON) ---
    if not date_str:
        date_tag = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('time')
        if date_tag:
            raw_date = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
            try:
                dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                date_str = dt.strftime("%d-%m-%Y %H:%M")
            except:
                date_str = decrypter_final_anti_bug(raw_date)

    if not date_str:
        date_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    # Détection Paywall complémentaire
    if soup.find(class_=re.compile(r'paywall|abo-only|premium|lock')):
        is_paywall = True

    # --- 4. NETTOYAGE FINAL ---
    titre_f = decrypter_final_anti_bug(titre)
    chapo_f = decrypter_final_anti_bug(chapo)
    corps_f = decrypter_final_anti_bug(corps)

    print(f"📌 Titre : {titre_f[:50]}...")
    print(f"💰 Paywall : {'OUI' if is_paywall else 'NON'}")
    print(f"📏 Taille finale : {len(corps_f)} caractères.")
    print(f"--- ✅ FIN EXTRACTION CTB ---\n")

    # --- 5. RÉSULTAT EXPORTABLE ---
    return {
        "title": titre_f,
        "description": chapo_f,
        "content": corps_f,
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
            res = get_article_data(f.read(), "https://www.lemoniteur.fr/ctb/test", 1)
            import pprint
            pprint.pprint(res)