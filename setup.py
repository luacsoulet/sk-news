from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="sk-news",
    version="0.1.0",
    author="SK News Team",
    description="Outil de récupération d'articles de journaux",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "feedparser>=6.0.10",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "python-dateutil>=2.8.2",
        "lxml>=4.9.0",
    ],
    entry_points={
        "console_scripts": [
            "sk-news=sknews.cli:main",
        ],
    },
)
