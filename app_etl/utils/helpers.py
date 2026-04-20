import unicodedata
import re

def clean_journal_name(name):
    """
    Transforme le nom Google News en slug compatible dossier/BDD.
    Gère les doublons de noms (ex: francebleu vs france_bleu).
    """
    if not name: return "inconnu"
    
    # 1. Retrait des accents et passage en minuscule
    name = ''.join(c for c in unicodedata.normalize('NFD', name.lower()) if unicodedata.category(c) != 'Mn')
    
    # 2. Retrait de l'extension seulement en fin de chaîne
    extensions = r'\.(fr|com|net|org|ch|be|it|at|de)$'
    name = re.sub(extensions, '', name)
    
    # 3. ON CRÉE LES UNDERSCORES D'ABORD !
    name = re.sub(r'[^a-z0-9]+', '_', name).strip('_')
    name = re.sub(r'_+', '_', name)
    
    # 4. --- RÈGLES DE MAPPING FORCÉ (Maintenant on peut chercher avec des underscores) ---
    
    if any(x in name for x in ["france3", "france_3", "franceinfo"]):
        return "france_3_regions"
    
    if any(x in name for x in ["L'Usine Nouvelle", "usine_nouvelle", "usinenouvelle"]):
        return "usine_nouvelle"
    
    if any(x in name for x in ["lepetitjournal","petit_journal", "le_petit_journal"]):
        return "le_petit_journal"
    
    if any(x in name for x in ["republique_du_centre", "la_rep", "larep.fr"]):
        return "la_republique_du_centre"
    
    if any(x in name for x in ["european_data", "edjnet", "European Data Journalism Network"]):
        return "european_data_journalism_network"
    
    if "francebleu" in name or "france_bleu" in name:
        return "france_bleu"

    if any(x in name for x in ["lesechos.fr","lesechos"]):
        return "les_echos"
    
    if any(x in name for x in ["Revue L'Eau, L'Industrie, Les Nuisances","revue_l_eau_l_industrie_les_nuisances"]):
        return "revue_l_eau_l_industrie_les_nuisances"

    return name

def normalize_title(title):
    """Normalisation TRÈS stricte : garde l'ordre des mots, retire tout sauf alpha-num."""
    if not title: return ""
    t = title.lower().replace('\xa0', ' ')
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    
    # On retire le bloc journal à la fin (après le dernier tiret ou barre)
    parts = re.split(r' [-\u2013\u2014|] ', t)
    t = " ".join(parts[:-1]) if len(parts) > 1 else parts[0]
    
    # On ne garde QUE les lettres et les chiffres
    t = re.sub(r'[^a-z0-9]', '', t) 
    return t

def should_ignore(title):
    ignored_keywords = ["gigantesque incendie", "duralex"]
    t_norm = title.lower()
    return any(kw in t_norm for kw in ignored_keywords)