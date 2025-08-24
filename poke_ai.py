# poke_ai.py
from flask import Flask, render_template, request
import requests
from requests.exceptions import ReadTimeout, ConnectionError as ReqConnectionError, RequestException
from html import escape

app = Flask(__name__)

# --- Configure these ---
API_KEY = "YOUR_API_KEY_HERE"  # Get one free at https://pokemontcg.io/
BASE_URL = "https://api.pokemontcg.io/v2/cards"
PAGE_SIZE = 20
API_TIMEOUT_SECS = 30  # bumped from 15 to 30
# -----------------------

def build_query(name: str, set_name: str, number: str, rarity: str, type_: str) -> str:
    parts = []
    if name:
        parts.append(f'name:"{name}"')
    if set_name:
        parts.append(f'set.name:"{set_name}"')
    if number:
        parts.append(f'number:"{number}"')
    if rarity:
        parts.append(f'rarity:"{rarity}"')
    if type_:
        parts.append(f'types:"{type_}"')
    return " ".join(parts)

def extract_price(card: dict) -> dict | None:
    tcg = (card.get("tcgplayer") or {})
    prices = (tcg.get("prices") or {})
    if not prices:
        return None

    preference = [
        "holofoil",
        "reverseHolofoil",
        "1stEditionHolofoil",
        "1stEdition",
        "normal",
        "unlimitedHolofoil",
        "unlimited",
    ]

    keys = [k for k in preference if k in prices] or list(prices.keys())
    for k in keys:
        p = prices.get(k) or {}
        market = p.get("market")
        mid = p.get("mid")
        low = p.get("low")
        high = p.get("high")
        if any(v is not None for v in (market, mid, low, high)):
            return {
                "variant": k,
                "market": market,
                "mid": mid,
                "low": low,
                "high": high,
                "updatedAt": tcg.get("updatedAt"),
            }
    return None

@app.route("/", methods=["GET", "POST"])
def home():
    results = []
    query_display = ""
    error_msg = None
    page = request.args.get("page", default=1, type=int)

    if request.method == "POST" or request.args.get("from_nav") == "1":
        name = request.form.get("name", request.args.get("name", "")).strip()
        set_name = request.form.get("set_name", request.args.get("set_name", "")).strip()
        number = request.form.get("number", request.args.get("number", "")).strip()
        rarity = request.form.get("rarity", request.args.get("rarity", "")).strip()
        type_ = request.form.get("type", request.args.get("type", "")).strip()

        query = build_query(name, set_name, number, rarity, type_)
        query_display = escape(query) if query else "(all)"

        headers = {"X-Api-Key": API_KEY} if API_KEY else {}
        params = {
            "q": query,
            "page": page,
            "pageSize": PAGE_SIZE,
            "orderBy": "set.releaseDate,-number",
        }

        try:
            resp = requests.get(BASE_URL, headers=headers, params=params, timeout=API_TIMEOUT_SECS)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("data", []) or []
                for c in results:
                    c["_price"] = extract_price(c)
            else:
                app.logger.warning(f"API error {resp.status_code}: {resp.text[:300]}")
                error_msg = "Pokémon TCG API returned an error."
        except Exception as e:
            error_msg = f"Network error: {e}"

        return render_template(
            "index.html",
            results=results,
            search=query_display,
            error=error_msg,
            page=page,
            name=name,
            set_name=set_name,
            number=number,
            rarity=rarity,
            type_=type_,
        )

    # default empty page
    return render_template("index.html", results=results, search=query_display, error=error_msg, page=page)

if __name__ == "__main__":
    # host=0.0.0.0 is handy for Codespaces/containers; change to default if local only
    app.run(debug=True, host="0.0.0.0", port=5000)
