@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        card_name = request.form.get("card_name", "")
        set_name = request.form.get("set_name", "")
        rarity = request.form.get("rarity", "")
        type_ = request.form.get("type", "")

        query_parts = []
        if card_name:
            query_parts.append(f'name:"{card_name}"')
        if set_name:
            query_parts.append(f'set.name:"{set_name}"')
        if rarity:
            query_parts.append(f'rarity:"{rarity}"')
        if type_:
            query_parts.append(f'types:"{type_}"')

        query = " AND ".join(query_parts) if query_parts else "*"

        headers = {"X-Api-Key": API_KEY}
        params = {"q": query, "pageSize": 20}
        r = requests.get(API_URL, headers=headers, params=params)
        data = r.json()

        cards = data.get("data", [])
        return render_template("results.html", cards=cards, search=query)

    return render_template("index.html")
