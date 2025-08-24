# poke_ai.py
from flask import Flask, render_template, request
import requests
from html import escape

app = Flask(__name__)

# --- Configure these ---
API_KEY = "318e5b16-1c35-4b07-b1cb-6e1c227a9cfc"  # Get one free at https://pokemontcg.io/
BASE_URL = "https://api.pokemontcg.io/v2/cards"
PAGE_SIZE = 20  # how many results to fetch per search
# -----------------------

def build_query(name: str, set_name: str, number: str, rarity: str, type_: str) -> str:
    """
    Build a Pokémon TCG API v2 query string.
    We wrap values in quotes to handle spaces and special chars.
    """
    parts = []
    if name:
        parts.append(f'name:"{name}"')
    if set_name:
        parts.append(f'set.name:"{set_name}"')
    if number:
        # Card numbers are strings in the API (can be "4", "4a", "TG10", etc.)
        parts.append(f'number:"{number}"')
    if rarity:
        parts.append(f'rarity:"{rarity}"')
    if type_:
        parts.append(f'types:"{type_}"')
    return " ".join(parts)

@app.route("/", methods=["GET", "POST"])
def home():
    results = []
    query_display = ""
    error_msg = None

    if request.method == "POST":
        # Pull fields from the form and normalize
        name = request.form.get("name", "").strip()
        set_name = request.form.get("set_name", "").strip()
        number = request.form.get("number", "").strip()
        rarity = request.form.get("rarity", "").strip()
        type_ = request.form.get("type", "").strip()

        # Build API query
        query = build_query(name, set_name, number, rarity, type_)
        query_display = escape(query) if query else "(all)"

        headers = {"X-Api-Key": API_KEY} if API_KEY else {}
        params = {
            "q": query,
            "pageSize": PAGE_SIZE,
            # Sort newest sets first; then descending by card number for a stable list
            "orderBy": "set.releaseDate,-number"
        }

        try:
            resp = requests.get(BASE_URL, headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                results = resp.json().get("data", [])
            else:
                error_msg = f"API error {resp.status_code}: {resp.text[:200]}"
        except requests.RequestException as e:
            error_msg = f"Network error: {e}"

    # Render one page (form + optional results)
    return render_template("index.html", results=results, search=query_display, error=error_msg)

if __name__ == "__main__":
    # host=0.0.0.0 is handy for Codespaces/containers; change to default if local only
    app.run(debug=True, host="0.0.0.0", port=5000)
