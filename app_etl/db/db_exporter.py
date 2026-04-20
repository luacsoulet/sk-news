# db_exporter.py
import streamlit as st

def send_to_supabase(supabase, article_list):
    """Envoie une liste d'articles vers Supabase en évitant les doublons (UPSERT)."""
    success_count = 0
    errors = []

    for article in article_list:
        try:
            # Préparation des données propres
            data_to_push = {
                "title": article.get("title"),
                "description": article.get("description"),
                "content": article.get("content"),
                "article_url": article.get("article_url"),
                "is_paywall": article.get("is_paywall", True),
                "news_source_id": article.get("news_source_id"),
                "created_at": article.get("created_at")
            }
            
            # Utilisation de upsert : si l'article_url existe déjà, il met à jour au lieu de créer une erreur
            supabase.table("articles").upsert(
                data_to_push, 
                on_conflict='article_url'
            ).execute()
            
            success_count += 1
        except Exception as e:
            errors.append(f"Erreur sur '{article.get('title')[:30]}...' : {e}")

    return success_count, errors