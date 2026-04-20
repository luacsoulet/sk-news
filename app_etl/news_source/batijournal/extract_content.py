import os
import html
import re
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime

def decrypter_et_nettoyer(raw_text):
    """
    Décode les entités HTML, répare l'encodage et normalise les espaces.
    (Ta logique d'origine conservée)
    """
    if not raw_text: return ""
    
    # 1. Décodage des entités HTML
    text = html.unescape(raw_text)
    
    # 2. Suppression des balises HTML
    text = re.sub(r'<[^>]+>', '', text)
    
    # 3. Réparation de l'encodage (Mojibake)
    try:
        text = text.encode('latin-1').decode('utf-8')
    except:
        pass
    
    # 4. Nettoyage final
    text = text.replace('\xa0', ' ')
    # Suppression des caractères de contrôle invisibles
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\r")
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines).strip()

def get_article_data(html_content, url, source_id):
    """
    Logique d'extraction spécifique Batijournal.
    Retourne un dictionnaire exportable pour Supabase.
    """
    print(f"\n--- 🛠️ DÉBUT EXTRACTION BATIJOURNAL : {url} ---")
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. EXTRACTION DU TITRE (entry-title)
    titre_tag = soup.find('h1', class_='entry-title')
    titre_final = decrypter_et_nettoyer(titre_tag.get_text()) if titre_tag else "Titre non trouvé"
    print(f"📌 Titre : {titre_final[:50]}...")

    # 2. EXTRACTION DE LA DESCRIPTION
    desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    description = decrypter_et_nettoyer(desc_tag['content']) if desc_tag else ""

    # 3. EXTRACTION DE LA DATE
    # Batijournal (WordPress) utilise souvent 'published_time' ou la balise time
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

    # 4. EXTRACTION DU CORPS (entry-content)
    content_div = soup.find('div', class_='entry-content')
    corps_final = []
    is_paywall = False

    if content_div:
        # Nettoyage des bruits MailPoet (Ta logique)
        for noise in content_div.find_all('div', class_=re.compile(r'mailpoet|mp_form')):
            noise.decompose()
        
        # Détection paywall (Si texte tronqué ou présence de classes restrictives)
        if soup.find(class_=re.compile(r'lock|premium|abonnement|paywall')):
            is_paywall = True
        
        # On récupère les paragraphes et les sous-titres
        elements = content_div.find_all(['p', 'h2', 'h3'])
        print(f"📖 Analyse de {len(elements)} paragraphes...")
        
        for el in elements:
            txt = el.get_text().strip()
            if txt and len(txt) > 5:
                # Formatage des sous-titres
                prefix = "## " if el.name in ['h2', 'h3'] else ""
                corps_final.append(prefix + decrypter_et_nettoyer(txt))
    else:
        print("❌ Erreur : Zone 'entry-content' introuvable.")

    print(f"💰 Paywall : {'OUI' if is_paywall else 'NON'}")
    
    corps_final_texte = "\n\n".join(corps_final)
    print(f"📏 Taille finale : {len(corps_final_texte)} caractères.")

    # 5. RÉSULTAT EXPORTABLE
    print(f"--- ✅ FIN EXTRACTION BATIJOURNAL ---\n")
    
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
            res = get_article_data(f.read(), "https://batijournal.com/test", 1)
            import pprint
            pprint.pprint(res)