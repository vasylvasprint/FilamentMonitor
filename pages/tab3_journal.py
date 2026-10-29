"""Tab 3: Print journal, filament deduction log, and Print Cost Estimator."""
import io
from datetime import datetime

import pandas as pd
import streamlit as st

from config import LOW_STOCK_ALERT_G, CRITICAL_STOCK_ALERT_G
from db import queries
from db.colors import render_color_badge
from gcode_parser.parser import parse_gcode_file


def render():
    """Render the print journal and cost estimator tab."""
    st.header("🖨️ Журнал друку та розрахунок собівартості")
    
    jt1, jt2, jt3 = st.tabs([
        "✂️ Швидке списання & Калькулятор собівартості",
        "📂 Імпорт зі слайсера (GCode / .3mf)",
        "📋 Журнал друку",
    ])
    
    with jt1:
        _render_quick_deduct()
    
    with jt2:
        _render_gcode_import()
    
    with jt3:
        _render_journal()


def _render_quick_deduct():
    """Quick filament deduction and full print cost estimator."""
    st.subheader("✂️ Калькулятор собівартості та швидке списання після друку")
    st.caption(
        "Розрахуйте повну собівартість надрукованої деталі (пластик + витрачена електроенергія) "
        "та спишіть вагу з котушки в 1 клік:"
    )
    
    # Get active spools from inventory
    spools = queries.get_inventory(status_filter=["active", "sealed"])
    if not spools:
        st.warning("⚠️ На складі немає активних котушок. Спочатку додайте котушку у вкладці «📦 Мій склад».")
        return
    
    # Build dictionary of spools with visual labels
    spool_options = {}
    for s in spools:
        spool_id = s["id"]
        ptype = s.get("plastic_type", "?")
        hardness = f" {s['hardness']}" if s.get("hardness") and s["hardness"] not in ("Невідомо", "—") else ""
        color = s.get("color") or ""
        brand = s.get("brand") or s.get("store_name") or "Котушка"
        current_g = s["current_weight_g"]
        
        # Calculate price per 1 kg for this spool
        init_g = max(int(s.get("initial_weight_g") or 1000), 1)
        price_val = float(s.get("purchase_price") or 0.0)
        price_per_kg = (price_val / init_g) * 1000.0
        
        warn_mark = " 🔴 <100г!" if current_g < CRITICAL_STOCK_ALERT_G else (" 🟡 <200г" if current_g < LOW_STOCK_ALERT_G else "")
        label = f"{ptype}{hardness} — {color} ({brand}) | Залишок: {current_g}г{warn_mark} | {price_per_kg:.0f} ₴/кг #{spool_id}"
        spool_options[label] = s
    
    selected_label = st.selectbox("🎯 Оберіть котушку зі складу *", options=list(spool_options.keys()), key="qd_spool_selector")
    selected_spool = spool_options[selected_label]
    
    # Spool parameters
    spool_id = selected_spool["id"]
    spool_color = selected_spool.get("color", "")
    spool_ptype = selected_spool.get("plastic_type", "PLA")
    spool_brand = selected_spool.get("brand", "")
    current_weight_g = float(selected_spool.get("current_weight_g") or 0.0)
    initial_weight_g = max(float(selected_spool.get("initial_weight_g") or 1000.0), 1.0)
    purchase_price = float(selected_spool.get("purchase_price") or 0.0)
    
    # Auto price per kg
    price_per_kg = (purchase_price / initial_weight_g) * 1000.0
    price_per_g = price_per_kg / 1000.0
    
    # Visual Spool Info Card
    dot_html = render_color_badge(spool_color, size=20)
    st.markdown(
        f"""
        <div style='background: rgba(37, 99, 235, 0.08); border: 1px solid rgba(37, 99, 235, 0.25);
                    padding: 10px 16px; border-radius: 8px; margin-bottom: 15px;'>
            {dot_html} <b>{spool_brand} {spool_ptype} {spool_color}</b> &nbsp;|&nbsp;
            Поточний залишок: <b>{current_weight_g:.0f} г</b> &nbsp;|&nbsp;
            Ціна котушки: <b>{purchase_price:.0f} ₴</b> &nbsp;|&nbsp;
            Ціна за 1 кг: <b>{price_per_kg:.1f} ₴/кг</b> ({price_per_g:.3f} ₴/г)
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Main model inputs
    col_p1, col_p2 = st.columns([3, 2])
    with col_p1:
        project_name = st.text_input(
            "Назва деталі / проєкту *",
            placeholder="наприклад: Кронштейн монітора, Корпус датчика, Вазочка...",
            key="qd_project_name",
        )
    with col_p2:
        is_failed = st.checkbox("❌ Невдалий друк (брак)", key="qd_is_failed", help="Позначити запис як брак для аналітики")
    
    col_w, col_t = st.columns(2)
    with col_w:
        # Default weight or preset
        if "qd_preset_weight" not in st.session_state:
            st.session_state["qd_preset_weight"] = 45.0
            
        model_weight_g = st.number_input(
            "Вага моделі в грамах (зі слайсера) *",
            min_value=0.1,
            max_value=float(max(current_weight_g + 100.0, 5000.0)),
            value=float(st.session_state["qd_preset_weight"]),
            step=1.0,
            key="qd_weight_input",
            help="Вкажіть вагу моделі, розраховану вашим слайсером (Bambu Studio, OrcaSlicer, Cura, PrusaSlicer)",
        )
    with col_t:
        print_time_hours = st.number_input(
            "Час друку (у годинах)",
            min_value=0.0,
            max_value=300.0,
            value=2.5,
            step=0.25,
            key="qd_time_hours",
            help="Тривалість друку для розрахунку витраченої електроенергії (наприклад: 2.5 год = 2 год 30 хв)",
        )
    
    # Quick presets buttons
    st.write("⚡ **Швидкі пресети ваги:**")
    btn_cols = st.columns(5)
    with btn_cols[0]:
        if st.button("5 г (продувка)", use_container_width=True, key="preset_5"):
            st.session_state["qd_preset_weight"] = 5.0
            st.rerun()
    with btn_cols[1]:
        if st.button("15 г (тест/кубик)", use_container_width=True, key="preset_15"):
            st.session_state["qd_preset_weight"] = 15.0
            st.rerun()
    with btn_cols[2]:
        if st.button("50 г", use_container_width=True, key="preset_50"):
            st.session_state["qd_preset_weight"] = 50.0
            st.rerun()
    with btn_cols[3]:
        if st.button("100 г", use_container_width=True, key="preset_100"):
            st.session_state["qd_preset_weight"] = 100.0
            st.rerun()
    with btn_cols[4]:
        if st.button("250 г", use_container_width=True, key="preset_250"):
            st.session_state["qd_preset_weight"] = 250.0
            st.rerun()
            
    # Settings expander for Electricity Tariff & Printer Power
    with st.expander("⚙️ Налаштування тарифу та потужності принтера"):
        cfg_col1, cfg_col2 = st.columns(2)
        with cfg_col1:
            power_kw = st.number_input(
                "Потужність принтера (кВт)",
                min_value=0.05,
                max_value=2.0,
                value=0.20,
                step=0.05,
                key="qd_power_kw",
                help="Середня потужність FDM 3D-принтера під час друку становить 150-250 Вт (0.2 кВт)",
            )
        with cfg_col2:
            tariff_uah = st.number_input(
                "Тариф на електроенергію (грн/кВт·год)",
                min_value=0.5,
                max_value=20.0,
                value=4.32,
                step=0.10,
                key="qd_tariff_uah",
                help="Актуальний базовий тариф на електроенергію в Україні: 4.32 грн за 1 кВт·год",
            )
            
    notes = st.text_input(
        "Примітки / налаштування (необов'язково)",
        placeholder="наприклад: сопло 0.4, висота шару 0.2, швидкість 120 мм/с, заповнення 20%",
        key="qd_notes",
    )
    
    # ── Formulas & Cost Calculations ──────────────────────────────────────────
    # 1. Plastic Cost: (Spool Price per 1 kg / 1000) * Model Weight
    plastic_cost = (price_per_kg / 1000.0) * model_weight_g
    
    # 2. Electricity Cost: Print Time (h) * Printer Power (kW) * Electricity Tariff (UAH/kWh)
    electricity_cost = print_time_hours * power_kw * tariff_uah
    
    # 3. Total Print Cost
    total_cost = plastic_cost + electricity_cost
    
    # Remaining weight
    remaining_weight_g = max(0.0, current_weight_g - model_weight_g)
    
    # Low stock alert check for remaining weight
    if remaining_weight_g < CRITICAL_STOCK_ALERT_G:
        rem_badge = f"<span style='color: #EF4444; font-weight: 700;'>🔴 {remaining_weight_g:.0f} г (&lt; {CRITICAL_STOCK_ALERT_G}г КРИТИЧНО)</span>"
    elif remaining_weight_g < LOW_STOCK_ALERT_G:
        rem_badge = f"<span style='color: #F59E0B; font-weight: 700;'>🟡 {remaining_weight_g:.0f} г (&lt; {LOW_STOCK_ALERT_G}г МАЛО)</span>"
    else:
        rem_badge = f"<span style='color: #10B981; font-weight: 700;'>🟢 {remaining_weight_g:.0f} г</span>"

    # ── Prominent Cost Breakdown Block ────────────────────────────────────────
    st.markdown(
        f"""
        <div style='background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
                    border: 2px solid #3B82F6; border-radius: 12px; padding: 18px 24px;
                    margin: 18px 0; box-shadow: 0 4px 14px rgba(0,0,0,0.25);'>
            <div style='font-size: 1.25rem; font-weight: 700; color: #60A5FA; margin-bottom: 12px; display: flex; align-items: center;'>
                📊 Деталізація собівартості друку
            </div>
            <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px;'>
                <div style='background: rgba(255,255,255,0.05); padding: 10px 14px; border-radius: 8px;'>
                    <div style='font-size: 0.85rem; color: #94A3B8;'>🧵 Собівартість пластику</div>
                    <div style='font-size: 1.4rem; font-weight: 700; color: #F8FAFC;'>{plastic_cost:.2f} ₴</div>
                    <div style='font-size: 0.78rem; color: #64748B;'>{model_weight_g:.1f} г × {price_per_g:.3f} ₴/г</div>
                </div>
                <div style='background: rgba(255,255,255,0.05); padding: 10px 14px; border-radius: 8px;'>
                    <div style='font-size: 0.85rem; color: #94A3B8;'>⚡ Витрати на електроенергію</div>
                    <div style='font-size: 1.4rem; font-weight: 700; color: #FBBF24;'>{electricity_cost:.2f} ₴</div>
                    <div style='font-size: 0.78rem; color: #64748B;'>{print_time_hours:.1f} год × {power_kw:.2f} кВт × {tariff_uah:.2f} ₴</div>
                </div>
                <div style='background: rgba(37, 99, 235, 0.2); border: 1px solid #3B82F6; padding: 10px 14px; border-radius: 8px;'>
                    <div style='font-size: 0.85rem; color: #93C5FD;'>💰 Загальна собівартість моделі</div>
                    <div style='font-size: 1.6rem; font-weight: 800; color: #38BDF8;'>{total_cost:.2f} ₴</div>
                    <div style='font-size: 0.78rem; color: #BAE6FD;'>пластик + електрика</div>
                </div>
                <div style='background: rgba(255,255,255,0.05); padding: 10px 14px; border-radius: 8px;'>
                    <div style='font-size: 0.85rem; color: #94A3B8;'>⚖️ Залишок на котушці</div>
                    <div style='font-size: 1.3rem; margin-top: 3px;'>{rem_badge}</div>
                    <div style='font-size: 0.78rem; color: #64748B;'>було {current_weight_g:.0f} г − {model_weight_g:.0f} г</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # ── Deduct Action Button ──────────────────────────────────────────────────
    btn_text = f"✂️ Списати {model_weight_g:.1f} г з котушки (Собівартість: {total_cost:.2f} ₴)"
    if st.button(btn_text, type="primary", use_container_width=True, key="btn_quick_deduct"):
        if not project_name.strip():
            st.error("Вкажіть назву деталі чи проєкту перед списанням.")
            return
        if model_weight_g <= 0:
            st.error("Вага деталі має бути більшою за 0 грамів.")
            return
            
        full_note = notes.strip()
        cost_breakdown_note = f"Пластик: {plastic_cost:.2f} ₴ ({model_weight_g:.1f}г), Ел-енергія: {electricity_cost:.2f} ₴ ({print_time_hours}год)"
        if full_note:
            final_notes = f"{full_note} | {cost_breakdown_note}"
        else:
            final_notes = cost_breakdown_note
            
        job = {
            "spool_id": spool_id,
            "project_name": project_name.strip(),
            "filament_used_g": float(model_weight_g),
            "cost_uah": round(total_cost, 2),
            "is_failed": 1 if is_failed else 0,
            "gcode_filename": None,
            "notes": final_notes,
        }
        queries.add_print_job(job)
        
        st.success(
            f"🎉 Успішно списано **{model_weight_g:.1f} г** з котушки #{spool_id}! "
            f"Собівартість: **{total_cost:.2f} ₴**. Залишок: **{remaining_weight_g:.0f} г**."
        )
        st.rerun()


def _render_gcode_import():
    """GCode / 3MF file import with drag-and-drop and print cost estimator."""
    st.subheader("📂 Автоматичний імпорт даних зі слайсера")
    st.caption("Завантажте файл .gcode, .3mf або .bgcode для миттєвого вилучення ваги та розрахунку:")
    
    uploaded = st.file_uploader(
        "Перетягніть файл GCode або 3MF сюди",
        type=["gcode", "3mf", "bgcode"],
        help="Підтримуються всі популярні слайсери: OrcaSlicer, PrusaSlicer, Cura, Bambu Studio",
    )
    
    if not uploaded:
        st.info("📎 Завантажте файл, створений вашим слайсером, щоб автоматично підставити вагу моделі.")
        return
    
    # Parse file
    file_bytes = uploaded.read()
    grams, slicer, error = parse_gcode_file(file_bytes, uploaded.name)
    
    if error:
        st.error(f"❌ {error}")
        return
    
    st.success(f"📂 Файл: **{uploaded.name}** | Слайсер: **{slicer}** | Знайдена вага: **{grams:.2f} г**")
    
    spools = queries.get_inventory(status_filter=["active", "sealed"])
    if not spools:
        st.warning("На складі немає котушок.")
        return
        
    spool_options = {
        f"{s['plastic_type']} — {s.get('color','')} ({s.get('brand','Котушка')}) | {s['current_weight_g']}г #{s['id']}": s
        for s in spools
    }
    
    selected_label = st.selectbox("Котушка для списання", options=list(spool_options.keys()), key="gcode_spool_sel")
    selected_spool = spool_options[selected_label]
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        project_name = st.text_input(
            "Назва деталі",
            value=uploaded.name.replace(".gcode", "").replace(".3mf", "").replace(".bgcode", ""),
            key="gcode_proj_name",
        )
        override_g = st.number_input(
            "Вага моделі (г)",
            min_value=0.1,
            value=float(grams),
            step=1.0,
            key="gcode_grams",
        )
    with col_g2:
        print_time_hours = st.number_input(
            "Час друку (годин)",
            min_value=0.0,
            value=2.0,
            step=0.5,
            key="gcode_hours",
        )
        is_failed = st.checkbox("❌ Невдалий друк (брак)", key="gcode_failed")
        
    init_g = max(float(selected_spool.get("initial_weight_g") or 1000.0), 1.0)
    price_val = float(selected_spool.get("purchase_price") or 0.0)
    price_per_kg = (price_val / init_g) * 1000.0
    
    plastic_cost = (price_per_kg / 1000.0) * override_g
    electricity_cost = print_time_hours * 0.20 * 4.32
    total_cost = plastic_cost + electricity_cost
    
    st.info(
        f"💰 **Собівартість друку: {total_cost:.2f} ₴** "
        f"(Пластик: {plastic_cost:.2f} ₴ + Електроенергія: {electricity_cost:.2f} ₴)"
    )
    
    if st.button("✅ Підтвердити списання з файлу", type="primary", use_container_width=True, key="btn_gcode_submit"):
        job = {
            "spool_id": selected_spool["id"],
            "project_name": project_name.strip() or uploaded.name,
            "filament_used_g": float(override_g),
            "cost_uah": round(total_cost, 2),
            "is_failed": 1 if is_failed else 0,
            "gcode_filename": uploaded.name,
            "notes": f"Імпорт {slicer}; Пластик: {plastic_cost:.2f}₴, Електрика: {electricity_cost:.2f}₴",
        }
        queries.add_print_job(job)
        st.success(f"✅ Списано {override_g:.1f} г | Собівартість: {total_cost:.2f} ₴")
        st.rerun()


def _render_journal():
    """Render print history journal with visual indicators."""
    st.subheader("📋 Журнал виконаних робіт та списань")
    
    jobs = queries.get_print_jobs(limit=100)
    
    if not jobs:
        st.info("Журнал друку наразі порожній. Спишіть першу деталь на вкладці «✂️ Швидке списання».")
        return
        
    total_g = sum(j["filament_used_g"] for j in jobs)
    total_cost = sum(j.get("cost_uah") or 0.0 for j in jobs)
    failed = [j for j in jobs if j.get("is_failed")]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всього друків", len(jobs))
    col2.metric("Витрачено пластику", f"{total_g:.0f} г ({total_g/1000:.2f} кг)")
    col3.metric("Загальна собівартість", f"{total_cost:.0f} ₴")
    col4.metric("❌ Бракованих робіт", len(failed))
    
    show_failed_only = st.checkbox("Показати тільки браковані друки", value=False)
    if show_failed_only:
        jobs = failed
        
    st.divider()
    
    for job in jobs:
        failed_icon = "❌" if job.get("is_failed") else "✅"
        ptype = job.get("plastic_type", "?")
        hardness = f" {job['hardness']}" if job.get("hardness") and job["hardness"] not in ("Невідомо", "—") else ""
        color = job.get("color", "")
        brand = job.get("brand", "")
        
        dot = render_color_badge(color, size=18)
        mat_str = f"{dot} <b>{ptype}{hardness}</b>"
        if color:
            mat_str += f" {color}"
        if brand:
            mat_str += f" <span style='opacity: 0.7;'>({brand})</span>"
            
        printed_at = str(job.get("printed_at") or "")[:16].replace("T", " ")
        used_g = job.get("filament_used_g", 0.0)
        cost = job.get("cost_uah") or 0.0
        gcode = job.get("gcode_filename") or ""
        gcode_str = f" | 📂 {gcode}" if gcode else ""
        
        col_info, col_del = st.columns([8.5, 1.5])
        with col_info:
            st.markdown(
                f"{failed_icon} <b>{job['project_name']}</b> &nbsp;|&nbsp; {mat_str} &nbsp;|&nbsp; "
                f"<b>{used_g:.1f} г</b> &nbsp;|&nbsp; <b>{cost:.2f} ₴</b> &nbsp;|&nbsp; 🕒 {printed_at}{gcode_str}",
                unsafe_allow_html=True,
            )
            if job.get("notes"):
                st.caption(f"📝 {job['notes']}")
        with col_del:
            if st.button("🗑️", key=f"del_job_{job['id']}", help="Видалити запис і повернути витрачені грами на котушку"):
                queries.delete_print_job(
                    job_id=job["id"],
                    spool_id=job["spool_id"],
                    filament_used_g=job["filament_used_g"],
                )
                st.success("Запис видалено, вагу відновлено на котушці.")
                st.rerun()
