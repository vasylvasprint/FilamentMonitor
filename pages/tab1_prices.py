"""Tab 1: Price monitoring across Ukrainian filament stores."""
import asyncio
import logging
import pandas as pd
import streamlit as st

from config import PLASTIC_TYPES, TPU_HARDNESS, STANDARD_COLORS
from db import queries
from scrapers import run_scraper
from scrapers.utils import clean_url

logger = logging.getLogger(__name__)


def render():
    """Render the price monitoring tab."""
    st.header("🛒 Моніторинг цін у магазинах")

    # --- Scraping controls row
    col1, col2, col3 = st.columns([2.5, 3, 2.5])

    with col1:
        if st.button("🔄 Оновити всі ціни", type="primary", use_container_width=True):
            _run_all_scrapers()

    with col2:
        last_scrape = queries.get_last_scrape_time()
        if last_scrape:
            st.caption(f"🕒 Останнє оновлення: **{last_scrape[:16].replace('T', ' ')}**")
        else:
            st.caption("🕒 Дані ще не завантажені")

    with col3:
        with st.expander("⚙️ Керування магазинами"):
            _render_store_management()

    # --- Add custom URL
    with st.expander("➕ Додати свій URL магазину / категорії"):
        _render_add_url()

    st.markdown("---")

    # --- Filters
    st.subheader("🔍 Фільтри")

    # Universal Search Row
    search_query = st.text_input(
        "🔎 Пошук за назвою або кольором",
        placeholder="Пошук (наприклад: petg чорний, kingroon, sunlu, flex, латунь...)",
        help="Шукає збіг слів одночасно у назві, кольорі, типі пластику та бренді",
    )

    fcol1, fcol2, fcol3, fcol4 = st.columns([2, 2, 1.5, 1.5])

    with fcol1:
        selected_types = st.multiselect(
            "Тип пластику",
            options=PLASTIC_TYPES,
            default=[],
            placeholder="Всі типи (PETG, PLA...)",
        )

    with fcol2:
        available_colors = queries.get_distinct_colors()
        selected_colors = st.multiselect(
            "Колір",
            options=available_colors,
            default=[],
            placeholder="Всі кольори",
        )

    with fcol3:
        selected_hardness = st.selectbox(
            "Твердість TPU",
            options=["Всі"] + TPU_HARDNESS,
        )

    with fcol4:
        in_stock_only = st.toggle("Тільки в наявності", value=True)

    fcol5, fcol6 = st.columns([3, 2])
    with fcol5:
        stores = queries.get_all_stores()
        store_options = {s["name"]: s["id"] for s in stores}
        selected_stores = st.multiselect(
            "Магазини",
            options=list(store_options.keys()),
            default=[],
            placeholder="Всі магазини",
            help="Залиште порожнім, щоб показувати товари з усіх магазинів",
        )

    with fcol6:
        sort_by = st.selectbox(
            "Сортування",
            [
                "Ціна за 1 кг (від дешевих) ↑",
                "Ціна за 1 кг (від дорогих) ↓",
                "Ціна за котушку ↑",
                "Ціна за котушку ↓",
                "Назва А-Я",
                "Магазин А-Я",
            ],
        )

    st.markdown("---")

    # --- Load and filter data
    # IMPORTANT: if selected_stores is empty, store_ids MUST BE None -> queries all stores!
    store_ids = [store_options[s] for s in selected_stores if s in store_options] if selected_stores else None
    hardness = None if selected_hardness == "Всі" else selected_hardness

    prices = queries.get_latest_prices(
        plastic_types=selected_types if selected_types else None,
        in_stock_only=in_stock_only,
        store_ids=store_ids,
        selected_colors=selected_colors if selected_colors else None,
        color_search=search_query if search_query else None,
        search_query=search_query if search_query else None,
        hardness=hardness,
    )

    total_in_db = queries.get_total_snapshots_count()

    if not prices:
        if total_in_db == 0:
            st.info("🔍 У базі ще немає збережених цін. Натисніть кнопку «🔄 Оновити всі ціни», щоб спарсити актуальні дані з магазинів.")
        else:
            st.warning("⚠️ За обраними фільтрами товарів не знайдено. Спробуйте змінити колір або тип пластику.")
        return

    df = pd.DataFrame(prices)

    # Clean nan values
    for col in ["color", "brand", "plastic_type", "hardness"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: "—" if (pd.isna(x) or str(x).lower() == "nan" or not str(x).strip()) else str(x)
            )

    # Apply sorting
    sort_map = {
        "Ціна за 1 кг (від дешевих) ↑": ("price_per_kg", True),
        "Ціна за 1 кг (від дорогих) ↓": ("price_per_kg", False),
        "Ціна за котушку ↑": ("price_uah", True),
        "Ціна за котушку ↓": ("price_uah", False),
        "Назва А-Я": ("product_name", True),
        "Магазин А-Я": ("store_name", True),
    }
    sort_col, ascending = sort_map[sort_by]
    if sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=ascending, na_position="last")

    st.markdown(f"Знайдено: **{len(df)}** позицій (всі котушки нормалізовані до ≤ 1.1 кг)")

    # --- Render product table
    _render_price_table(df)


def _render_price_table(df: pd.DataFrame):
    """Render price table with structured columns and action buttons."""
    page_size = 25
    total = len(df)
    total_pages = max(1, (total + page_size - 1) // page_size)

    col_pg, _ = st.columns([2, 5])
    with col_pg:
        if total_pages > 1:
            page = st.number_input("Сторінка", min_value=1, max_value=total_pages, value=1, step=1)
        else:
            page = 1

    start = (page - 1) * page_size
    end = start + page_size
    page_df = df.iloc[start:end]

    # Table Header
    header_cols = st.columns([1.5, 4.0, 1.1, 1.3, 1.1, 1.3, 1.5, 1.1, 1.2])
    header_cols[0].markdown("**Магазин**")
    header_cols[1].markdown("**Назва товару**")
    header_cols[2].markdown("**Тип**")
    header_cols[3].markdown("**Колір**")
    header_cols[4].markdown("**Вага**")
    header_cols[5].markdown("**Ціна**")
    header_cols[6].markdown("**Ціна / 1 кг**")
    header_cols[7].markdown("**Стан**")
    header_cols[8].markdown("**Дія**")

    st.markdown("<hr style='margin: 4px 0 10px 0;'>", unsafe_allow_html=True)

    # Render each row
    for i, (idx, row) in enumerate(page_df.iterrows()):
        r_cols = st.columns([1.5, 4.0, 1.1, 1.3, 1.1, 1.3, 1.5, 1.1, 1.2])

        store = row.get("store_name", "—")
        name = row.get("product_name", "—")
        ptype = row.get("plastic_type", "—") or "—"
        color = row.get("color", "—") or "—"
        if str(color).lower() == "nan":
            color = "—"

        weight = row.get("weight_g")
        weight_str = f"{weight:.0f} г" if pd.notna(weight) and weight else "1000 г"

        price = row.get("price_uah")
        price_str = f"**{price:.0f} ₴**" if pd.notna(price) and price else "—"

        ppkg = row.get("price_per_kg")
        ppkg_str = f"<span style='color:#1e7e34; font-weight:bold;'>{ppkg:.0f} ₴/кг</span>" if pd.notna(ppkg) and ppkg else "—"

        in_stock = bool(row.get("in_stock", True))
        stock_badge = "🟢 В наявності" if in_stock else "🔴 Немає"

        url = row.get("product_url")
        if url:
            name_html = f"<a href='{url}' target='_blank' style='text-decoration:none; font-weight:500;'>{name}</a>"
        else:
            name_html = f"<span>{name}</span>"

        r_cols[0].markdown(
            f"<span style='background:#f0f2f6; padding:2px 6px; border-radius:4px; font-size:0.85rem;'>{store}</span>",
            unsafe_allow_html=True,
        )
        r_cols[1].markdown(name_html, unsafe_allow_html=True)
        r_cols[2].markdown(f"**{ptype}**")
        r_cols[3].text(color)
        r_cols[4].text(weight_str)
        r_cols[5].markdown(price_str)
        r_cols[6].markdown(ppkg_str, unsafe_allow_html=True)
        r_cols[7].markdown(f"<span style='font-size:0.85rem;'>{stock_badge}</span>", unsafe_allow_html=True)

        btn_key = f"add_inv_{row.get('id', idx)}_{i}"
        with r_cols[8]:
            if st.button("➕ Склад", key=btn_key, help="Додати цю котушку на мій склад", use_container_width=True):
                _add_to_inventory_from_snapshot(row)

        st.markdown("<hr style='margin: 4px 0 6px 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)

    if total_pages > 1:
        st.caption(f"Сторінка {page} з {total_pages} (Показано {len(page_df)} з {total} товарів)")


def _add_to_inventory_from_snapshot(row: dict):
    """Add a price snapshot product directly to inventory."""
    from config import DEFAULT_EMPTY_SPOOL_G
    from datetime import date

    weight_g = int(row.get("weight_g") or 1000)
    price = float(row.get("price_uah") or 0)
    color = row.get("color")
    if str(color).lower() == "nan":
        color = "—"

    spool = {
        "brand": row.get("brand") or row.get("store_name"),
        "store_name": row.get("store_name"),
        "plastic_type": row.get("plastic_type") or "PLA",
        "color": color,
        "hardness": row.get("hardness"),
        "initial_weight_g": weight_g,
        "current_weight_g": weight_g,
        "empty_spool_weight_g": DEFAULT_EMPTY_SPOOL_G,
        "purchase_price": price,
        "purchase_date": date.today().isoformat(),
        "status": "sealed",
        "notes": f"Додано з моніторингу цін ({row.get('store_name')})",
        "snapshot_id": row.get("id"),
    }

    spool_id = queries.add_spool(spool)
    st.success(f"✅ Котушку «{spool['plastic_type']} {color}» ({weight_g} г, {price:.0f} ₴) успішно додано на ваш склад! (ID: {spool_id})")


def _render_store_management():
    """Render store enable/disable controls."""
    stores = queries.get_all_stores()
    for store in stores:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.text(store["name"])
        with col2:
            is_active = bool(store["is_active"])
            new_val = st.toggle(
                "Активний",
                value=is_active,
                key=f"store_toggle_{store['id']}",
                label_visibility="collapsed",
            )
            if new_val != is_active:
                queries.toggle_store_active(store["id"], new_val)
                st.rerun()


def _render_add_url():
    """Render form to add a custom URL."""
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        new_url = st.text_input("URL категорії або товару", placeholder="https://...")
    with col2:
        new_name = st.text_input("Назва магазину", placeholder="Назва (необов'язково)")
    with col3:
        st.write("")
        if st.button("Додати", use_container_width=True):
            if new_url:
                cleaned = clean_url(new_url.strip())
                from urllib.parse import urlparse
                parsed = urlparse(cleaned)
                base = f"{parsed.scheme}://{parsed.netloc}"
                name = new_name.strip() if new_name.strip() else parsed.netloc
                store_id = queries.add_custom_store(name, base, cleaned)
                st.success(f"✅ Магазин «{name}» додано! ID: {store_id}")
                st.rerun()
            else:
                st.error("Вкажіть URL")


def _run_all_scrapers():
    """Run all active store scrapers and save results."""
    stores = queries.get_all_stores(active_only=True)
    progress = st.progress(0, text="Підготовка...")
    status_placeholder = st.empty()

    total = len(stores)
    all_results = []

    for i, store in enumerate(stores):
        progress.progress((i) / total, text=f"Парсинг: {store['name']}...")
        status_placeholder.info(f"🔄 Опитування {store['name']}...")

        try:
            results = asyncio.run(run_scraper(store))
            if results:
                queries.save_price_snapshots(results)
                all_results.extend(results)
                status_placeholder.success(f"✅ {store['name']}: знайдено {len(results)} позицій")
            else:
                status_placeholder.warning(f"⚠️ {store['name']}: 0 позицій")
        except Exception as e:
            status_placeholder.error(f"❌ {store['name']}: помилка {e}")

        progress.progress((i + 1) / total, text=f"{store['name']} завершено")

    progress.progress(1.0, text="Готово!")
    status_placeholder.success(f"✅ Оновлення завершено! Збережено {len(all_results)} позицій.")
    st.rerun()
