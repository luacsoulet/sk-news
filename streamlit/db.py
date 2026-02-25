import os
from supabase import create_client, Client

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def get_articles():
    # Chargement global initial
    response = supabase.table("articles").select("*").order("created_at", desc=True).execute()
    return response.data

def get_news_sources():
    response = supabase.table("news_source").select("*").execute()
    return response.data