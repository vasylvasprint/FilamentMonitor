"""Tab 2: My filament inventory (spool management)."""
from datetime import date
from typing import Optional, List, Dict
import pandas as pd
import streamlit as st

from config import (
    PLASTIC_TYPES, TPU_HARDNESS, SPOOL_STATUSES,
    DEFAULT_EMPTY_SPOOL_G, LOW_STOCK_ALERT_G, CRITICAL_STOCK_ALERT_G,
    STANDARD_COLORS,
)
from db import queries

POPULAR_BRANDS = [
    "MonoFilament",
    "LBL Corp",
    "Pochatok",
    "Plexiwire",
    "3DPlast",
    "3D-Smart",
    "Filament.org.ua",
    "UKR3D",
    "Daniparts",
    "Epic3D / 333Print",
    "eSUN",
    "Sunlu",
    "Kingroon",
    "Creality",
    "Bambu Lab",
    "Інший",
]

CONSTRUCTOR_PLASTIC_TYPES = [
    "PETG",
    "CoPE",
    "PLA",
    "TPU / Flex",
    "ABS",
    "ASA",
    "Nylon",
    "PCTG",
]

WEIGHT_OPTIONS = [
    "1000 г (1 кг)",
    "850 г",
    "750 г",
    "500 г",
    "Своя вага / залишок у грамах",
]

# ── Color name → CSS color mapping ────────────────────────────────────────────
# Covers Ukrainian, English, Russian keywords and common descriptors.
_COLOR_MAP = {
    # Ukrainian standard
    "чорний": "#222222", "чорн": "#222222",
    "білий": "#F5F5F5", "біл": "#F5F5F5",
    "сірий": "#9E9E9E", "сір": "#9E9E9E",
    "бежевий": "#D2B48C", "беж": "#D2B48C", "тілесний": "#D2B48C", "кремовий": "#D2B48C", "ivory": "#FFFFF0",
    "червоний": "#E53935", "червон": "#E53935",
    "синій": "#1E88E5", "син": "#1E88E5",
    "зелений": "#43A047", "зелен": "#43A047",
    "жовтий": "#FDD835", "жовт": "#FDD835",
    "помаранчевий": "#FF9800", "помаранч": "#FF9800", "оранж": "#FF9800",
    "фіолетовий": "#8E24AA", "фіолет": "#8E24AA",
    "рожевий": "#EC407A", "рожев": "#EC407A",
    "прозорий": "transparent", "прозор": "transparent", "натуральний": "transparent", "natural": "transparent",
    "сріблястий": "#C0C0C0", "срібл": "#C0C0C0", "срібний": "#C0C0C0",
    "золотий": "#FFD700", "золот": "#FFD700",
    "коричневий": "#6D4C41", "коричнев": "#6D4C41",
    "різнокольоровий": "conic-gradient(red,yellow,lime,aqua,blue,magenta,red)",
    # English
    "black": "#222222", "white": "#F5F5F5", "grey": "#9E9E9E", "gray": "#9E9E9E",
    "red": "#E53935", "blue": "#1E88E5", "green": "#43A047", "yellow": "#FDD835",
    "orange": "#FF9800", "purple": "#8E24AA", "violet": "#8E24AA", "pink": "#EC407A",
    "silver": "#C0C0C0", "gold": "#FFD700", "brown": "#6D4C41", "beige": "#D2B48C",
    "transparent": "transparent", "clear": "transparent",
    "cyan": "#00BCD4", "teal": "#009688", "lime": "#CDDC39", "magenta": "#E91E63",
    "maroon": "#800000", "navy": "#000080", "olive": "#808000", "coral": "#FF7F50",
    "turquoise": "#40E0D0", "indigo": "#3F51B5", "ivory": "#FFFFF0", "khaki": "#F0E68C",
    "crimson": "#DC143C", "aqua": "#00FFFF", "peach": "#FFDAB9",
    # Russian
    "черный": "#222222", "белый": "#F5F5F5", "серый": "#9E9E9E",
    "красный": "#E53935", "синий": "#1E88E5", "зеленый": "#43A047",
    "желтый": "#FDD835", "оранжевый": "#FF9800", "фиолетовый": "#8E24AA",
    "розовый": "#EC407A", "серебристый": "#C0C0C0", "золотой": "#FFD700",
    "коричневый": "#6D4C41", "бежевый": "#D2B48C",
    # Modifiers that hint at a shade
    "темно": None, "темн": None, "світло": None, "світл": None, "яскраво": None,
    "dark": None, "light": None, "bright": None, "pale": None, "deep": None,
}

# Priority-ordered list for substring matching (longest first avoids partial hits)
_COLOR_KEYS_SORTED = sorted(
    [(k, v) for k, v in _COLOR_MAP.items() if v is not None],
    key=lambda pair: -len(pair[0]),
)


def _color_name_to_css(color_name: str) -> Optional[str]:
    """Attempt to derive a CSS colour value from a free-text colour name.

    Returns a CSS colour string or None if nothing recognisable was found.
    """
    if not color_name:
        return None
    lower = color_name.lower().strip()

    # 1. Direct hit in the map (full match)
    if lower in _COLOR_MAP and _COLOR_MAP[lower] is not None:
        return _COLOR_MAP[lower]

    # 2. Substring search (longest keyword first)
    for key, css in _COLOR_KEYS_SORTED:
        if key in lower:
            return css

    return None


def _render_color_dot(color_name: str, size: int = 28) -> str:
    """Return an HTML snippet with a coloured circle indicator for *color_name*.

    If the colour cannot be resolved, a neutral grey circle with a "?" is shown.
    """
    css_color = _color_name_to_css(color_name)

    if css_color is None:
        # Unknown colour – grey with "?"
        return (
            f"<span style='display:inline-block;width:{size}px;height:{size}px;"
            f"border-radius:50%;background:#ccc;border:2px solid #999;vertical-align:middle;"
            f"line-height:{size}px;text-align:center;font-size:{size//2}px;color:#555;'>"
            f"?</span>"
        )

    if css_color == "transparent":
        # Chequered transparency indicator
        return (
            f"<span style='display:inline-block;width:{size}px;height:{size}px;"
            f"border-radius:50%;border:2px solid #aaa;vertical-align:middle;"
            f"background:repeating-conic-gradient(#ddd 0% 25%, #fff 0% 50%) 50%/8px 8px;'>"
            f"</span>"
        )

    if css_color.startswith("conic-gradient"):
        # Rainbow / multicolour
        return (
            f"<span style='display:inline-block;width:{size}px;height:{size}px;"
            f"border-radius:50%;border:2px solid #aaa;vertical-align:middle;"
            f"background:{css_color};'>"
            f"</span>"
        )

    # Solid colour
    border = "#ddd" if css_color.upper() in ("#F5F5F5", "#FFFFF0") else css_color
    return (
        f"<span style='display:inline-block;width:{size}px;height:{size}px;"
        f"border-radius:50%;background:{css_color};border:2px solid {border};"
        f"vertical-align:middle;box-shadow:0 1px 4px rgba(0,0,0,0.18);'>"
        f"</span>"
    )


def render():
    """Render the inventory management tab."""
    st.header("📦 Мій склад філаменту")

    # Top summary banner & metrics
    _render_summary()

    st.markdown("<hr style='margin: 12px 0 20px 0;'>", unsafe_allow_html=True)

    # Subtabs
    inv_tab1, inv_tab2 = st.tabs(["📋 Мої котушки", "➕ Додати котушку"])

    with inv_tab1:
        _render_inventory_view()

    with inv_tab2:
        _render_add_spool_tab()


def _render_summary():
    """Display prominent total stock summary and key metrics."""
    spools = queries.get_inventory(status_filter=["active", "sealed"])
    total_spools = len(spools)
    total_g = sum(s["current_weight_g"] for s in spools)
    total_kg = total_g / 1000.0
    total_value = sum(
        s["purchase_price"] * (s["current_weight_g"] / max(s["initial_weight_g"], 1))
        for s in spools
    )
    low_stock = [s for s in spools if s["current_weight_g"] < LOW_STOCK_ALERT_G]

    # Prominent summary banner
    st.markdown(
        f"""
        <div style='background: linear-gradient(90deg, #1f77b4 0%, #155a8a 100%); color: #ffffff; padding: 14px 22px; border-radius: 8px; margin-bottom: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.08);'>
            <div style='font-size: 1.35rem; font-weight: 700; letter-spacing: 0.3px;'>
                📦 Всього на складі: {total_spools} котушок &nbsp;|&nbsp; Загальна вага: {total_kg:.2f} кг
            </div>
            <div style='font-size: 0.95rem; opacity: 0.92; margin-top: 3px;'>
                Загальна вартість залишку: <b>{total_value:.0f} ₴</b> &nbsp;•&nbsp; Активні та запаковані запаси пластику
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not spools:
        st.info("ℹ️ Склад наразі порожній. Перейдіть на підвкладку «➕ Додати котушку», щоб занести свої запаси!")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Котушок на складі", total_spools)
    col2.metric("Всього пластику", f"{total_kg:.2f} кг")
    col3.metric("Вартість залишку", f"{total_value:.0f} ₴")
    col4.metric("⚠️ Мало залишку (<150г)", len(low_stock))


# ══════════════════════════════════════════════════════════════════════════════
#  Grouping helpers
# ══════════════════════════════════════════════════════════════════════════════

def _group_key(spool: dict) -> tuple:
    """Return the key used to group spools that should display in one row."""
    return (
        (spool.get("brand") or "").strip().lower(),
        (spool.get("plastic_type") or "").strip().lower(),
        (spool.get("color") or "").strip().lower(),
    )


def _build_groups(spools: list) -> list:
    """Group spools by (brand, plastic_type, color) and produce summary dicts.

    Each group dict has the combined weights, summed value, list of member
    spool IDs, and a representative spool for display metadata.
    """
    from collections import OrderedDict

    groups: OrderedDict = OrderedDict()
    for sp in spools:
        key = _group_key(sp)
        if key not in groups:
            groups[key] = {
                "spools": [],
                "total_current_g": 0,
                "total_initial_g": 0,
                "total_value": 0.0,
            }
        groups[key]["spools"].append(sp)
        groups[key]["total_current_g"] += sp["current_weight_g"]
        groups[key]["total_initial_g"] += sp["initial_weight_g"]
        groups[key]["total_value"] += sp.get("purchase_price", 0) * (
            sp["current_weight_g"] / max(sp["initial_weight_g"], 1)
        )

    result = []
    for key, g in groups.items():
        rep = g["spools"][0]  # representative spool for metadata
        result.append({
            "key": key,
            "representative": rep,
            "spools": g["spools"],
            "count": len(g["spools"]),
            "total_current_g": g["total_current_g"],
            "total_initial_g": g["total_initial_g"],
            "total_value": g["total_value"],
            "min_current_g": min(s["current_weight_g"] for s in g["spools"]),
        })
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  Inventory view — grouped cards
# ══════════════════════════════════════════════════════════════════════════════

def _render_inventory_view():
    """Render inventory cards grouped by (brand, plastic_type, color)."""
    col1, col2 = st.columns(2)
    with col1:
        status_filter_display = st.multiselect(
            "Статус",
            options=list(SPOOL_STATUSES.values()),
            default=["В роботі", "Запакована (нова)"],
        )
    with col2:
        type_filter = st.multiselect("Тип пластику", options=PLASTIC_TYPES, default=[])

    status_reverse = {v: k for k, v in SPOOL_STATUSES.items()}
    status_keys = [status_reverse[s] for s in status_filter_display if s in status_reverse]

    spools = queries.get_inventory(status_filter=status_keys if status_keys else None)

    if type_filter:
        spools = [s for s in spools if s["plastic_type"] in type_filter]

    if not spools:
        st.info("Не знайдено котушок за обраними фільтрами.")
        return

    groups = _build_groups(spools)

    # Sort: critical first (by minimum spool weight in group)
    groups.sort(key=lambda g: (
        0 if g["min_current_g"] < CRITICAL_STOCK_ALERT_G
        else 1 if g["min_current_g"] < LOW_STOCK_ALERT_G
        else 2
    ))

    cols = st.columns(2)
    for i, group in enumerate(groups):
        with cols[i % 2]:
            _render_group_card(group)


def _render_group_card(group: dict):
    """Render a single grouped card representing 1+ spools with the same brand/type/color."""
    rep = group["representative"]
    count = group["count"]
    total_current_g = group["total_current_g"]
    total_initial_g = group["total_initial_g"]
    min_g = group["min_current_g"]

    pct = min(100.0, (total_current_g / max(total_initial_g, 1)) * 100)

    is_critical = min_g < CRITICAL_STOCK_ALERT_G
    is_low = min_g < LOW_STOCK_ALERT_G

    if is_critical:
        alert_icon = "🔴"
    elif is_low:
        alert_icon = "🟡"
    else:
        alert_icon = "🟢"

    plastic_type = rep.get("plastic_type", "?")
    color = rep.get("color", "") or ""
    brand = rep.get("brand", "") or ""
    hardness = rep.get("hardness", "")

    type_display = plastic_type
    if hardness and hardness != "Невідомо" and hardness != "—":
        type_display += f" {hardness}"

    # Build title line
    color_dot = _render_color_dot(color, size=24)
    qty_badge = f"<span style='background:#1f77b4;color:#fff;border-radius:12px;padding:2px 9px;font-size:0.82rem;font-weight:700;margin-left:6px;'>{count} шт</span>" if count > 1 else ""
    title_html = f"{color_dot}&nbsp; {alert_icon} <b>{type_display}</b>"
    if color:
        title_html += f" — {color}"
    if brand:
        title_html += f" <span style='opacity:0.7;'>({brand})</span>"
    title_html += qty_badge

    with st.container(border=True):
        st.markdown(title_html, unsafe_allow_html=True)

        total_kg_display = total_current_g / 1000.0
        st.progress(pct / 100, text=f"{total_current_g} г ({total_kg_display:.2f} кг) / {total_initial_g} г ({pct:.0f}%)")

        value_display = group["total_value"]
        st.caption(f"💰 Залишкова вартість: {value_display:.0f} ₴")

        if is_low:
            st.warning(f"⚠️ Одна з котушок має залишок < {LOW_STOCK_ALERT_G} г!")
            if st.button(
                "🔍 Перевірити актуальні ціни на цей пластик",
                key=f"check_prices_grp_{'_'.join(str(x) for x in group['key'])}",
                use_container_width=True,
            ):
                st.session_state["price_filter_type"] = plastic_type
                st.session_state["active_tab"] = 0
                st.rerun()

        # Expandable detail section showing individual spools
        with st.expander(f"📋 Деталі ({count} {'котушка' if count == 1 else 'котушок'})", expanded=False):
            for sp in group["spools"]:
                _render_individual_spool(sp)


def _render_individual_spool(spool: dict):
    """Render a compact inline view for a single spool inside a group expander."""
    spool_id = spool["id"]
    current_g = spool["current_weight_g"]
    initial_g = spool["initial_weight_g"]
    pct = min(100.0, (current_g / max(initial_g, 1)) * 100)
    status = SPOOL_STATUSES.get(spool.get("status", "active"), "В роботі")
    store = spool.get("store_name", "")
    price = spool.get("purchase_price", 0)

    st.markdown(f"**ID #{spool_id}** — {current_g} г / {initial_g} г ({pct:.0f}%) | {status} | {price:.0f} ₴{f' | 📍 {store}' if store else ''}")

    action_col1, action_col2, action_col3 = st.columns(3)

    with action_col1:
        if st.button("⚖️ Зважити", key=f"weigh_{spool_id}", use_container_width=True):
            st.session_state[f"weighing_{spool_id}"] = True

    with action_col2:
        status_options = list(SPOOL_STATUSES.values())
        current_status_display = SPOOL_STATUSES.get(spool.get("status", "active"), "В роботі")
        new_status_display = st.selectbox(
            "Статус",
            options=status_options,
            index=status_options.index(current_status_display) if current_status_display in status_options else 0,
            key=f"status_sel_{spool_id}",
            label_visibility="collapsed",
        )
        if new_status_display != current_status_display:
            status_reverse = {v: k for k, v in SPOOL_STATUSES.items()}
            queries.update_spool_status(spool_id, status_reverse[new_status_display])
            st.rerun()

    with action_col3:
        if st.button("🗑️ Видалити", key=f"del_{spool_id}", use_container_width=True):
            st.session_state[f"confirm_del_{spool_id}"] = True

    # Weigh modal
    if st.session_state.get(f"weighing_{spool_id}"):
        with st.form(key=f"weigh_form_{spool_id}"):
            st.subheader("⚖️ Швидка інвентаризація на вагах")
            empty_g = spool.get("empty_spool_weight_g", DEFAULT_EMPTY_SPOOL_G)
            gross_g = st.number_input(
                "Загальна вага котушки з вагів (брутто, г)",
                min_value=0,
                value=int(current_g + empty_g),
                step=1,
                help=f"Введіть вагу з кухонних ваг. Програма автоматично відніме вагу тари ({empty_g} г).",
            )
            net_g = max(0, gross_g - empty_g)
            st.info(f"Чистий залишок пластику: **{net_g} г** (брутто {gross_g} г − тара {empty_g} г)")

            col_ok, col_cancel = st.columns(2)
            with col_ok:
                if st.form_submit_button("✅ Оновити залишок", use_container_width=True):
                    queries.update_spool_weight(spool_id, net_g)
                    st.session_state[f"weighing_{spool_id}"] = False
                    st.success(f"Залишок оновлено: {net_g} г")
                    st.rerun()
            with col_cancel:
                if st.form_submit_button("❌ Скасувати", use_container_width=True):
                    st.session_state[f"weighing_{spool_id}"] = False
                    st.rerun()

    # Delete confirmation
    if st.session_state.get(f"confirm_del_{spool_id}"):
        plastic_type = spool.get("plastic_type", "?")
        hardness = spool.get("hardness", "")
        type_display = plastic_type
        if hardness and hardness != "Невідомо" and hardness != "—":
            type_display += f" {hardness}"
        st.error(f"Видалити котушку «{type_display}»? Цю дію неможливо скасувати.")
        dc1, dc2 = st.columns(2)
        with dc1:
            if st.button("Так, видалити", key=f"del_yes_{spool_id}", use_container_width=True):
                queries.delete_spool(spool_id)
                st.session_state[f"confirm_del_{spool_id}"] = False
                st.rerun()
        with dc2:
            if st.button("Скасувати", key=f"del_no_{spool_id}", use_container_width=True):
                st.session_state[f"confirm_del_{spool_id}"] = False
                st.rerun()

    st.markdown("<hr style='margin:8px 0;border:none;border-top:1px solid rgba(128,128,128,0.15);'>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  Add Spool form — free text color input
# ══════════════════════════════════════════════════════════════════════════════

def _render_add_spool_tab():
    """Render fast constructor with selectboxes and free-text color input."""
    st.subheader("⚡ Швидкий конструктор котушки (в один клік)")
    st.caption("Оберіть параметри з випадаючих списків, а колір введіть як завгодно — довільним текстом:")

    # ──────────────────────────────────────────────────────────────────────────
    # Mode 1: Fast Single / Multi-spool Constructor
    # ──────────────────────────────────────────────────────────────────────────
    with st.container(border=True):
        col1, col2, col3 = st.columns([2.5, 2.5, 2.0])

        with col1:
            brand_choice = st.selectbox(
                "Бренд / Виробник *",
                options=POPULAR_BRANDS,
                index=0,
                key="c_brand_choice",
            )
            if brand_choice == "Інший":
                custom_brand = st.text_input("Введіть свій бренд *", placeholder="Наприклад: Devil Design")
                actual_brand = custom_brand.strip() or "Інший"
            else:
                actual_brand = brand_choice

            # Free-text color input with live preview
            color_input = st.text_input(
                "Колір *",
                value="Чорний",
                key="c_color_input",
                placeholder="напр.: темно-зелений, кришталево-прозорий, sky blue",
            )
            color_choice = color_input.strip() if color_input.strip() else "Чорний"

            # Live colour preview
            dot_html = _render_color_dot(color_choice, size=22)
            st.markdown(
                f"<div style='margin-top:-8px;margin-bottom:8px;'>"
                f"{dot_html} <span style='font-size:0.85rem;opacity:0.7;'>Попередній перегляд кольору</span></div>",
                unsafe_allow_html=True,
            )

        with col2:
            plastic_choice = st.selectbox(
                "Тип пластику *",
                options=CONSTRUCTOR_PLASTIC_TYPES,
                index=0,
                key="c_plastic_choice",
            )

            if plastic_choice == "TPU / Flex":
                hardness_choice = st.selectbox(
                    "Твердість TPU",
                    options=["95A", "90A", "85A", "40D", "Невідомо"],
                    index=0,
                    key="c_hardness_choice",
                )
                actual_type = "TPU"
                actual_hardness = hardness_choice if hardness_choice != "Невідомо" else None
            else:
                actual_type = plastic_choice
                actual_hardness = None

            weight_preset = st.selectbox(
                "Вага нитки на 1 котушці (г) *",
                options=WEIGHT_OPTIONS,
                index=0,
                key="c_weight_preset",
            )
            if weight_preset == "1000 г (1 кг)":
                actual_weight_g = 1000
            elif weight_preset == "850 г":
                actual_weight_g = 850
            elif weight_preset == "750 г":
                actual_weight_g = 750
            elif weight_preset == "500 г":
                actual_weight_g = 500
            else:
                actual_weight_g = st.number_input(
                    "Введіть точну вагу нитки (г) *",
                    min_value=10,
                    max_value=5000,
                    value=1000,
                    step=50,
                    key="c_custom_weight",
                    help="Підходить для вже початих або нестандартних котушок",
                )

        with col3:
            quantity = st.number_input(
                "Кількість котушок (шт.)",
                min_value=1,
                max_value=50,
                value=1,
                step=1,
                key="c_quantity",
                help="Якщо вказати, наприклад, 5 шт по 1 кг — на склад запишеться одразу 5 окремих котушок",
            )

            price = st.number_input(
                "Ціна за котушку (₴)",
                min_value=0.0,
                value=500.0,
                step=25.0,
                key="c_price",
                help="Необов'язково. За замовчуванням 500 грн або 0, якщо не пам'ятаєте",
            )

            status_display = st.selectbox(
                "Статус",
                options=["Запакована (нова)", "В роботі"],
                index=0,
                key="c_status_display",
            )
            status_key = "sealed" if status_display == "Запакована (нова)" else "active"

        btn_text = f"➕ Додати на склад ({quantity} шт · {actual_brand} {actual_type} {color_choice}, {actual_weight_g} г)"
        if st.button(btn_text, type="primary", use_container_width=True, key="btn_add_constructor"):
            today_iso = date.today().isoformat()
            added_ids = []
            for _ in range(quantity):
                spool = {
                    "brand": actual_brand,
                    "store_name": actual_brand,
                    "plastic_type": actual_type,
                    "color": color_choice,
                    "hardness": actual_hardness,
                    "initial_weight_g": int(actual_weight_g),
                    "current_weight_g": int(actual_weight_g),
                    "empty_spool_weight_g": DEFAULT_EMPTY_SPOOL_G,
                    "purchase_price": float(price),
                    "purchase_date": today_iso,
                    "status": status_key,
                    "notes": "Швидкий конструктор складу",
                    "snapshot_id": None,
                }
                new_id = queries.add_spool(spool)
                added_ids.append(new_id)

            st.success(f"🎉 Успішно додано {quantity} котушок «{actual_brand} {actual_type} {color_choice}» ({actual_weight_g} г, {price:.0f} ₴) на склад!")
            st.rerun()

    st.markdown("<hr style='margin: 25px 0 15px 0;'>", unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Mode 2: Interactive Batch Table Entry (st.data_editor)
    # ──────────────────────────────────────────────────────────────────────────
    st.subheader("⚡ Швидке додавання списком (Таблиця)")
    st.caption(
        "Наклікайте зі списків у таблиці одразу 5-10 різних видів пластику, які вже лежать у вас вдома, "
        "та збережіть весь список однією кнопкою (кнопка «+» внизу таблиці додає новий рядок). "
        "Колір можна ввести будь-який текст:"
    )

    if "batch_inventory_df" not in st.session_state:
        initial_data = [
            {"Бренд": "MonoFilament", "Тип": "PETG", "Твердість TPU": "—", "Колір": "Чорний", "Вага 1 шт (г)": 1000, "Кількість котушок": 1, "Ціна (₴)": 500.0, "Статус": "Запакована (нова)"},
            {"Бренд": "3D-Smart", "Тип": "PLA", "Твердість TPU": "—", "Колір": "Білий", "Вага 1 шт (г)": 1000, "Кількість котушок": 1, "Ціна (₴)": 450.0, "Статус": "Запакована (нова)"},
            {"Бренд": "Daniparts", "Тип": "PETG", "Твердість TPU": "—", "Колір": "Сірий", "Вага 1 шт (г)": 1000, "Кількість котушок": 1, "Ціна (₴)": 298.0, "Статус": "Запакована (нова)"},
        ]
        st.session_state["batch_inventory_df"] = pd.DataFrame(initial_data)

    edited_df = st.data_editor(
        st.session_state["batch_inventory_df"],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Бренд": st.column_config.SelectboxColumn("Бренд", options=POPULAR_BRANDS, required=True),
            "Тип": st.column_config.SelectboxColumn("Тип", options=["PETG", "CoPE", "PLA", "TPU", "ABS", "ASA", "Nylon", "PCTG"], required=True),
            "Твердість TPU": st.column_config.SelectboxColumn("Твердість TPU", options=["—", "95A", "90A", "85A", "40D"]),
            "Колір": st.column_config.TextColumn("Колір", help="Введіть будь-який колір вручну, наприклад: темно-зелений", required=True),
            "Вага 1 шт (г)": st.column_config.NumberColumn("Вага 1 шт (г)", min_value=50, max_value=5000, step=50, required=True),
            "Кількість котушок": st.column_config.NumberColumn("Кількість котушок", min_value=1, max_value=50, step=1, required=True),
            "Ціна (₴)": st.column_config.NumberColumn("Ціна (₴)", min_value=0.0, step=10.0, required=True),
            "Статус": st.column_config.SelectboxColumn("Статус", options=["Запакована (нова)", "В роботі"], required=True),
        },
        key="batch_data_editor",
    )

    col_save, col_clear = st.columns([3, 1])

    with col_save:
        if st.button("💾 Зберегти весь список на склад", type="primary", use_container_width=True, key="btn_save_batch"):
            if edited_df is None or len(edited_df) == 0:
                st.warning("Таблиця порожня. Додайте хоча б один рядок.")
                return

            today_iso = date.today().isoformat()
            total_added = 0

            for idx, row in edited_df.iterrows():
                brand = str(row.get("Бренд", "MonoFilament")).strip()
                ptype = str(row.get("Тип", "PLA")).strip()
                color = str(row.get("Колір", "Чорний")).strip()
                hardness_raw = str(row.get("Твердість TPU", "—")).strip()
                hardness = hardness_raw if hardness_raw != "—" and ptype == "TPU" else None

                try:
                    weight_g = int(row.get("Вага 1 шт (г)") or 1000)
                except Exception:
                    weight_g = 1000

                try:
                    qty = int(row.get("Кількість котушок") or 1)
                except Exception:
                    qty = 1

                try:
                    price_val = float(row.get("Ціна (₴)") or 0.0)
                except Exception:
                    price_val = 0.0

                st_disp = str(row.get("Статус", "Запакована (нова)")).strip()
                st_key = "sealed" if st_disp == "Запакована (нова)" else "active"

                for _ in range(qty):
                    spool = {
                        "brand": brand,
                        "store_name": brand,
                        "plastic_type": ptype,
                        "color": color,
                        "hardness": hardness,
                        "initial_weight_g": weight_g,
                        "current_weight_g": weight_g,
                        "empty_spool_weight_g": DEFAULT_EMPTY_SPOOL_G,
                        "purchase_price": price_val,
                        "purchase_date": today_iso,
                        "status": st_key,
                        "notes": "Пакетне занесення списком",
                        "snapshot_id": None,
                    }
                    queries.add_spool(spool)
                    total_added += 1

            st.success(f"🎉 Успішно збережено {total_added} котушок на ваш склад!")
            st.rerun()

    with col_clear:
        if st.button("🔄 Скинути таблицю", use_container_width=True, key="btn_clear_batch"):
            st.session_state["batch_inventory_df"] = pd.DataFrame([
                {"Бренд": "MonoFilament", "Тип": "PETG", "Твердість TPU": "—", "Колір": "Чорний", "Вага 1 шт (г)": 1000, "Кількість котушок": 1, "Ціна (₴)": 500.0, "Статус": "Запакована (нова)"}
            ])
            st.rerun()
