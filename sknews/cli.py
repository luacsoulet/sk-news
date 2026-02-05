"""
Command-line interface for SK News
"""

import argparse
import json
import sys
from typing import List

from .models import Article
from .rss_parser import RSSFeedParser, get_feed_url, COMMON_FEEDS


def format_articles(articles: List[Article], format_type: str = 'text') -> str:
    """
    Format articles for output
    
    Args:
        articles: List of articles
        format_type: Output format ('text', 'json')
        
    Returns:
        Formatted string
    """
    if format_type == 'json':
        return json.dumps([article.to_dict() for article in articles], indent=2, ensure_ascii=False)
    
    # Text format
    output = []
    output.append(f"\n{'='*80}")
    output.append(f"Found {len(articles)} articles")
    output.append(f"{'='*80}\n")
    
    for i, article in enumerate(articles, 1):
        output.append(f"\n[{i}] {article.title}")
        output.append(f"    URL: {article.url}")
        if article.published:
            output.append(f"    Published: {article.published}")
        if article.author:
            output.append(f"    Author: {article.author}")
        if article.source:
            output.append(f"    Source: {article.source}")
        if article.summary:
            summary = article.summary[:200] + "..." if len(article.summary) > 200 else article.summary
            output.append(f"    Summary: {summary}")
        if article.tags:
            output.append(f"    Tags: {', '.join(article.tags)}")
        output.append("")
    
    return "\n".join(output)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='SK News - Outil de récupération d\'articles de journaux',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Sources disponibles:
{chr(10).join(f"  - {source}" for source in sorted(COMMON_FEEDS.keys()))}

Exemples:
  sk-news --source lemonde
  sk-news --source bbc --limit 5
  sk-news --url https://www.example.com/rss --format json
  sk-news --list-sources
        """
    )
    
    parser.add_argument(
        '--source', '-s',
        help='Source de news prédéfinie (ex: lemonde, bbc, cnn)'
    )
    
    parser.add_argument(
        '--url', '-u',
        help='URL du flux RSS personnalisé'
    )
    
    parser.add_argument(
        '--limit', '-l',
        type=int,
        help='Nombre maximum d\'articles à récupérer'
    )
    
    parser.add_argument(
        '--format', '-f',
        choices=['text', 'json'],
        default='text',
        help='Format de sortie (default: text)'
    )
    
    parser.add_argument(
        '--list-sources',
        action='store_true',
        help='Afficher la liste des sources disponibles'
    )
    
    args = parser.parse_args()
    
    # List sources
    if args.list_sources:
        print("\nSources de news disponibles:")
        print("="*50)
        for source, url in sorted(COMMON_FEEDS.items()):
            print(f"  {source:15} -> {url}")
        print()
        return 0
    
    # Determine feed URL
    feed_url = None
    if args.url:
        feed_url = args.url
    elif args.source:
        feed_url = get_feed_url(args.source)
        if not feed_url:
            print(f"Erreur: Source '{args.source}' non reconnue", file=sys.stderr)
            print(f"Utilisez --list-sources pour voir les sources disponibles", file=sys.stderr)
            return 1
    else:
        parser.print_help()
        return 1
    
    # Fetch articles
    try:
        parser_obj = RSSFeedParser(feed_url)
        articles = parser_obj.fetch_articles(limit=args.limit)
        
        if not articles:
            print("Aucun article trouvé", file=sys.stderr)
            return 1
        
        # Output articles
        output = format_articles(articles, args.format)
        print(output)
        
        return 0
        
    except Exception as e:
        print(f"Erreur lors de la récupération des articles: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
