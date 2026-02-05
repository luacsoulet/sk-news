"""
Tests for Article model
"""

import unittest
from datetime import datetime
from sknews.models import Article


class TestArticle(unittest.TestCase):
    """Test Article model"""
    
    def test_article_creation(self):
        """Test creating an article"""
        article = Article(
            title="Test Article",
            url="https://example.com/article",
            published=datetime(2024, 1, 1, 12, 0, 0),
            author="Test Author",
            summary="This is a test article",
            source="Test Source"
        )
        
        self.assertEqual(article.title, "Test Article")
        self.assertEqual(article.url, "https://example.com/article")
        self.assertEqual(article.author, "Test Author")
        self.assertEqual(article.source, "Test Source")
    
    def test_article_to_dict(self):
        """Test article to_dict conversion"""
        article = Article(
            title="Test Article",
            url="https://example.com/article",
            published=datetime(2024, 1, 1, 12, 0, 0),
            tags=["tag1", "tag2"]
        )
        
        article_dict = article.to_dict()
        
        self.assertEqual(article_dict['title'], "Test Article")
        self.assertEqual(article_dict['url'], "https://example.com/article")
        self.assertEqual(article_dict['published'], "2024-01-01T12:00:00")
        self.assertEqual(article_dict['tags'], ["tag1", "tag2"])
    
    def test_article_str(self):
        """Test article string representation"""
        article = Article(
            title="Test Article",
            url="https://example.com/article",
            author="Test Author"
        )
        
        article_str = str(article)
        
        self.assertIn("Test Article", article_str)
        self.assertIn("https://example.com/article", article_str)
        self.assertIn("Test Author", article_str)
    
    def test_article_minimal(self):
        """Test article with minimal fields"""
        article = Article(
            title="Minimal Article",
            url="https://example.com/minimal"
        )
        
        self.assertEqual(article.title, "Minimal Article")
        self.assertEqual(article.url, "https://example.com/minimal")
        self.assertIsNone(article.published)
        self.assertIsNone(article.author)
        self.assertIsNone(article.summary)


if __name__ == '__main__':
    unittest.main()
