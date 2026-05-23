"""
Keyword-based auto-categorization for expense descriptions.

add_rule() / extend the CATEGORY_RULES dict to teach the system new merchants.
The first matching category wins, so put more specific rules earlier.
"""

CATEGORY_RULES: dict[str, list[str]] = {
    "Food & Dining": [
        "restaurant", "mcdonald", "starbucks", "subway", "pizza", "cafe",
        "diner", "grubhub", "doordash", "uber eats", "deliveroo", "foodpanda",
        "grabfood", "kfc", "burger king", "wendy", "sushi", "ramen", "noodle",
        "hawker", "kopitiam", "toast box", "ya kun", "old town", "coffee bean",
        "mos burger", "jollibee", "mcdonalds", "chipotle", "panera", "dunkin",
        "domino", "taco bell", "popeye", "chick-fil",
    ],
    "Shopping": [
        "amazon", "walmart", "target", "costco", "bestbuy", "best buy",
        "home depot", "ikea", "zalora", "lazada", "shopee", "taobao",
        "fairprice", "ntuc", "cold storage", "giant", "sheng siong",
        "watsons", "guardian", "decathlon", "uniqlo", "h&m", "zara",
        "cotton on", "muji", "daiso",
    ],
    "Transportation": [
        "uber", "lyft", "grab", "ez-link", "nets flash", "mrt", "smrt",
        "bus", "taxi", "parking", "shell", "bp", "exxon", "caltex", "esso",
        "petron", "spc", "comfort delgro", "transit link", "go-jek", "gojek",
        "zipcar", "hertz", "enterprise rent",
    ],
    "Entertainment": [
        "netflix", "spotify", "disney", "youtube premium", "cinema", "movie",
        "golden village", "gv ", "shaw", "cathay cineplexes", "steam",
        "playstation", "xbox", "nintendo", "apple tv", "hbo", "prime video",
        "bilibili", "esplanade", "sistic", "klook", "tiktok", "twitch",
    ],
    "Health & Medical": [
        "pharmacy", "cvs", "walgreens", "hospital", "clinic", "dental",
        "guardian", "watsons health", "unity pharmacy", "polyclinic",
        "raffles medical", "parkway", "mount elizabeth", "sgh", "ttsh",
        "nuh", "kk women", "optometrist", "optician", "physiotherapy",
    ],
    "Travel": [
        "airline", "airbnb", "booking.com", "expedia", "agoda", "trip.com",
        "singapore airlines", " sia ", "scoot", "jetstar", "cathay pacific",
        "airasia", "changi airport", "trivago", "hotels.com", "marriott",
        "hilton", "hyatt", "ibis", "novotel",
    ],
    "Utilities": [
        "sp services", "city gas", "senoko", "geneco", "pacific light",
        "singtel", "starhub", "m1 limited", "simba telecom", "circles.life",
        "viewqwest", "myrepublic", "electric bill", "water bill",
    ],
    "Insurance": [
        "prudential", "aia singapore", "great eastern", "aviva", "ntuc income",
        "fwd insurance", "tokio marine", "manulife", "income insurance",
        "allianz", "axa",
    ],
    "Banking & Finance": [
        "interest charge", "annual fee", "late fee", "finance charge",
        "cash advance", "atm withdrawal", "wire transfer", "bank transfer",
        "investment", "brokerage", "tiger brokers", "moomoo", "syfe",
        "endowus", "stashaway",
    ],
    "Home & Garden": [
        "ikea", "courts", "harvey norman", "gain city", "best denki",
        "hdb ", "condo ", "rent payment", "maintenance fee", "renovation",
        "furnishing", "home fix", "selffix", "ace hardware",
    ],
    "Personal Care": [
        "hair salon", "barber", "spa ", "massage", "nail ", "beauty",
        "sephora", "mac cosmetics", "l'oreal", "wella", "tony & guy",
        "manicure", "pedicure",
    ],
    "Education": [
        "school fee", "tuition", "udemy", "coursera", "skillsfuture",
        "ntuc learning hub", "kinokuniya", "popular bookstore",
        "times bookstore", "national library",
    ],
    "Income": [
        "salary", "payroll", "direct deposit", "dividend", "interest credit",
        "cashback", "refund", "reimbursement",
    ],
}


def auto_categorize(description: str) -> str:
    """
    Return the best-matching category for a transaction description.
    Falls back to 'Other' when no keyword matches.
    """
    desc_lower = description.lower()
    for category, keywords in CATEGORY_RULES.items():
        for keyword in keywords:
            if keyword in desc_lower:
                return category
    return "Other"
