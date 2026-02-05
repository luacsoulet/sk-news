"""
Data models for news articles
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class Article:
    """Represents a news article"""
    
    title: str
    url: str
    published: Optional[datetime] = None
    author: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    
    def to_dict(self):
        """Convert article to dictionary"""
        return {
            'title': self.title,
            'url': self.url,
            'published': self.published.isoformat() if self.published else None,
            'author': self.author,
            'summary': self.summary,
            'content': self.content,
            'source': self.source,
            'tags': self.tags or []
        }
    
    def __str__(self):
        """String representation of article"""
        lines = [
            f"Title: {self.title}",
            f"URL: {self.url}",
        ]
        if self.published:
            lines.append(f"Published: {self.published}")
        if self.author:
            lines.append(f"Author: {self.author}")
        if self.source:
            lines.append(f"Source: {self.source}")
        if self.summary:
            lines.append(f"Summary: {self.summary[:200]}...")
        return "\n".join(lines)
