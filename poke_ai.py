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

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        set_name = request.form.get("set_name", "").strip()
        number = request.form.get("number", "").strip()
        rarity = request.form.get("rarity", "").strip()
        type_ = request.form.get("type", "").strip()

        query = build_query(name, set_name, number, rarity, type_)
        query_display = escape(query) if query else "(all)"

        headers = {"X-Api-Key": API_KEY} if API_KEY else {}
        params = {
            "q": query,
            "pageSize": PAGE_SIZE,
            "orderBy": "set.releaseDate,-number",
        }

        try:
            # Log the outgoing request for debugging
            app.logger.info(f"Pokémon TCG API request → params={params}")
            resp = requests.get(
                BASE_URL, headers=headers, params=params, timeout=API_TIMEOUT_SECS
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("data", []) or []
                for c in results:
                    c["_price"] = extract_price(c)
            else:
                # Friendly message for users; details in logs
                app.logger.warning(f"API error {resp.status_code}: {resp.text[:300]}")
                error_msg = (
                    "The Pokémon TCG service returned an error. "
                    "Try refining your search (name + set + number) or try again in a moment."
                )

        except ReadTimeout as e:
            app.logger.warning(f"API timeout after {API_TIMEOUT_SECS}s: {e}")
            error_msg = (
                "Phew! thats A big, broad data set for me to cover. "
                "Perhaps a more specific query (e.g., name + set + card number) and try again."
            )
        except ReqConnectionError as e:
            app.logger.warning(f"API connection error: {e}")
            error_msg = (
                "Maybe it's us, but maybe it's you... "
                "Please check your internet connection or try again shortly."
            )
        except RequestException as e:
            app.logger.warning(f"API request exception: {e}")
            error_msg = (
                "Oops! That's on us, not you. "
                "Please try again."
            )

    return render_template("index.html", results=results, search=query_display, error=error_msg)

if __name__ == "__main__":
    # host=0.0.0.0 is handy for Codespaces/containers; change to default if local only
    app.run(debug=True, host="0.0.0.0", port=5000)
