#!/usr/bin/env python
"""
Example script demonstrating SK News library usage
"""

from sknews.rss_parser import RSSFeedParser, COMMON_FEEDS
from sknews.models import Article

def main():
    print("SK News - Example Usage")
    print("=" * 60)
    print()
    
    # Example 1: Using predefined sources
    print("Example 1: Available news sources")
    print("-" * 60)
    for source, url in sorted(COMMON_FEEDS.items()):
        print(f"  {source:15} -> {url}")
    print()
    
    # Example 2: Fetching articles with custom RSS feed
    print("Example 2: Fetching articles (with mock data)")
    print("-" * 60)
    
    # For demonstration, we'll use mock data since external feeds might be blocked
    from unittest.mock import MagicMock
    import feedparser
    
    def mock_parse(url):
        result = MagicMock()
        result.feed = {'title': 'Example News Source'}
        result.entries = [
            {
                'title': 'Breaking: Important News Event',
                'link': 'https://example.com/news/article1',
                'summary': 'This is a summary of an important news event that occurred today.',
                'author': 'Jane Reporter',
                'published': 'Wed, 05 Feb 2026 10:00:00 GMT'
            },
            {
                'title': 'Technology: New Innovation Announced',
                'link': 'https://example.com/tech/article2',
                'summary': 'A major technology company has announced a groundbreaking innovation.',
                'author': 'Tech Writer',
                'published': 'Wed, 05 Feb 2026 09:30:00 GMT',
                'tags': [MagicMock(term='technology'), MagicMock(term='innovation')]
            },
            {
                'title': 'Sports: Championship Results',
                'link': 'https://example.com/sports/article3',
                'summary': 'The championship concluded with an exciting final match.',
                'published': 'Wed, 05 Feb 2026 08:00:00 GMT'
            }
        ]
        return result
    
    # Temporarily replace feedparser
    original_parse = feedparser.parse
    feedparser.parse = mock_parse
    
    try:
        # Create parser and fetch articles
        parser = RSSFeedParser('https://example.com/rss')
        articles = parser.fetch_articles(limit=5)
        
        print(f"Fetched {len(articles)} articles:\n")
        
        for i, article in enumerate(articles, 1):
            print(f"[{i}] {article.title}")
            print(f"    URL: {article.url}")
            if article.published:
                print(f"    Published: {article.published}")
            if article.author:
                print(f"    Author: {article.author}")
            if article.source:
                print(f"    Source: {article.source}")
            if article.tags:
                print(f"    Tags: {', '.join(article.tags)}")
            if article.summary:
                summary = article.summary[:100] + "..." if len(article.summary) > 100 else article.summary
                print(f"    Summary: {summary}")
            print()
    
    finally:
        # Restore original feedparser
        feedparser.parse = original_parse
    
    # Example 3: Converting to JSON
    print("Example 3: Converting articles to JSON")
    print("-" * 60)
    import json
    
    if articles:
        first_article = articles[0]
        print(json.dumps(first_article.to_dict(), indent=2, ensure_ascii=False))
    
    print()
    print("=" * 60)
    print("For more examples, see README.md")

if __name__ == '__main__':
    main()
