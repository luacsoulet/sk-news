import os
from supabase import create_client, Client
from dotenv import load_dotenv
from flask import Flask

# Chargement des variables d'environnement
load_dotenv()

app = Flask(__name__)

supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"), 
    os.environ.get("SUPABASE_KEY")
)

@app.route("/articles")
def get_articles():
    try:
        response = supabase.table("articles").select("*").execute()
        return {"articles": response.data}
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/sources")
def get_sources():
    try:
        response = supabase.table("news_source").select("*").execute()
        return {"sources": response.data}
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(debug=True)