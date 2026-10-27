"""Tab 4: Analytics and cost statistics."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db import queries


def render():
    """Render the analytics tab."""
    st.header("📊 Аналітика та витрати")
    
    data = queries.get_analytics_summary()
    
    # ── Top metrics ────────────────────────────────────────────────────
    st.subheader("📦 Склад зараз")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Пластику вдома", f"{data['total_g'] / 1000:.2f} кг")
    m2.metric("Вартість запасів", f"{data['total_value']:.0f} ₴")
    m3.metric("За цей місяць", f"{data['month_used_g']:.0f} г")
    m4.metric("Витрачено місяць", f"{data['month_used_uah']:.0f} ₴")
    
    st.divider()
    
    # ── All-time stats ─────────────────────────────────────────────────
    st.subheader("📈 За весь час")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Всього надруковано", f"{data['all_used_g'] / 1000:.2f} кг")
    a2.metric("Всього витрачено", f"{data['all_used_uah']:.0f} ₴")
    a3.metric("Друків всього", data["total_jobs"])
    
    fail_pct = 0
    if data["total_jobs"] > 0:
        fail_pct = data["failed_jobs"] / data["total_jobs"] * 100
    a4.metric("Бракованих", f"{data['failed_jobs']} ({fail_pct:.1f}%)")
    
    st.divider()
    
    # ── Avg price by type (purchased) ─────────────────────────────────
    if data["avg_by_type"]:
        st.subheader("💰 Середня ціна за типом (мої покупки)")
        avg_df = pd.DataFrame(data["avg_by_type"])
        avg_df = avg_df.rename(columns={
            "plastic_type": "Тип",
            "avg_price_per_kg": "Ціна/кг (₴)",
            "spool_count": "Котушок",
        })
        avg_df["Ціна/кг (₴)"] = avg_df["Ціна/кг (₴)"].round(0)
        
        fig_avg = px.bar(
            avg_df,
            x="Тип",
            y="Ціна/кг (₴)",
            text="Ціна/кг (₴)",
            color="Тип",
            title="Середня ціна моїх покупок за типом пластику (₴/кг)",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_avg.update_traces(texttemplate="%{text:.0f} ₴", textposition="outside")
        fig_avg.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig_avg, use_container_width=True)
    
    # ── Charts row ─────────────────────────────────────────────────────
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        # Monthly filament usage
        if data["monthly"]:
            monthly_df = pd.DataFrame(data["monthly"])
            monthly_df = monthly_df.rename(columns={
                "month": "Місяць",
                "used_g": "Пластику (г)",
                "cost_uah": "Витрат (₴)",
            })
            fig_monthly = px.bar(
                monthly_df,
                x="Місяць",
                y="Пластику (г)",
                title="Витрата пластику по місяцях",
                color_discrete_sequence=["#4CAF50"],
            )
            fig_monthly.update_layout(height=350)
            st.plotly_chart(fig_monthly, use_container_width=True)
        else:
            st.info("Немає даних про друки для графіка витрат.")
    
    with chart_col2:
        # Type distribution pie
        if data["type_dist"]:
            type_df = pd.DataFrame(data["type_dist"])
            type_df = type_df.rename(columns={
                "plastic_type": "Тип",
                "total_g": "Всього (г)",
            })
            fig_pie = px.pie(
                type_df,
                values="Всього (г)",
                names="Тип",
                title="Розподіл пластику на складі за типом",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_pie.update_layout(height=350)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Немає даних складу для графіка розподілу.")
    
    # ── Store price comparison ─────────────────────────────────────────
    if data["store_prices"]:
        st.subheader("🛒 Порівняння цін по магазинах")
        
        sp_df = pd.DataFrame(data["store_prices"])
        sp_df = sp_df.rename(columns={
            "store_name": "Магазин",
            "plastic_type": "Тип",
            "avg_price_per_kg": "Ціна/кг (₴)",
        })
        sp_df["Ціна/кг (₴)"] = sp_df["Ціна/кг (₴)"].round(0)
        
        plastic_filter = st.multiselect(
            "Тип пластику для порівняння",
            options=sp_df["Тип"].unique().tolist(),
            default=sp_df["Тип"].unique().tolist()[:3] if len(sp_df) > 3 else sp_df["Тип"].unique().tolist(),
        )
        if plastic_filter:
            sp_df = sp_df[sp_df["Тип"].isin(plastic_filter)]
        
        fig_stores = px.bar(
            sp_df,
            x="Магазин",
            y="Ціна/кг (₴)",
            color="Тип",
            barmode="group",
            title="Середня ціна пластику по магазинах (₴/кг)",
            text="Ціна/кг (₴)",
            color_discrete_sequence=px.colors.qualitative.Set1,
        )
        fig_stores.update_traces(texttemplate="%{text:.0f}", textposition="outside")
        fig_stores.update_layout(height=450, xaxis_tickangle=-35)
        st.plotly_chart(fig_stores, use_container_width=True)
    
    # ── Failed vs successful ───────────────────────────────────────────
    if data["total_jobs"] > 0:
        st.subheader("✅ Успішні vs ❌ Бракований друк")
        fail_df = pd.DataFrame([
            {"Результат": "✅ Успішний", "Кількість": data["total_jobs"] - data["failed_jobs"]},
            {"Результат": "❌ Брак", "Кількість": data["failed_jobs"]},
        ])
        fig_fail = px.pie(
            fail_df,
            values="Кількість",
            names="Результат",
            color="Результат",
            color_discrete_map={"✅ Успішний": "#44bb44", "❌ Брак": "#bb4444"},
            title="Співвідношення успішних та бракованих друків",
        )
        fig_fail.update_layout(height=300)
        st.plotly_chart(fig_fail, use_container_width=True)
