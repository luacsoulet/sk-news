# SK News - Outil de récupération d'articles de journaux

SK News est un outil Python pour récupérer et analyser des articles de journaux à partir de flux RSS.

## Fonctionnalités

- 📰 Récupération d'articles depuis des flux RSS
- 🌍 Support de sources de news internationales prédéfinies
- 📊 Export au format texte ou JSON
- 🔧 Support de flux RSS personnalisés
- 🎯 Limitation du nombre d'articles à récupérer

## Installation

### Depuis le code source

```bash
git clone https://github.com/luacsoulet/sk-news.git
cd sk-news
pip install -r requirements.txt
pip install -e .
```

## Utilisation

### Interface en ligne de commande

#### Lister les sources disponibles

```bash
sk-news --list-sources
```

#### Récupérer des articles d'une source prédéfinie

```bash
sk-news --source lemonde
sk-news --source bbc --limit 5
```

#### Utiliser un flux RSS personnalisé

```bash
sk-news --url https://www.example.com/rss.xml
```

#### Exporter au format JSON

```bash
sk-news --source cnn --format json
```

### Sources prédéfinies

- **lemonde** - Le Monde (France)
- **lefigaro** - Le Figaro (France)
- **liberation** - Libération (France)
- **franceinfo** - France Info (France)
- **bbc** - BBC News (UK)
- **cnn** - CNN (USA)
- **nytimes** - New York Times (USA)

### Utilisation en tant que bibliothèque Python

```python
from sknews.rss_parser import RSSFeedParser
from sknews.models import Article

# Créer un parser
parser = RSSFeedParser('https://www.lemonde.fr/rss/une.xml')

# Récupérer les articles
articles = parser.fetch_articles(limit=10)

# Traiter les articles
for article in articles:
    print(f"Title: {article.title}")
    print(f"URL: {article.url}")
    print(f"Published: {article.published}")
    print("---")
```

## Tests

Pour exécuter les tests :

```bash
python -m pytest tests/
```

Ou avec unittest :

```bash
python -m unittest discover tests
```

## Structure du projet

```
sk-news/
├── sknews/              # Package principal
│   ├── __init__.py      # Initialisation du package
│   ├── models.py        # Modèles de données (Article)
│   ├── rss_parser.py    # Parser RSS
│   └── cli.py           # Interface en ligne de commande
├── tests/               # Tests unitaires
│   ├── test_models.py
│   └── test_rss_parser.py
├── requirements.txt     # Dépendances
├── setup.py            # Configuration du package
└── README.md           # Documentation

```

## Dépendances

- `feedparser` - Parsing de flux RSS/Atom
- `requests` - Requêtes HTTP
- `beautifulsoup4` - Parsing HTML
- `python-dateutil` - Manipulation de dates
- `lxml` - Parser XML

## Développement

### Contribuer

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

### Roadmap

- [ ] Support de sources de news additionnelles
- [ ] Scraping web pour articles complets
- [ ] Filtrage par mots-clés
- [ ] Export vers base de données
- [ ] Interface web

## Licence

MIT License

## Auteur

SK News Team