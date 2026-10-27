"""URL cleaning and product normalization utilities."""
import re
from typing import Optional, Tuple, List
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

# UTM & tracking params to strip
_TRACKING_PARAMS = frozenset([
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "yclid", "msclkid", "ref", "_ga", "mc_cid", "mc_eid",
])

# Weight patterns: matches "1 кг", "0.5kg", "750г", "750 г", "0.85 кг", "1000g" etc.
_WEIGHT_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:кг|kg|кілограм|кg|kh)\b",
    re.IGNORECASE,
)
_WEIGHT_G_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:г(?:рам)?|g(?:r)?)\b",
    re.IGNORECASE,
)
_SPOOL_WEIGHT_SLUG = re.compile(
    r"(?:ves|vaga|ves-)?(\d+(?:[.,]\d+)?)(?:kg|кг|kh)",
    re.IGNORECASE,
)

# Plastic type keyword map
_TYPE_KEYWORDS: list[Tuple[str, list[str]]] = [
    ("TPU", ["tpu", "flex", "elastan", "tpe", "thermoplastic"]),
    ("ABS", ["abs+", "abs pro", "abs-plus", "abs"]),
    ("ASA", ["asa"]),
    ("PETG", ["petg", "copet", "co-pet", "сорет"]),
    ("PLA", ["pla+", "pla-plus", "pla matte", "pla-matte", "pla silk", "pla", "пла"]),
    ("Nylon", ["nylon", "pa6", "pa12", "pa11", "polyamide"]),
    ("CoPE", ["cope", "co-pe", "tpe-e"]),
    ("PCTG", ["pctg"]),
    ("Flex", ["flex"]),
]

# TPU hardness patterns
_HARDNESS_PATTERN = re.compile(
    r"\b(\d{2,3}[AD])\b",
    re.IGNORECASE,
)

# Multilingual color patterns mapped strictly to Ukrainian standard names
COLOR_PATTERNS: List[Tuple[str, List[str]]] = [
    ("Різнокольоровий", [
        "дуоколір", "дуоцвет", "duo", "двоколір", "двухцвет", "триколір", "трехцвет", "tricolor",
        "multicolor", "мультиколор", "перехідний", "переходной", "веселка", "радуга", "rainbow",
        "gradient", "градієнт", "градиент", "magic", "калейдоскоп", "мікс", "микс", "mix", "пастель"
    ]),
    ("Бежевий", [
        "беж", "beige", "skin", "тілесний", "телесный", "крем", "cream", "слонова кістка", "слоновая кость",
        "ivory", "пісочн", "песочн", "sand", "біла кістка", "белая кость", "тіло", "тело", "телесн"
    ]),
    ("Прозорий", [
        "transparent", "clear", "trans", "прозорий", "прозрачный", "прозоро", "прозрачно",
        "natural", "натуральний", "натуральный", "натур"
    ]),
    ("Сріблястий", [
        "срібл", "серебр", "silver", "металік", "металлик", "metallic", "хром", "chrome", "платин", "титан", "titanium"
    ]),
    ("Золотий", [
        "золот", "gold", "латунь", "brass", "бронз", "bronze", "мідь", "медь", "мідний", "медный", "copper", "бурштин", "янтарь", "amber"
    ]),
    ("Чорний", [
        "чорн", "черн", "black", "noir", "schwarz", "графіт", "графит", "graphite", "антрацит", "anthracite", "carbon", "вугіль", "уголь"
    ]),
    ("Білий", [
        "біл", "бел", "white", "blanc", "weiss", "сніжн", "снежн", "snow", "крейд", "мел"
    ]),
    ("Червоний", [
        "червон", "красн", "red", "рубін", "рубин", "ruby", "бордо", "burgundy", "crimson", "вишн", "cherry", "гранат", "garnet", "алий", "scarlet"
    ]),
    ("Синій", [
        "син", "blue", "голуб", "блакит", "azure", "лазур", "navy", "аква", "aqua", "marine", "морськ", "морск",
        "cyan", "ціан", "циан", "сапфір", "сапфир", "бірюз", "бирюз", "turquoise", "волошков", "васильков", "ультрамарин", "ultramarine", "sky blue", "klein"
    ]),
    ("Зелений", [
        "зелен", "green", "хакі", "хаки", "khaki", "оливк", "olive", "лайм", "lime", "м'ят", "мят", "mint",
        "смарагд", "изумруд", "emerald", "пляшков", "бутылоч", "койот", "coyote", "army", "армійськ", "армейск",
        "сосна", "ялин", "салат", "яблучн", "яблочн", "forest"
    ]),
    ("Жовтий", [
        "жовт", "желт", "yellow", "лимон", "lemon"
    ]),
    ("Помаранчевий", [
        "помаранч", "оранж", "orange", "мандарин", "терракот", "теракот", "персик", "peach", "корал", "coral", "гарбуз", "тыква"
    ]),
    ("Фіолетовий", [
        "фіолет", "фиолет", "purple", "violet", "лаванд", "lavender", "бузков", "сиренев", "lilac", "аметист", "пурпур", "magenta"
    ]),
    ("Рожевий", [
        "рожев", "розов", "pink", "бабл", "bubble", "малина", "fuchsia", "фуксія", "фуксия"
    ]),
    ("Коричневий", [
        "коричн", "brown", "шоколад", "chocolate", "дерев", "wood", "каштан", "кава", "кофе", "coffee", "капучино", "cappuccino", "дуб", "oak", "венге", "тютюн", "табак", "горіх", "орех", "cinnamon", "кориц"
    ]),
    ("Сірий", [
        "сір", "сер", "gray", "grey", "silver grey", "попеляст", "пепельн", "сталев", "steel", "димчат", "дымчат"
    ]),
]


def clean_url(url: str) -> str:
    """Strip UTM parameters, fbclid, and other tracking params from a URL."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    qs = parse_qs(parsed.query, keep_blank_values=True)
    cleaned_qs = {k: v for k, v in qs.items() if k.lower() not in _TRACKING_PARAMS}
    new_query = urlencode(cleaned_qs, doseq=True)
    cleaned = parsed._replace(query=new_query)
    return urlunparse(cleaned)


def extract_weight_g(text: str) -> Optional[int]:
    """
    Extract spool weight in grams from product name / title / URL slug.
    Returns None if not detected.
    """
    if not text:
        return None

    cleaned_text = re.sub(r"[12][.,]75\s*мм|[12][.,]85\s*мм|[12][.,]75\s*mm|[12][.,]85\s*mm", " ", text, flags=re.IGNORECASE)

    slug_match = _SPOOL_WEIGHT_SLUG.search(cleaned_text)
    if slug_match:
        val_str = slug_match.group(1).replace(",", ".")
        if val_str == "10":
            return 1000
        val = float(val_str)
        if 0.1 <= val <= 10.0:
            return int(round(val * 1000))

    kg_matches = _WEIGHT_PATTERN.findall(cleaned_text)
    for kg_str in kg_matches:
        val = float(kg_str.replace(",", "."))
        if 0.2 <= val <= 10.0:
            return int(round(val * 1000))

    g_matches = _WEIGHT_G_PATTERN.findall(cleaned_text)
    for g_str in g_matches:
        val = float(g_str.replace(",", "."))
        if 200 <= val <= 10000:
            return int(round(val))

    return None


def normalize_plastic_type(text: str) -> Optional[str]:
    """Detect plastic type from product name."""
    if not text:
        return "PLA"
    lower = text.lower()
    for ptype, keywords in _TYPE_KEYWORDS:
        for kw in keywords:
            if re.search(r"(?:^|[\s/_\-])" + re.escape(kw) + r"(?:$|[\s/_\-])", lower):
                return ptype
    return "PLA"


def extract_hardness(text: str) -> Optional[str]:
    """Extract TPU hardness rating (e.g. 95A, 40D)."""
    if not text:
        return None
    match = _HARDNESS_PATTERN.search(text)
    if match:
        return match.group(1).upper()
    return None


def normalize_color(text: str) -> str:
    """Detect main color name from product title and map to unified Ukrainian standard name."""
    if not text:
        return "Не вказано"
    lower = text.lower()
    for color_name, keywords in COLOR_PATTERNS:
        for kw in keywords:
            if kw in lower:
                return color_name
    return "Не вказано"


def compute_prices(price_uah: float, weight_g: int) -> Tuple[float, float]:
    """Return (price_per_kg, price_per_g) from price and weight in grams."""
    if weight_g == 0 or price_uah is None or price_uah <= 0:
        return (0.0, 0.0)
    price_per_g = price_uah / weight_g
    price_per_kg = price_per_g * 1000
    return round(price_per_kg, 2), round(price_per_g, 4)


def parse_price(text: str) -> Optional[float]:
    """Extract numeric price from text."""
    if not text:
        return None
    
    clean_nums = re.findall(r"(\d+(?:[\s\u00a0]\d+)*(?:[.,]\d+)?)", text)
    valid_prices = []
    for num_str in clean_nums:
        cleaned = re.sub(r"[\s\u00a0]", "", num_str).replace(",", ".")
        try:
            val = float(cleaned)
            if 100 <= val <= 10000:
                valid_prices.append(val)
        except ValueError:
            pass
            
    if valid_prices:
        return valid_prices[0]
    
    match = re.search(r"\d+(?:[.,]\d+)?", text.replace(" ", "").replace("\u00a0", ""))
    if match:
        try:
            return float(match.group(0).replace(",", "."))
        except ValueError:
            pass
            
    return None
