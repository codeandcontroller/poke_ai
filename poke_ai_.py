# poke_ai.py
from flask import Flask, render_template, request
import os, hashlib
import requests
from requests.exceptions import ReadTimeout, ConnectionError as ReqConnectionError, RequestException
from html import escape

# Optional: load .env if present (so OPENAI_API_KEY can live in a .env file)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# --- OpenAI (for the AI outlook) ---
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # handle gracefully if not installed

app = Flask(__name__, template_folder="templates", static_folder="static")

# --- Config ---
POKEMON_TCG_API_KEY = os.getenv("POKEMON_TCG_API_KEY", "YOUR_API_KEY_HERE")
BASE_URL = "https://api.pokemontcg.io/v2/cards"
PAGE_SIZE = 20
API_TIMEOUT_SECS = 30

# Try to load AI directions from either the current folder OR the parent (handles your nested folder case)
AI_DIRECTIONS_PATHS = ["ai_directions.txt", "../ai_directions.txt"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

def load_ai_directions() -> str:
    for p in AI_DIRECTIONS_PATHS:
        try:
            with open(p, "r", encoding="utf-8") as f:
                text = f.read().strip()
                if text:
                    app.logger.info(f"Loaded AI directions from {p}")
                    return text
        except FileNotFoundError:
            continue
    # Fallback if file not found
    return ("You are an assistant that gives collector-focused outlooks on Pokémon cards. "
            "Avoid financial advice; keep to 2–4 sentences; use hedged language and include one caution.")

AI_DIRECTIONS = load_ai_directions()

# -------- Helpers --------
def build_query(name: str, set_name: str, number: str, rarity: str, type_: str) -> str:
    parts = []
    if name: parts.append(f'name:"{name}"')
    if set_name: parts.append(f'set.name:"{set_name}"')
    if number: parts.append(f'number:"{number}"')
    if rarity: parts.append(f'rarity:"{rarity}"')
    if type_: parts.append(f'types:"{type_}"')
    return " ".join(parts)

def extract_price(card: dict) -> dict | None:
    tcg = (card.get("tcgplayer") or {})
    prices = (tcg.get("prices") or {})
    if not prices:
        return None
    preference = [
        "holofoil", "reverseHolofoil", "1stEditionHolofoil", "1stEdition",
        "normal", "unlimitedHolofoil", "unlimited"
    ]
    keys = [k for k in preference if k in prices] or list(prices.keys())
    for k in keys:
        p = prices.get(k) or {}
        market, mid, low, high = p.get("market"), p.get("mid"), p.get("low"), p.get("high")
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

def fetch_cards(query: str, page: int):
    headers = {"X-Api-Key": POKEMON_TCG_API_KEY} if POKEMON_TCG_API_KEY else {}
    params = {
        "q": query,
        "page": page,
        "pageSize": PAGE_SIZE,
        "orderBy": "set.releaseDate,-number",
    }
    app.logger.info(f"Pokémon TCG API → page={page}, params={params}")
    resp = requests.get(BASE_URL, headers=headers, params=params, timeout=API_TIMEOUT_SECS)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("data", []) or []
    for c in results:
        c["_price"] = extract_price(c)
    return results

def hash_payload(payload: dict) -> str:
    keys = ["card_name","card_set","card_number","card_rarity",
            "price_variant","price_market","price_mid","price_low","price_high","price_updated"]
    s = "|".join(str(payload.get(k, "")) for k in keys)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

_AI_CACHE: dict[str, str] = {}

def analyze_with_ai(card_payload: dict) -> str:
    """
    Uses OpenAI to produce a short, collector-focused outlook.
    Simple in-memory cache keyed by card+price details.
    """
    # No key or library? Return a friendly placeholder.
    if not OPENAI_API_KEY or OpenAI is None:
        return ("(AI not configured) Based on set, rarity, and recent prices, collector interest could vary. "
                "Consider historical demand and reprint risk; condition and grading remain key drivers.")

    cache_key = hash_payload(card_payload) + "|" + hashlib.sha256(AI_DIRECTIONS.encode()).hexdigest()
    if cache_key in _AI_CACHE:
        return _AI_CACHE[cache_key]

    details = [
        f"Name: {card_payload.get('card_name','N/A')}",
        f"Set: {card_payload.get('card_set','N/A')}",
        f"Number: {card_payload.get('card_number','N/A')}",
        f"Rarity: {card_payload.get('card_rarity','N/A')}",
    ]
    if card_payload.get("price_variant"):
        details.append(f"TCGplayer Variant: {card_payload['price_variant']}")
    for k,label in [("price_market","Market"),("price_mid","Mid"),("price_low","Low"),("price_high","High")]:
        v = card_payload.get(k)
        if v not in (None, "", "None"):
            details.append(f"{label}: {v}")
    if card_payload.get("price_updated"):
        details.append(f"Prices Updated: {card_payload['price_updated']}")

    system_prompt = AI_DIRECTIONS
    user_prompt = "Card details:\n" + "\n".join(details) + "\n\nReturn 2–4 sentences."

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=180,
        )
        text = resp.choices[0].message.content.strip()
    except Exception as e:
        app.logger.warning(f"OpenAI error: {e}")
        text = "AI service error. Try again later."

    _AI_CACHE[cache_key] = text
    return text

# -------- Routes --------
@app.route("/", methods=["GET", "POST"])
def home():
    results, error_msg = [], None
    page = request.args.get("page", default=1, type=int)

    if request.method == "POST" or request.args.get("from_nav") == "1":
        name = request.form.get("name", request.args.get("name", "")).strip()
        set_name = request.form.get("set_name", request.args.get("set_name", "")).strip()
        number = request.form.get("number", request.args.get("number", "")).strip()
        rarity = request.form.get("rarity", request.args.get("rarity", "")).strip()
        type_ = request.form.get("type", request.args.get("type", "")).strip()

        query = build_query(name, set_name, number, rarity, type_)
        try:
            results = fetch_cards(query, page)
        except ReadTimeout as e:
            app.logger.warning(f"API timeout after {API_TIMEOUT_SECS}s: {e}")
            error_msg = "The Pokémon TCG service took too long to respond. Try a more specific query and try again."
        except ReqConnectionError as e:
            app.logger.warning(f"API connection error: {e}")
            error_msg = "Couldn’t reach the Pokémon TCG service. Please try again shortly."
        except RequestException as e:
            app.logger.warning(f"API request exception: {e}")
            error_msg = "Pokémon TCG API returned an error."

        return render_template(
            "index.html",
            results=results,
            error=error_msg,
            page=page,
            name=name, set_name=set_name, number=number, rarity=rarity, type_=type_,
            ai_opinions={},  # filled by /analyze
        )

    # first load
    return render_template("index.html", results=results, error=error_msg, page=page)

@app.route("/analyze", methods=["POST"])
def analyze():
    # Card payload
    card_id = request.form.get("card_id", "")
    payload = {
        "card_id": card_id,
        "card_name": request.form.get("card_name", ""),
        "card_set": request.form.get("card_set", ""),
        "card_number": request.form.get("card_number", ""),
        "card_rarity": request.form.get("card_rarity", ""),
        "price_variant": request.form.get("price_variant"),
        "price_market": request.form.get("price_market"),
        "price_mid": request.form.get("price_mid"),
        "price_low": request.form.get("price_low"),
        "price_high": request.form.get("price_high"),
        "price_updated": request.form.get("price_updated"),
    }
    # Convert price strings to floats when sensible
    for k in ["price_market", "price_mid", "price_low", "price_high"]:
        v = payload.get(k)
        if v not in (None, "", "None"):
            try:
                payload[k] = float(v)
            except ValueError:
                pass
        else:
            payload[k] = None

    # Restore current query state for re-render
    page = request.form.get("page", type=int, default=1)
    name = request.form.get("name", "")
    set_name = request.form.get("set_name", "")
    number = request.form.get("number", "")
    rarity = request.form.get("rarity", "")
    type_ = request.form.get("type", "")

    query = build_query(name.strip(), set_name.strip(), number.strip(), rarity.strip(), type_.strip())
    opinion = analyze_with_ai(payload)
    ai_opinions = {card_id: opinion}

    results, error_msg = [], None
    try:
        results = fetch_cards(query, page)
    except Exception as e:
        app.logger.warning(f"Re-fetch after AI failed: {e}")
        error_msg = "Error refreshing results after AI analysis."

    return render_template(
        "index.html",
        results=results,
        error=error_msg,
        page=page,
        name=name, set_name=set_name, number=number, rarity=rarity, type_=type_,
        ai_opinions=ai_opinions,
    )

if __name__ == "__main__":
    # host=0.0.0.0 plays nice in Codespaces/containers
    app.run(debug=True, host="0.0.0.0", port=5000)
