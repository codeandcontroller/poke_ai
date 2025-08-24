from flask import Flask, render_template, request
import requests

app = Flask(__name__)

# Put your actual Pokémon TCG API key here
API_KEY = "YOUR_API_KEY_HERE"
BASE_URL = "https://api.pokemontcg.io/v2/cards"

@app.route("/", methods=["GET", "POST"])
def home():
    results = []
    if request.method == "POST":
        name = request.form.get("name")
        set_name = request.form.get("set_name")
        rarity = request.form.get("rarity")

        # Build a flexible query string
        query_parts = []
        if name:
            query_parts.append(f'name:"{name}"')
        if set_name:
            query_parts.append(f'set.name:"{set_name}"')
        if rarity:
            query_parts.append(f'rarity:"{rarity}"')

        query = " ".join(query_parts) if query_parts else ""

        headers = {"X-Api-Key": API_KEY}
        params = {"q": query, "pageSize": 20}  # fetch up to 20 results

        response = requests.get(BASE_URL, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            results = data.get("data", [])
        else:
            results = [{"name": "Error fetching cards", "id": "N/A"}]

    return render_template("index.html", results=results)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
