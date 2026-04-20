# utils/check_validity.py

def check_keyword_presence(content, keyword="swiss krono"):
    """
    Vérifie si le mot-clé est présent dans le texte (insensible à la casse).
    Retourne True si trouvé, False sinon.
    """
    if not content or not isinstance(content, str):
        return False
    
    # Nettoyage simple pour la recherche
    text_to_check = content.lower()
    search_term = keyword.lower()
    
    return search_term in text_to_check

def get_validation_score(article_obj):
    """
    Analyse un objet article complet et retourne un indicateur de validité.
    """
    content = article_obj.get("content", "")
    title = article_obj.get("title", "")
    
    # On cherche dans le titre ET le contenu
    full_text = f"{title} {content}"
    
    is_valid = check_keyword_presence(full_text)
    return is_valid