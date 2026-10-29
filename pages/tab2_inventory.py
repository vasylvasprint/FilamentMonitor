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
from db.colors import get_color_hex, render_color_badge

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
    "Devil Design",
    "Polymaker",
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


# ── Color Palette Helper with Database Persistence ────────────────────────────

def _get_combined_color_options() -> List[str]:
    """Retrieve all available colors from DB, standard list, and user additions."""
    try:
        db_colors = queries.get_distinct_colors()
    except Exception:
        db_colors = []

    # Merge standard colors and DB colors
    seen = set()
    palette = []
    for c in STANDARD_COLORS + db_colors:
        c_clean = str(c).strip()
        if c_clean and c_clean.lower() not in seen and c_clean not in ("—", "nan", "None"):
            seen.add(c_clean.lower())
            palette.append(c_clean)

    return palette


def _color_selectbox_with_custom(label: str, key_prefix: str) -> str:
    """Render a convenient combined selectbox with option to enter a new custom color.
    
    Automatically persists newly typed custom colors to the database so they are
    available in all dropdowns for future use.
    """
    palette = _get_combined_color_options()
    custom_sentinel = "✏️ Ввести свій колір / відтінок..."
    options = palette + [custom_sentinel]

    select_key = f"{key_prefix}_color_sel"
    
    # Check if a custom color was just added in this session
    default_index = 0
    if st.session_state.get(f"{key_prefix}_chosen_color") in palette:
        default_index = palette.index(st.session_state[f"{key_prefix}_chosen_color"])

    chosen = st.selectbox(label, options=options, index=default_index, key=select_key)

    if chosen == custom_sentinel:
        custom_key = f"{key_prefix}_color_custom_input"
        custom_input = st.text_input(
            "Введіть точну назву або відтінок кольору *",
            placeholder="наприклад: м'ятний, дуб, слонової кістки, хакі, ультрамарин...",
            key=custom_key,
            help="Система автоматично підбере точний HEX-відтінок за назвою",
        )
        final_color = custom_input.strip() if custom_input.strip() else "Чорний"

        # Live visual indicator preview
        hex_preview = get_color_hex(final_color)
        badge_html = render_color_badge(final_color, size=24, show_text=True)
        st.markdown(
            f"<div style='margin-top: -6px; margin-bottom: 8px; padding: 4px 8px; background: rgba(255,255,255,0.05); border-radius: 6px;'>"
            f"<b>Індикатор:</b> {badge_html} &nbsp;<code>{hex_preview}</code>"
            f"</div>",
            unsafe_allow_html=True,
        )

        save_btn_col1, save_btn_col2 = st.columns([2, 1])
        with save_btn_col1:
            if st.button("💾 Зберегти цей колір у список", key=f"{key_prefix}_btn_save_color", use_container_width=True):
                queries.add_custom_color(final_color, hex_preview)
                st.session_state[f"{key_prefix}_chosen_color"] = final_color
                st.success(f"Колір «{final_color}» збережено в базу!")
                st.rerun()

        return final_color
    else:
        # Display current color indicator pill
        badge_html = render_color_badge(chosen, size=22, show_text=True)
        st.markdown(
            f"<div style='margin-top: -6px; margin-bottom: 6px; font-size: 0.9rem;'>"
            f"{badge_html}"
            f"</div>",
            unsafe_allow_html=True,
        )
        return chosen


# ══════════════════════════════════════════════════════════════════════════════
#  Main render entry point
# ══════════════════════════════════════════════════════════════════════════════

def render():
    """Render the inventory management tab."""
    st.header("📦 Мій склад філаменту")
    
    # Prominent summary and stock alerts
    _render_summary()

    st.markdown("<hr style='margin: 12px 0 20px 0;'>", unsafe_allow_html=True)

    inv_tab1, inv_tab2 = st.tabs(["📋 Мої котушки", "➕ Додати котушку"])
    with inv_tab1:
        _render_inventory_view()
    with inv_tab2:
        _render_add_spool_tab()


# ══════════════════════════════════════════════════════════════════════════════
#  Summary banner & Low-stock Alerts (< 200g)
# ══════════════════════════════════════════════════════════════════════════════

def _render_summary():
    """Display summary banner and visual alerts for low stock (<200g)."""
    spools = queries.get_inventory(status_filter=["active", "sealed"])
    total_spools = len(spools)
    total_g = sum(s["current_weight_g"] for s in spools)
    total_kg = total_g / 1000.0
    total_value = sum(
        s["purchase_price"] * (s["current_weight_g"] / max(s["initial_weight_g"], 1))
        for s in spools
    )
    
    # Low stock is < 200g, critical is < 100g
    low_stock = [s for s in spools if s["current_weight_g"] < LOW_STOCK_ALERT_G]
    critical_stock = [s for s in spools if s["current_weight_g"] < CRITICAL_STOCK_ALERT_G]

    # Gradient Top Banner
    st.markdown(
        f"""
        <div style='background: linear-gradient(90deg, #1e3a8a 0%, #2563eb 100%); color: #ffffff;
                    padding: 16px 24px; border-radius: 10px; margin-bottom: 14px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.12);'>
          <div style='font-size: 1.35rem; font-weight: 700; letter-spacing: 0.3px;'>
            📦 Всього на складі: {total_spools} котушок &nbsp;|&nbsp; Загальна вага: {total_kg:.2f} кг
          </div>
          <div style='font-size: 0.95rem; opacity: 0.92; margin-top: 4px;'>
            Загальна оціночна вартість залишків: <b>{total_value:.0f} ₴</b> &nbsp;•&nbsp; Активні та нові котушки
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Prominent visual notification if any plastic is low on stock (<200g)
    if critical_stock:
        crit_items = []
        for s in critical_stock:
            dot = render_color_badge(s.get("color"), size=16)
            crit_items.append(f"{dot} <b>{s['plastic_type']}</b> {s.get('color','')} ({s['current_weight_g']}г)")
        st.error(
            f"🔴 **КРИТИЧНО МАЛО ФІЛАМЕНТУ (< {CRITICAL_STOCK_ALERT_G} г)!** "
            f"Терміново замовте нові котушки: " + " &nbsp;•&nbsp; ".join(crit_items),
            icon="🚨",
        )
    elif low_stock:
        low_items = []
        for s in low_stock:
            dot = render_color_badge(s.get("color"), size=16)
            low_items.append(f"{dot} <b>{s['plastic_type']}</b> {s.get('color','')} ({s['current_weight_g']}г)")
        st.warning(
            f"🟡 **СПОСТЕРЕЖЕННЯ: Залишок менше {LOW_STOCK_ALERT_G} г!** "
            f"Рекомендуємо поповнити запаси: " + " &nbsp;•&nbsp; ".join(low_items),
            icon="⚠️",
        )

    if not spools:
        st.info("ℹ️ Ваш домашній склад порожній. Перейдіть на підвкладку «➕ Додати котушку», щоб занести свої запаси.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Котушок на складі", total_spools)
    col2.metric("Всього пластику", f"{total_kg:.2f} кг")
    col3.metric("Вартість залишків", f"{total_value:.0f} ₴")
    col4.metric(
        "⚠️ Мало (< 200г)",
        len(low_stock),
        delta=f"-{len(critical_stock)} критичних (<100г)" if critical_stock else "В нормі",
        delta_color="inverse" if low_stock else "normal",
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Grouping logic (Group by Brand + Plastic Type + Color)
# ══════════════════════════════════════════════════════════════════════════════

def _group_key(spool: dict) -> tuple:
    return (
        (spool.get("brand") or "").strip().lower(),
        (spool.get("plastic_type") or "").strip().lower(),
        (spool.get("color") or "").strip().lower(),
    )


def _build_groups(spools: list) -> list:
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
        rep = g["spools"][0]
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
#  Inventory View — Grouped Spool Cards
# ══════════════════════════════════════════════════════════════════════════════

def _render_inventory_view():
    col1, col2 = st.columns(2)
    with col1:
        status_filter_display = st.multiselect(
            "Статус котушок",
            options=list(SPOOL_STATUSES.values()),
            default=["В роботі", "Запакована (нова)"],
        )
    with col2:
        type_filter = st.multiselect("Фільтр за типом пластику", options=PLASTIC_TYPES, default=[])

    status_reverse = {v: k for k, v in SPOOL_STATUSES.items()}
    status_keys = [status_reverse[s] for s in status_filter_display if s in status_reverse]
    spools = queries.get_inventory(status_filter=status_keys if status_keys else None)
    if type_filter:
        spools = [s for s in spools if s["plastic_type"] in type_filter]

    if not spools:
        st.info("Не знайдено котушок за обраними фільтрами.")
        return

    groups = _build_groups(spools)
    
    # Sort order: Critical (<100g) first, then Low (<200g), then Normal
    groups.sort(key=lambda g: (
        0 if g["min_current_g"] < CRITICAL_STOCK_ALERT_G
        else 1 if g["min_current_g"] < LOW_STOCK_ALERT_G
        else 2,
        -g["total_current_g"]
    ))

    cols = st.columns(2)
    for i, group in enumerate(groups):
        with cols[i % 2]:
            _render_group_card(group)


def _render_group_card(group: dict):
    rep = group["representative"]
    count = group["count"]
    total_current_g = group["total_current_g"]
    total_initial_g = group["total_initial_g"]
    min_g = group["min_current_g"]
    pct = min(100.0, (total_current_g / max(total_initial_g, 1)) * 100)

    is_critical = min_g < CRITICAL_STOCK_ALERT_G
    is_low = min_g < LOW_STOCK_ALERT_G

    plastic_type = rep.get("plastic_type", "?")
    color = rep.get("color", "") or ""
    brand = rep.get("brand", "") or ""
    hardness = rep.get("hardness", "")
    type_display = plastic_type + (f" {hardness}" if hardness and hardness not in ("Невідомо", "—") else "")

    # Visual Color Indicator
    dot_html = render_color_badge(color, size=24)

    # Quantity badge
    qty_badge = (
        f"<span style='background: #2563EB; color: #fff; border-radius: 12px; "
        f"padding: 2px 10px; font-size: 0.82rem; font-weight: 700; margin-left: 6px;'>"
        f"{count} шт</span>"
        if count > 1 else ""
    )

    # Visual Alert Badges for Low Stock (<200g)
    if is_critical:
        alert_badge = (
            f"<span style='background: #DC2626; color: #fff; border-radius: 8px; "
            f"padding: 2px 8px; font-size: 0.78rem; font-weight: 600; margin-left: 6px;'>"
            f"🔴 &lt; {CRITICAL_STOCK_ALERT_G}г КРИТИЧНО!</span>"
        )
    elif is_low:
        alert_badge = (
            f"<span style='background: #D97706; color: #fff; border-radius: 8px; "
            f"padding: 2px 8px; font-size: 0.78rem; font-weight: 600; margin-left: 6px;'>"
            f"🟡 &lt; {LOW_STOCK_ALERT_G}г МАЛО ЗАЛИШКУ</span>"
        )
    else:
        alert_badge = ""

    title_html = (
        f"<div style='font-size: 1.15rem; font-weight: 600; margin-bottom: 4px; display: flex; align-items: center; flex-wrap: wrap;'>"
        f"{dot_html}&nbsp; <span>{type_display}</span>"
        + (f" — <span style='color: #F8FAFC;'>{color}</span>" if color else "")
        + (f" <span style='opacity: 0.7; font-size: 0.95rem; font-weight: 400; margin-left: 4px;'>({brand})</span>" if brand else "")
        + qty_badge + alert_badge
        + f"</div>"
    )

    with st.container(border=True):
        st.markdown(title_html, unsafe_allow_html=True)

        st.progress(
            pct / 100,
            text=f"Сумарно: {total_current_g} г ({total_current_g/1000:.2f} кг) / {total_initial_g} г ({pct:.0f}%)",
        )
        st.caption(f"💰 Залишкова вартість: **{group['total_value']:.0f} ₴**")

        if is_low:
            if is_critical:
                st.error(f"🚨 Увага: на складі залишилось лише **{min_g} г** цього пластику. Рекомендуємо замовити котушку.")
            else:
                st.warning(f"⚠️ Увага: залишок пластику менше **{LOW_STOCK_ALERT_G} г** ({min_g} г). Вчасно поповніть склад.")

            if st.button(
                f"🔍 Знайти найкращу ціну на {plastic_type} у магазинах",
                key=f"chk_price_{'_'.join(str(x) for x in group['key'])}",
                use_container_width=True,
            ):
                st.session_state["price_filter_type"] = plastic_type
                st.session_state["active_tab"] = 0
                st.rerun()

        # Expandable individual spool management
        label_count = "котушка" if count == 1 else "котушок"
        with st.expander(f"📋 Деталі та індивідуальні котушки ({count} {label_count})", expanded=False):
            for sp in group["spools"]:
                _render_individual_spool(sp)


def _render_individual_spool(spool: dict):
    """Render a single spool row with weigh / status / delete actions."""
    spool_id = spool["id"]
    current_g = spool["current_weight_g"]
    initial_g = spool["initial_weight_g"]
    pct = min(100.0, (current_g / max(initial_g, 1)) * 100)
    status = SPOOL_STATUSES.get(spool.get("status", "active"), "В роботі")
    price = spool.get("purchase_price", 0)
    store = spool.get("store_name", "")

    is_crit = current_g < CRITICAL_STOCK_ALERT_G
    is_low = current_g < LOW_STOCK_ALERT_G
    badge = ""
    if is_crit:
        badge = f" <span style='color: #EF4444; font-weight: 700;'>[🔴 &lt; {CRITICAL_STOCK_ALERT_G}г!]</span>"
    elif is_low:
        badge = f" <span style='color: #F59E0B; font-weight: 600;'>[🟡 &lt; {LOW_STOCK_ALERT_G}г]</span>"

    st.markdown(
        f"**Котушка #{spool_id}**{badge} &nbsp;|&nbsp; **{current_g} г** / {initial_g} г ({pct:.0f}%) "
        f"&nbsp;|&nbsp; {status} &nbsp;|&nbsp; {price:.0f} ₴"
        + (f" &nbsp;|&nbsp; 📍 {store}" if store else ""),
        unsafe_allow_html=True,
    )

    ac1, ac2, ac3 = st.columns([1.5, 2, 1.5])
    with ac1:
        if st.button("⚖️ Зважити", key=f"weigh_{spool_id}", use_container_width=True):
            st.session_state[f"weighing_{spool_id}"] = True
    with ac2:
        status_opts = list(SPOOL_STATUSES.values())
        cur_disp = SPOOL_STATUSES.get(spool.get("status", "active"), "В роботі")
        new_disp = st.selectbox(
            "Статус", options=status_opts,
            index=status_opts.index(cur_disp) if cur_disp in status_opts else 0,
            key=f"status_sel_{spool_id}", label_visibility="collapsed",
        )
        if new_disp != cur_disp:
            rev = {v: k for k, v in SPOOL_STATUSES.items()}
            queries.update_spool_status(spool_id, rev[new_disp])
            st.rerun()
    with ac3:
        if st.button("🗑️ Видалити", key=f"del_{spool_id}", use_container_width=True):
            st.session_state[f"confirm_del_{spool_id}"] = True

    # Weigh modal / inline form
    if st.session_state.get(f"weighing_{spool_id}"):
        with st.form(key=f"weigh_form_{spool_id}"):
            st.subheader("⚖️ Швидке зважування на кухонних вагах")
            empty_g = spool.get("empty_spool_weight_g", DEFAULT_EMPTY_SPOOL_G)
            gross_g = st.number_input(
                "Загальна вага котушки з вагів (брутто, г)", min_value=0,
                value=int(current_g + empty_g), step=1,
                help=f"Введіть показник з ваг. Програма автоматично відніме тару ({empty_g} г).",
            )
            net_g = max(0, gross_g - empty_g)
            st.info(f"Чистий залишок пластику: **{net_g} г** (брутто {gross_g} г − тара {empty_g} г)")
            
            ok, cancel = st.columns(2)
            with ok:
                if st.form_submit_button("✅ Зберегти залишок", use_container_width=True):
                    queries.update_spool_weight(spool_id, net_g)
                    st.session_state[f"weighing_{spool_id}"] = False
                    st.success(f"Залишок оновлено до {net_g} г!")
                    st.rerun()
            with cancel:
                if st.form_submit_button("❌ Скасувати", use_container_width=True):
                    st.session_state[f"weighing_{spool_id}"] = False
                    st.rerun()

    if st.session_state.get(f"confirm_del_{spool_id}"):
        st.error(f"Видалити котушку #{spool_id} зі складу? Дію не можна буде скасувати.")
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

    st.markdown("<hr style='margin: 8px 0; border: none; border-top: 1px solid rgba(128,128,128,0.15);'>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  Add Spool Form — Combined Selectbox with Custom Color Creation
# ══════════════════════════════════════════════════════════════════════════════

def _render_add_spool_tab():
    st.subheader("⚡ Швидкий конструктор котушки (в один клік)")
    st.caption("Оберіть бренд, тип та колір із випадаючого списку. Також можна вписати будь-який власний відтінок:")

    with st.container(border=True):
        col1, col2, col3 = st.columns([2.5, 2.5, 2.0])

        with col1:
            brand_choice = st.selectbox("Бренд / Виробник *", options=POPULAR_BRANDS, index=0, key="c_brand_choice")
            if brand_choice == "Інший":
                custom_brand = st.text_input("Введіть назву бренду *", placeholder="Наприклад: Devil Design")
                actual_brand = custom_brand.strip() or "Інший"
            else:
                actual_brand = brand_choice

            # Combined dropdown with custom entry capability & spectrum matching
            color_choice = _color_selectbox_with_custom("Колір *", key_prefix="c")

        with col2:
            plastic_choice = st.selectbox("Тип пластику *", options=CONSTRUCTOR_PLASTIC_TYPES, index=0, key="c_plastic_choice")
            if plastic_choice == "TPU / Flex":
                hardness_choice = st.selectbox("Твердість TPU", options=["95A", "90A", "85A", "40D", "Невідомо"], index=0, key="c_hardness_choice")
                actual_type = "TPU"
                actual_hardness = hardness_choice if hardness_choice != "Невідомо" else None
            else:
                actual_type = plastic_choice
                actual_hardness = None

            weight_preset = st.selectbox("Вага нитки (г) *", options=WEIGHT_OPTIONS, index=0, key="c_weight_preset")
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
                    "Точна вага нитки (г) *", min_value=10, max_value=5000,
                    value=1000, step=50, key="c_custom_weight",
                )

        with col3:
            quantity = st.number_input("Кількість котушок (шт.)", min_value=1, max_value=50, value=1, step=1, key="c_quantity")
            price = st.number_input("Ціна за 1 котушку (₴)", min_value=0.0, value=500.0, step=25.0, key="c_price")
            status_display = st.selectbox("Статус", options=["Запакована (нова)", "В роботі"], index=0, key="c_status_display")
            status_key = "sealed" if status_display == "Запакована (нова)" else "active"

        btn_text = f"➕ Додати на склад ({quantity} шт · {actual_brand} {actual_type} {color_choice}, {actual_weight_g} г)"
        if st.button(btn_text, type="primary", use_container_width=True, key="btn_add_constructor"):
            today_iso = date.today().isoformat()
            
            # Persist custom color if it was newly added
            queries.add_custom_color(color_choice, get_color_hex(color_choice))

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
                queries.add_spool(spool)

            st.success(
                f"🎉 Успішно додано {quantity} котушок «{actual_brand} {actual_type} {color_choice}» "
                f"({actual_weight_g} г, {price:.0f} ₴) на склад!"
            )
            st.rerun()

    st.markdown("<hr style='margin: 25px 0 15px;'>", unsafe_allow_html=True)

    # ── Interactive Batch Table ───────────────────────────────────────────────
    st.subheader("⚡ Швидке додавання списком (Таблиця)")
    st.caption("Додайте одразу кілька котушок списком. Колір можна вибрати або вписати вручну:")

    if "batch_inventory_df" not in st.session_state:
        st.session_state["batch_inventory_df"] = pd.DataFrame([
            {"Бренд": "MonoFilament", "Тип": "PETG", "Твердість TPU": "—", "Колір": "Чорний", "Вага 1 шт (г)": 1000, "Кількість котушок": 1, "Ціна (₴)": 500.0, "Статус": "Запакована (нова)"},
            {"Бренд": "3D-Smart",     "Тип": "PLA",  "Твердість TPU": "—", "Колір": "Білий",   "Вага 1 шт (г)": 1000, "Кількість котушок": 1, "Ціна (₴)": 450.0, "Статус": "Запакована (нова)"},
            {"Бренд": "Daniparts",    "Тип": "PETG", "Твердість TPU": "—", "Колір": "Сірий",   "Вага 1 шт (г)": 1000, "Кількість котушок": 1, "Ціна (₴)": 298.0, "Статус": "Запакована (нова)"},
        ])

    edited_df = st.data_editor(
        st.session_state["batch_inventory_df"],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Бренд":           st.column_config.SelectboxColumn("Бренд", options=POPULAR_BRANDS, required=True),
            "Тип":             st.column_config.SelectboxColumn("Тип",   options=["PETG","CoPE","PLA","TPU","ABS","ASA","Nylon","PCTG"], required=True),
            "Твердість TPU":   st.column_config.SelectboxColumn("Твердість TPU", options=["—","95A","90A","85A","40D"]),
            "Колір":           st.column_config.TextColumn("Колір", help="Будь-яка назва: темно-зелений, м'ятний, дуб, ультрамарин…", required=True),
            "Вага 1 шт (г)":  st.column_config.NumberColumn("Вага 1 шт (г)", min_value=50, max_value=5000, step=50, required=True),
            "Кількість котушок": st.column_config.NumberColumn("Кількість", min_value=1, max_value=50, step=1, required=True),
            "Ціна (₴)":       st.column_config.NumberColumn("Ціна (₴)", min_value=0.0, step=10.0, required=True),
            "Статус":          st.column_config.SelectboxColumn("Статус", options=["Запакована (нова)","В роботі"], required=True),
        },
        key="batch_data_editor",
    )

    col_save, col_clear = st.columns([3, 1])
    with col_save:
        if st.button("💾 Зберегти список на склад", type="primary", use_container_width=True, key="btn_save_batch"):
            if edited_df is None or len(edited_df) == 0:
                st.warning("Таблиця порожня. Додайте хоча б один рядок.")
                return
            today_iso = date.today().isoformat()
            total_added = 0
            for _, row in edited_df.iterrows():
                brand = str(row.get("Бренд", "MonoFilament")).strip()
                ptype = str(row.get("Тип", "PLA")).strip()
                color = str(row.get("Колір", "Чорний")).strip()
                h_raw = str(row.get("Твердість TPU", "—")).strip()
                hardness = h_raw if h_raw != "—" and ptype == "TPU" else None
                try:    weight_g  = int(row.get("Вага 1 шт (г)") or 1000)
                except: weight_g  = 1000
                try:    qty       = int(row.get("Кількість котушок") or 1)
                except: qty       = 1
                try:    price_val = float(row.get("Ціна (₴)") or 0.0)
                except: price_val = 0.0
                st_key = "sealed" if "нова" in str(row.get("Статус", "")).lower() else "active"
                
                # Persist color
                queries.add_custom_color(color, get_color_hex(color))

                for _ in range(qty):
                    queries.add_spool({
                        "brand": brand, "store_name": brand, "plastic_type": ptype,
                        "color": color, "hardness": hardness,
                        "initial_weight_g": weight_g, "current_weight_g": weight_g,
                        "empty_spool_weight_g": DEFAULT_EMPTY_SPOOL_G,
                        "purchase_price": price_val, "purchase_date": today_iso,
                        "status": st_key, "notes": "Пакетне занесення списком", "snapshot_id": None,
                    })
                    total_added += 1
            st.success(f"🎉 Успішно збережено {total_added} котушок на ваш склад!")
            st.rerun()
    with col_clear:
        if st.button("🔄 Скинути таблицю", use_container_width=True, key="btn_clear_batch"):
            st.session_state["batch_inventory_df"] = pd.DataFrame([
                {"Бренд": "MonoFilament", "Тип": "PETG", "Твердість TPU": "—", "Колір": "Чорний", "Вага 1 шт (г)": 1000, "Кількість котушок": 1, "Ціна (₴)": 500.0, "Статус": "Запакована (нова)"}
            ])
            st.rerun()
