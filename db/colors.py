"""Smart color detection, matching, palette management, and visual indicators."""
import hashlib
import re
from typing import Optional, List, Dict, Tuple

# ── Rich lexicon of colors across Ukrainian, English, and Russian ───────────────
_EXACT_AND_STEM_COLORS: List[Tuple[str, str]] = [
    # --- Multicolored / Special
    ("різнокольоровий", "conic-gradient(red, yellow, lime, aqua, blue, magenta, red)"),
    ("радуга", "conic-gradient(red, yellow, lime, aqua, blue, magenta, red)"),
    ("веселка", "conic-gradient(red, yellow, lime, aqua, blue, magenta, red)"),
    ("rainbow", "conic-gradient(red, yellow, lime, aqua, blue, magenta, red)"),
    ("multicolor", "conic-gradient(red, yellow, lime, aqua, blue, magenta, red)"),
    ("gradient", "conic-gradient(red, yellow, lime, aqua, blue, magenta, red)"),

    # --- Transparent / Natural
    ("прозорий", "transparent"),
    ("прозоро-", "transparent"),
    ("прозрачный", "transparent"),
    ("transparent", "transparent"),
    ("clear", "transparent"),
    ("натуральний", "transparent"),
    ("натуральный", "transparent"),
    ("natural", "transparent"),
    ("кришталевий", "transparent"),
    ("кристалл", "transparent"),
    ("crystal", "transparent"),

    # --- Ivory / Слонова кістка / Cream / Flesh
    ("слонової кістки", "#FFFFF0"),
    ("слонова кістка", "#FFFFF0"),
    ("слоновая кость", "#FFFFF0"),
    ("слонов", "#FFFFF0"),
    ("ivory", "#FFFFF0"),
    ("айворі", "#FFFFF0"),
    ("молочний", "#FDFCFA"),
    ("молоко", "#FDFCFA",),
    ("milk", "#FDFCFA"),
    ("кремовий", "#FFFDD0"),
    ("крем", "#FFFDD0"),
    ("cream", "#FFFDD0"),
    ("тілесний", "#FFE4C4"),
    ("телесный", "#FFE4C4"),
    ("flesh", "#FFE4C4"),
    ("nude", "#E3BC9A"),
    ("нюд", "#E3BC9A"),
    ("skin", "#FFE4C4"),
    ("перламутровий", "#F0EAE1"),
    ("перламутр", "#F0EAE1"),
    ("pearl", "#F0EAE1"),

    # --- Wood / Дуб / Natural Timber / Cork / Earth
    ("дуб", "#935B33"),
    ("дубов", "#935B33"),
    ("oak", "#935B33"),
    ("деревний", "#8A5A36"),
    ("дерево", "#8A5A36"),
    ("wood", "#8A5A36"),
    ("сосна", "#8B5A2B"),
    ("соснов", "#8B5A2B"),
    ("pine", "#8B5A2B"),
    ("горіх", "#5D432C"),
    ("орех", "#5D432C"),
    ("walnut", "#5D432C"),
    ("бук", "#A67B5B"),
    ("beech", "#A67B5B"),
    ("ясен", "#B89778"),
    ("ash", "#B89778"),
    ("береза", "#D7C4B7"),
    ("birch", "#D7C4B7"),
    ("кедр", "#9C6644"),
    ("cedar", "#9C6644"),
    ("тик", "#7A5230"),
    ("teak", "#7A5230"),
    ("бамбук", "#D2B55B"),
    ("bamboo", "#D2B55B"),
    ("корка", "#9C6B30"),
    ("пробка", "#9C6B30"),
    ("cork", "#9C6B30"),
    ("венге", "#382C1E"),
    ("wenge", "#382C1E"),
    ("коричневий", "#6D4C41"),
    ("коричнев", "#6D4C41"),
    ("коричневый", "#6D4C41"),
    ("brown", "#6D4C41"),
    ("кавовий", "#4E3629"),
    ("кофейный", "#4E3629"),
    ("кава", "#4E3629"),
    ("coffee", "#4E3629"),
    ("шоколадний", "#4A2E18"),
    ("шоколадный", "#4A2E18"),
    ("шоколад", "#4A2E18"),
    ("chocolate", "#4A2E18"),
    ("капучино", "#8E7057"),
    ("cappuccino", "#8E7057"),
    ("пісочний", "#C2B280"),
    ("песочный", "#C2B280"),
    ("sand", "#C2B280"),
    ("бежевий", "#D2B48C"),
    ("бежевый", "#D2B48C"),
    ("беж", "#D2B48C"),
    ("beige", "#D2B48C"),
    ("tan", "#D2B48C"),
    ("терракот", "#E2725B"),
    ("теракот", "#E2725B"),
    ("terracotta", "#E2725B"),
    ("цегла", "#B22222"),
    ("глина", "#B66A50"),
    ("clay", "#B66A50"),

    # --- Mint / Khaki / Greens / Olive
    ("м'ятний", "#3EB489"),
    ("мятний", "#3EB489"),
    ("м'ят", "#3EB489"),
    ("мят", "#3EB489"),
    ("mint", "#3EB489"),
    ("хакі", "#708238"),
    ("хаки", "#708238"),
    ("khaki", "#708238"),
    ("оливковий", "#6B8E23"),
    ("оливковый", "#6B8E23"),
    ("оливк", "#6B8E23"),
    ("olive", "#6B8E23"),
    ("смарагдовий", "#50C878"),
    ("смарагд", "#50C878"),
    ("изумруд", "#50C878"),
    ("emerald", "#50C878"),
    ("нефрит", "#00A86B"),
    ("jade", "#00A86B"),
    ("лайм", "#32CD32"),
    ("лаймовий", "#32CD32"),
    ("lime", "#32CD32"),
    ("салатовий", "#7CFC00"),
    ("салатовый", "#7CFC00"),
    ("фісташковий", "#93C572"),
    ("фисташковый", "#93C572"),
    ("pistachio", "#93C572"),
    ("хвойний", "#1B4D3E"),
    ("сосновий зелений", "#1B4D3E"),
    ("forest green", "#228B22"),
    ("темно-зелений", "#1B5E20"),
    ("темно зелений", "#1B5E20"),
    ("dark green", "#1B5E20"),
    ("світло-зелений", "#81C784"),
    ("світло зелений", "#81C784"),
    ("light green", "#81C784"),
    ("зелений", "#43A047"),
    ("зеленый", "#43A047"),
    ("green", "#43A047"),

    # --- Ultramarine / Blue / Cyan / Navy / Sapphire
    ("ультрамарин", "#120A8F"),
    ("ultramarine", "#120A8F"),
    ("сапфір", "#0F52BA"),
    ("сапфир", "#0F52BA"),
    ("sapphire", "#0F52BA"),
    ("індиго", "#4B0082"),
    ("indigo", "#4B0082"),
    ("морська хвиля", "#007791"),
    ("морской", "#007791"),
    ("морськ", "#007791"),
    ("лазур", "#007FFF"),
    ("лазурний", "#007FFF"),
    ("azure", "#007FFF"),
    ("блакитний", "#4FC3F7"),
    ("голубий", "#4FC3F7"),
    ("голубой", "#4FC3F7"),
    ("небесний", "#87CEEB"),
    ("sky blue", "#87CEEB"),
    ("бірюзовий", "#40E0D0"),
    ("бирюзовый", "#40E0D0"),
    ("turquoise", "#40E0D0"),
    ("аквамарин", "#7FFFD4"),
    ("aquamarine", "#7FFFD4"),
    ("aqua", "#00FFFF"),
    ("ціан", "#00BCD4"),
    ("циан", "#00BCD4"),
    ("cyan", "#00BCD4"),
    ("волошковий", "#6495ED"),
    ("васильковый", "#6495ED"),
    ("cornflower", "#6495ED"),
    ("темно-синій", "#0D47A1"),
    ("темно синій", "#0D47A1"),
    ("navy", "#000080"),
    ("синій", "#1E88E5"),
    ("синий", "#1E88E5"),
    ("blue", "#1E88E5"),

    # --- Red / Ruby / Burgundy / Wine / Coral / Pink
    ("рубіновий", "#E0115F"),
    ("рубин", "#E0115F"),
    ("ruby", "#E0115F"),
    ("бордовий", "#800020"),
    ("бордо", "#800020"),
    ("burgundy", "#800020"),
    ("марсала", "#722F37"),
    ("винний", "#722F37"),
    ("вишневий", "#990011"),
    ("вишня", "#990011"),
    ("cherry", "#990011"),
    ("малиновий", "#DC143C"),
    ("малина", "#DC143C"),
    ("raspberry", "#DC143C"),
    ("crimson", "#DC143C"),
    ("кораловий", "#FF7F50"),
    ("корал", "#FF7F50"),
    ("coral", "#FF7F50"),
    ("персиковий", "#FFDAB9"),
    ("персик", "#FFDAB9"),
    ("peach", "#FFDAB9"),
    ("лососевий", "#FA8072"),
    ("salmon", "#FA8072"),
    ("рожевий", "#EC407A"),
    ("розовый", "#EC407A"),
    ("pink", "#EC407A"),
    ("фуксія", "#FF00FF"),
    ("фуксия", "#FF00FF"),
    ("fuchsia", "#FF00FF"),
    ("magenta", "#E91E63"),
    ("червоний", "#E53935"),
    ("красный", "#E53935"),
    ("red", "#E53935"),
    ("темно-червоний", "#B71C1C"),
    ("dark red", "#B71C1C"),

    # --- Yellow / Orange / Amber / Gold / Mustard
    ("бурштиновий", "#FFBF00"),
    ("янтарь", "#FFBF00"),
    ("amber", "#FFBF00"),
    ("медовий", "#EB9605"),
    ("гірчичний", "#E1AD01"),
    ("mustard", "#E1AD01"),
    ("лимонний", "#FFF44F"),
    ("лимон", "#FFF44F"),
    ("lemon", "#FFF44F"),
    ("жовтий", "#FDD835"),
    ("желтый", "#FDD835"),
    ("yellow", "#FDD835"),
    ("помаранчевий", "#FF9800"),
    ("оранжевий", "#FF9800"),
    ("оранжевый", "#FF9800"),
    ("orange", "#FF9800"),
    ("гарбузовий", "#FF7518"),
    ("pumpkin", "#FF7518"),

    # --- Purple / Violet / Lavender / Lilac
    ("фіолетовий", "#8E24AA"),
    ("фиолетовый", "#8E24AA"),
    ("purple", "#8E24AA"),
    ("violet", "#8E24AA"),
    ("лавандовий", "#B57EDC"),
    ("лаванда", "#B57EDC"),
    ("lavender", "#B57EDC"),
    ("бузковий", "#C8A2C8"),
    ("сиреневый", "#C8A2C8"),
    ("lilac", "#C8A2C8"),
    ("сливовий", "#8E4585"),
    ("plum", "#8E4585"),
    ("баклажан", "#614051"),
    ("eggplant", "#614051"),

    # --- Metals / Minerals / Neutral
    ("золотий", "#FFD700"),
    ("золото", "#FFD700"),
    ("gold", "#FFD700"),
    ("сріблястий", "#C0C0C0"),
    ("срібний", "#C0C0C0"),
    ("серебристый", "#C0C0C0"),
    ("silver", "#C0C0C0"),
    ("мідний", "#B87333"),
    ("мідь", "#B87333"),
    ("медь", "#B87333"),
    ("copper", "#B87333"),
    ("бронзовий", "#CD7F32"),
    ("бронза", "#CD7F32"),
    ("bronze", "#CD7F32"),
    ("латунь", "#B5A642"),
    ("латунний", "#B5A642"),
    ("brass", "#B5A642"),
    ("титан", "#878681"),
    ("titanium", "#878681"),
    ("хром", "#D4E1E8"),
    ("chrome", "#D4E1E8"),
    ("алюміній", "#A9ACB6"),
    ("aluminum", "#A9ACB6"),
    ("металік", "#A8A9AD"),
    ("металевий", "#A8A9AD"),
    ("metallic", "#A8A9AD"),

    # --- Black / Grey / White / Charcoal
    ("графітовий", "#383E42"),
    ("графіт", "#383E42"),
    ("графит", "#383E42"),
    ("graphite", "#383E42"),
    ("антрацит", "#293133"),
    ("anthracite", "#293133"),
    ("вугільний", "#282828"),
    ("charcoal", "#282828"),
    ("чорний", "#111111"),
    ("черный", "#111111"),
    ("black", "#111111"),
    ("білий", "#F8F9FA"),
    ("белый", "#F8F9FA"),
    ("white", "#F8F9FA"),
    ("світло-сірий", "#D6D8DB"),
    ("light grey", "#D6D8DB"),
    ("темно-сірий", "#495057"),
    ("dark grey", "#495057"),
    ("сірий", "#808080"),
    ("серый", "#808080"),
    ("grey", "#808080"),
    ("gray", "#808080"),
]

# Sorted by keyword length descending for exact & sub-string parsing
_SORTED_LEXICON: List[Tuple[str, str]] = sorted(_EXACT_AND_STEM_COLORS, key=lambda x: -len(x[0]))


def _generate_deterministic_pastel_hex(text: str) -> str:
    """Generate an aesthetically pleasing, vibrant color from any string hash."""
    h = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:6], 16)
    hue = h % 360
    # Use 65% saturation and 50% lightness for great visibility
    import colorsys
    r, g, b = colorsys.hls_to_rgb(hue / 360.0, 0.50, 0.65)
    return f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"


def get_color_hex(color_name: Optional[str]) -> str:
    """Intelligently map any free-text color name to a spectrum HEX code or CSS value.

    Recognizes Ukrainian, English, Russian terms (mint, oak, ivory, khaki, ultramarine, etc.).
    Falls back to a natural warm wood tone for organic/wood concepts,
    or generates a consistent pleasant color for unmapped words.
    """
    if not color_name or not str(color_name).strip() or str(color_name).strip() in ("—", "-", "nan", "None"):
        return "#A0A0A0"

    cleaned = str(color_name).lower().strip()

    # 1. Direct and substring matches in lexicon (longest matches first)
    for kw, hex_val in _SORTED_LEXICON:
        if kw == cleaned or kw in cleaned:
            return hex_val

    # 2. Semantic heuristics for organic/wood/nature terms
    wood_keywords = ["дуб", "дерев", "горіх", "бук", "сосн", "берез", "ялин", "wood", "oak", "timber", "венге", "тик", "кедр", "палісандр", "граб", "ясен", "cork", "bark", "earth"]
    if any(wk in cleaned for wk in wood_keywords):
        return "#935B33"  # Rich natural oak/wood tone

    herb_keywords = ["м'ят", "мят", "хак", "олив", "трав", "листя", "хвой", "мох", "sage", "leaf", "moss", "зелен"]
    if any(hk in cleaned for hk in herb_keywords):
        return "#43A047"  # Natural plant green

    sky_water_keywords = ["ультрамар", "аква", "морськ", "лазур", "бірюз", "неб", "вод", "волошк", "сапфір", "індиго", "хвиля"]
    if any(sw in cleaned for sw in sky_water_keywords):
        return "#1E88E5"  # Vibrant blue

    ivory_keywords = ["слонов", "кістк", "ivory", "айворі", "тілесн", "крем", "беж", "нюд", "skin"]
    if any(ik in cleaned for ik in ivory_keywords):
        return "#FFFFF0"  # Ivory

    # 3. If word is unknown, generate a consistent beautiful tone from string
    return _generate_deterministic_pastel_hex(cleaned)


def render_color_badge(color_name: Optional[str], size: int = 24, show_text: bool = False) -> str:
    """Render an HTML visual circular badge with shadow and border."""
    if not color_name or str(color_name).strip() in ("—", "-", "nan", "None"):
        return "<span style='opacity: 0.5;'>—</span>"

    name_str = str(color_name).strip()
    css_val = get_color_hex(name_str)

    # Transparency handling
    if css_val == "transparent":
        badge_style = (
            f"display: inline-block; width: {size}px; height: {size}px; "
            f"border-radius: 50%; vertical-align: middle; margin-right: 6px; "
            f"border: 2px solid #94A3B8; "
            f"background: repeating-conic-gradient(#CBD5E1 0% 25%, #FFFFFF 0% 50%) 50% / 8px 8px; "
            f"box-shadow: 0 1px 3px rgba(0,0,0,0.2);"
        )
    elif "gradient" in css_val:
        badge_style = (
            f"display: inline-block; width: {size}px; height: {size}px; "
            f"border-radius: 50%; vertical-align: middle; margin-right: 6px; "
            f"border: 2px solid #94A3B8; background: {css_val}; "
            f"box-shadow: 0 1px 3px rgba(0,0,0,0.2);"
        )
    else:
        # Border check for light/white colors
        border_color = "#CBD5E1" if css_val.upper() in ("#FFFFFF", "#F8F9FA", "#FDFCFA", "#FFFFF0", "#FFFDD0") else css_val
        badge_style = (
            f"display: inline-block; width: {size}px; height: {size}px; "
            f"border-radius: 50%; vertical-align: middle; margin-right: 6px; "
            f"border: 2px solid {border_color}; background-color: {css_val}; "
            f"box-shadow: 0 1px 4px rgba(0,0,0,0.22);"
        )

    badge_html = f"<span title='{name_str} ({css_val})' style='{badge_style}'></span>"
    if show_text:
        return f"{badge_html}<span>{name_str}</span>"
    return badge_html
