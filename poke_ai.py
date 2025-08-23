from flask import Flask, render_template, request
import requests

app = Flask(__name__)

API_KEY = "318e5b16-1c35-4b07-b1cb-6e1c227a9cfc"

API_URL = "https://api.pokemontcg.io/v2/cards"

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        card_name = request.form["card_name"]

        # Query the TCG API
        headers = {"X-Api-Key": API_KEY}
        params = {"q": f"name:{card_name}"}
        r = requests.get(API_URL, headers=headers, params=params)
        data = r.json()

        cards = data.get("data", [])
        return render_template("results.html", cards=cards, search=card_name)

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
