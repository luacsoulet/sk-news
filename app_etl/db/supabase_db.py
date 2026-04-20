import os
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

@st.cache_resource
def get_client():
    """Initialise ET connecte l'utilisateur à Supabase."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    email = os.environ.get("SUPABASE_AUTHENTICATE_USER_EMAIL")
    password = os.environ.get("SUPABASE_AUTHENTICATE_USER_PASSWORD")
    
    if not url or not key:
        st.error("Variables SUPABASE_URL ou SUPABASE_KEY manquantes dans le .env")
        return None
        
    client = create_client(url, key)
    
    if email and password:
        try: 
            # CRITIQUE : Connexion obligatoire pour passer outre le RLS
            client.auth.sign_in_with_password({"email": email, "password": password})
            return client
        except Exception as e:
            st.error(f"❌ Échec de l'authentification : {e}")
            return None
    else:
        st.warning("⚠️ Identifiants d'authentification manquants dans le .env")
        return None

def fetch_initial_data(client):
    sources = client.table("news_source").select("id, name, as_program").execute()
    articles = client.table("articles").select("title").execute()
    return sources.data, [a['title'] for a in articles.data]

def add_new_source(client, name):
    return client.table("news_source").insert({"name": name, "as_program": False}).execute()

def upsert_article(client, data):
    """Envoie les données une fois l'utilisateur authentifié."""
    ALLOWED = ["title", "description", "content", "article_url", "is_paywall", "news_source_id", "created_at"]
    clean_data = {k: v for k, v in data.items() if k in ALLOWED}
    # L'upsert fonctionnera car le client porte maintenant le jeton 'authenticated'
    return client.table("articles").upsert(clean_data, on_conflict='article_url').execute()