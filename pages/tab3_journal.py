"""Tab 3: Print journal and filament deduction log."""
import io
from datetime import datetime

import pandas as pd
import streamlit as st

from db import queries
from gcode_parser.parser import parse_gcode_file


def render():
    """Render the print journal tab."""
    st.header("🖨️ Журнал друку та списання пластику")
    
    jt1, jt2, jt3 = st.tabs(["✂️ Швидке списання", "📂 Імпорт GCode/.3mf", "📋 Журнал"])
    
    with jt1:
        _render_quick_deduct()
    
    with jt2:
        _render_gcode_import()
    
    with jt3:
        _render_journal()


def _render_quick_deduct():
    """Quick filament deduction form."""
    st.subheader("Списати філамент")
    
    # Get active spools
    spools = queries.get_inventory(status_filter=["active", "sealed"])
    if not spools:
        st.warning("На складі немає котушок. Спочатку додайте котушку у вкладці «Мій склад».")
        return
    
    spool_options = {
        f"{s['plastic_type']}{' ' + s['hardness'] if s.get('hardness') else ''}"
        f"{' — ' + s['color'] if s.get('color') else ''}"
        f" ({s['current_weight_g']} г залишок)"
        f" [{s.get('brand') or s.get('store_name') or '?'}]"
        f" #{s['id']}": s
        for s in spools
    }
    
    with st.form("quick_deduct_form", clear_on_submit=True):
        selected_label = st.selectbox("Котушка *", options=list(spool_options.keys()))
        selected_spool = spool_options[selected_label]
        
        col1, col2 = st.columns(2)
        with col1:
            project_name = st.text_input("Назва деталі / проєкту *", placeholder="Кронштейн, Вазочка...")
            filament_g = st.number_input(
                "Витрачено пластику (г) *",
                min_value=0.1,
                max_value=float(selected_spool["current_weight_g"] + 50),
                value=10.0,
                step=0.5,
            )
        with col2:
            is_failed = st.checkbox("❌ Невдалий друк (брак)")
            notes = st.text_area("Примітки", height=80)
        
        # Cost preview
        cost_per_g = selected_spool["purchase_price"] / max(selected_spool["initial_weight_g"], 1)
        cost_preview = cost_per_g * filament_g
        st.info(f"💰 Орієнтовна собівартість: **{cost_preview:.2f} ₴** ({cost_per_g:.4f} ₴/г)")
        
        submitted = st.form_submit_button("✂️ Списати", type="primary", use_container_width=True)
        if submitted:
            if not project_name.strip():
                st.error("Вкажіть назву деталі/проєкту")
            elif filament_g <= 0:
                st.error("Вкажіть кількість грамів більше 0")
            else:
                job = {
                    "spool_id": selected_spool["id"],
                    "project_name": project_name.strip(),
                    "filament_used_g": filament_g,
                    "cost_uah": round(cost_preview, 2),
                    "is_failed": 1 if is_failed else 0,
                    "gcode_filename": None,
                    "notes": notes.strip() or None,
                }
                job_id = queries.add_print_job(job)
                remaining = max(0, selected_spool["current_weight_g"] - filament_g)
                st.success(
                    f"✅ Списано {filament_g} г | Собівартість: {cost_preview:.2f} ₴ | "
                    f"Залишок на котушці: {remaining:.0f} г"
                )
                st.rerun()


def _render_gcode_import():
    """GCode / 3MF file import with drag-and-drop."""
    st.subheader("Імпорт даних зі слайсера")
    
    uploaded = st.file_uploader(
        "Перетягніть файл .gcode або .3mf сюди",
        type=["gcode", "3mf", "bgcode"],
        help="Підтримуються: OrcaSlicer, PrusaSlicer, Cura, Bambu Studio",
    )
    
    if not uploaded:
        st.info(
            "📎 Завантажте файл .gcode або .3mf зі слайсера, щоб автоматично "
            "визначити кількість потрібного філаменту та розрахувати собівартість."
        )
        return
    
    # Parse the file
    file_bytes = uploaded.read()
    grams, slicer, error = parse_gcode_file(file_bytes, uploaded.name)
    
    if error:
        st.error(f"❌ {error}")
        return
    
    st.success(f"📂 Файл: **{uploaded.name}** | Слайсер: **{slicer}** | Знайдено: **{grams:.2f} г**")
    
    # Select spool and calculate cost
    spools = queries.get_inventory(status_filter=["active", "sealed"])
    if not spools:
        st.warning("На складі немає котушок.")
        return
    
    spool_options = {
        f"{s['plastic_type']}{' ' + s['hardness'] if s.get('hardness') else ''}"
        f"{' — ' + s['color'] if s.get('color') else ''}"
        f" ({s['current_weight_g']} г) #{s['id']}": s
        for s in spools
    }
    
    with st.form("gcode_deduct_form"):
        selected_label = st.selectbox("Котушка для списання", options=list(spool_options.keys()))
        selected_spool = spool_options[selected_label]
        
        project_name = st.text_input(
            "Назва деталі",
            value=uploaded.name.replace(".gcode", "").replace(".3mf", "").replace(".bgcode", ""),
        )
        
        override_g = st.number_input(
            "Кількість грамів (можна відредагувати)",
            min_value=0.1,
            value=float(grams),
            step=0.5,
        )
        
        cost_per_g = selected_spool["purchase_price"] / max(selected_spool["initial_weight_g"], 1)
        cost = cost_per_g * override_g
        st.info(f"💰 Собівартість: **{cost:.2f} ₴** ({override_g:.2f} г × {cost_per_g:.4f} ₴/г)")
        
        is_failed = st.checkbox("❌ Невдалий друк (брак)")
        notes = st.text_area("Примітки")
        
        submitted = st.form_submit_button("✅ Підтвердити списання", type="primary", use_container_width=True)
        if submitted:
            job = {
                "spool_id": selected_spool["id"],
                "project_name": project_name.strip() or uploaded.name,
                "filament_used_g": override_g,
                "cost_uah": round(cost, 2),
                "is_failed": 1 if is_failed else 0,
                "gcode_filename": uploaded.name,
                "notes": notes.strip() or None,
            }
            job_id = queries.add_print_job(job)
            st.success(
                f"✅ Списано {override_g:.2f} г | {cost:.2f} ₴ | "
                f"Файл: {uploaded.name}"
            )
            st.rerun()


def _render_journal():
    """Render print history journal."""
    st.subheader("Журнал друку")
    
    jobs = queries.get_print_jobs(limit=100)
    
    if not jobs:
        st.info("Журнал порожній. Спишіть перший друк у вкладці «Швидке списання».")
        return
    
    # Summary
    total_g = sum(j["filament_used_g"] for j in jobs)
    total_cost = sum(j.get("cost_uah") or 0 for j in jobs)
    failed = [j for j in jobs if j.get("is_failed")]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всього записів", len(jobs))
    col2.metric("Пластику всього", f"{total_g:.0f} г")
    col3.metric("Витрат всього", f"{total_cost:.0f} ₴")
    col4.metric("❌ Бракованих", len(failed))
    
    # Filter
    show_failed = st.checkbox("Показати тільки брак", value=False)
    if show_failed:
        jobs = failed
    
    st.divider()
    
    # Render jobs table
    for job in jobs:
        failed_icon = "❌" if job.get("is_failed") else "✅"
        ptype = job.get("plastic_type", "?")
        hardness = job.get("hardness")
        color = job.get("color", "")
        brand = job.get("brand", "")
        
        mat_str = ptype
        if hardness:
            mat_str += f" {hardness}"
        if color:
            mat_str += f" {color}"
        if brand:
            mat_str += f" ({brand})"
        
        printed_at = job.get("printed_at", "")[:10] if job.get("printed_at") else "—"
        used_g = job.get("filament_used_g", 0)
        cost = job.get("cost_uah") or 0
        gcode = job.get("gcode_filename") or ""
        gcode_str = f" | 📂 {gcode}" if gcode else ""
        
        col_info, col_del = st.columns([8, 1])
        with col_info:
            st.markdown(
                f"{failed_icon} **{job['project_name']}** | {mat_str} | "
                f"{used_g:.1f} г | {cost:.2f} ₴ | {printed_at}{gcode_str}"
            )
            if job.get("notes"):
                st.caption(f"📝 {job['notes']}")
        
        with col_del:
            if st.button("🗑️", key=f"del_job_{job['id']}", help="Видалити запис і відновити вагу"):
                queries.delete_print_job(
                    job_id=job["id"],
                    spool_id=job["spool_id"],
                    filament_used_g=job["filament_used_g"],
                )
                st.rerun()
