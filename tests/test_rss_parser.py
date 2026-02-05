"""
Tests for RSS parser
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from sknews.rss_parser import RSSFeedParser, get_feed_url, COMMON_FEEDS


class TestRSSFeedParser(unittest.TestCase):
    """Test RSS feed parser"""
    
    @patch('sknews.rss_parser.feedparser.parse')
    def test_fetch_articles(self, mock_parse):
        """Test fetching articles from RSS feed"""
        # Mock RSS feed response
        mock_feed = MagicMock()
        mock_feed.feed = {'title': 'Test Source'}
        mock_feed.entries = [
            {
                'title': 'Article 1',
                'link': 'https://example.com/article1',
                'summary': 'Summary 1',
                'author': 'Author 1',
                'published': 'Mon, 01 Jan 2024 12:00:00 GMT'
            },
            {
                'title': 'Article 2',
                'link': 'https://example.com/article2',
                'summary': 'Summary 2',
            }
        ]
        mock_parse.return_value = mock_feed
        
        parser = RSSFeedParser('https://example.com/rss')
        articles = parser.fetch_articles()
        
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].title, 'Article 1')
        self.assertEqual(articles[0].url, 'https://example.com/article1')
        self.assertEqual(articles[0].author, 'Author 1')
        self.assertEqual(articles[1].title, 'Article 2')
    
    @patch('sknews.rss_parser.feedparser.parse')
    def test_fetch_articles_with_limit(self, mock_parse):
        """Test fetching articles with limit"""
        mock_feed = MagicMock()
        mock_feed.feed = {'title': 'Test Source'}
        mock_feed.entries = [
            {'title': f'Article {i}', 'link': f'https://example.com/article{i}'}
            for i in range(10)
        ]
        mock_parse.return_value = mock_feed
        
        parser = RSSFeedParser('https://example.com/rss')
        articles = parser.fetch_articles(limit=3)
        
        self.assertEqual(len(articles), 3)
    
    def test_get_feed_url(self):
        """Test getting feed URL for known source"""
        url = get_feed_url('lemonde')
        self.assertIsNotNone(url)
        self.assertIn('lemonde', url.lower())
        
        url = get_feed_url('unknown_source')
        self.assertIsNone(url)
    
    def test_common_feeds(self):
        """Test that common feeds are defined"""
        self.assertIn('lemonde', COMMON_FEEDS)
        self.assertIn('bbc', COMMON_FEEDS)
        self.assertIsInstance(COMMON_FEEDS['lemonde'], str)


if __name__ == '__main__':
    unittest.main()
