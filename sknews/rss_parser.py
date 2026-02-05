"""
RSS feed parser for retrieving news articles
"""

import feedparser
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser

from .models import Article


class RSSFeedParser:
    """Parser for RSS feeds"""
    
    def __init__(self, feed_url: str):
        self.feed_url = feed_url
    
    def fetch_articles(self, limit: Optional[int] = None) -> List[Article]:
        """
        Fetch articles from RSS feed
        
        Args:
            limit: Maximum number of articles to retrieve
            
        Returns:
            List of Article objects
        """
        feed = feedparser.parse(self.feed_url)
        articles = []
        
        entries = feed.entries[:limit] if limit else feed.entries
        
        for entry in entries:
            # Parse publication date
            published = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'published'):
                try:
                    published = date_parser.parse(entry.published)
                except:
                    pass
            
            # Extract tags
            tags = []
            if hasattr(entry, 'tags'):
                tags = [tag.term for tag in entry.tags]
            
            # Create article
            article = Article(
                title=entry.get('title', 'No Title'),
                url=entry.get('link', ''),
                published=published,
                author=entry.get('author'),
                summary=entry.get('summary'),
                content=entry.get('content', [{}])[0].get('value') if hasattr(entry, 'content') else None,
                source=feed.feed.get('title'),
                tags=tags if tags else None
            )
            articles.append(article)
        
        return articles


# Common news RSS feeds
COMMON_FEEDS = {
    'lemonde': 'https://www.lemonde.fr/rss/une.xml',
    'lefigaro': 'https://www.lefigaro.fr/rss/figaro_actualites.xml',
    'liberation': 'https://www.liberation.fr/arc/outboundfeeds/rss/',
    'franceinfo': 'https://www.francetvinfo.fr/titres.rss',
    'bbc': 'http://feeds.bbci.co.uk/news/rss.xml',
    'cnn': 'http://rss.cnn.com/rss/edition.rss',
    'nytimes': 'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml',
}


def get_feed_url(source: str) -> Optional[str]:
    """
    Get RSS feed URL for a known source
    
    Args:
        source: Source name
        
    Returns:
        Feed URL or None if not found
    """
    return COMMON_FEEDS.get(source.lower())
