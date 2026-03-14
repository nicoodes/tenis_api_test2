import os

import pandas as pd
import streamlit as st

RESULTS_CSV_PATH = os.path.join("src", "results_analysis.csv")

GROUP_LABELS = {
    "event_date": "Date",
    "event_gender": "Gender",
    "event_type": "Event Type",
    "jugador_a_apostar": "Player",
    "tournament_name": "Tournament",
    "tournament_sourface": "Surface",
}

GROUP_ORDER = [
    "event_date",
    "event_gender",
    "event_type",
    "tournament_name",
    "tournament_sourface",
    "jugador_a_apostar",
]


def render_tab_06() -> None:
    st.subheader("Results Analysis")

    try:
        df = pd.read_csv(RESULTS_CSV_PATH)
    except FileNotFoundError:
        st.error(f"Could not find results_analysis.csv at '{RESULTS_CSV_PATH}'.")
        return
    except Exception as e:
        st.error(f"Could not load results_analysis.csv: {e}")
        return

    if df.empty:
        st.info("No data available.")
        return

    # The CSV's second column is named 'event_date' but carries the per-group label value
    df = df.rename(columns={"event_date": "group_value"})

    px = None
    go = None
    try:
        import plotly.express as _px
        import plotly.graph_objects as _go

        px = _px
        go = _go
    except ImportError:
        st.warning("Plotly is not installed. Charts will not be displayed.")

    all_groups = df["view_group"].unique().tolist()
    ordered_groups = [g for g in GROUP_ORDER if g in all_groups] + [
        g for g in all_groups if g not in GROUP_ORDER
    ]

    for group in ordered_groups:
        group_df = df[df["view_group"] == group].copy()
        x_label = GROUP_LABELS.get(group, group)

        st.markdown(f"### By {x_label}")

        if px is not None and go is not None:
            col_left, col_right = st.columns(2)

            with col_left:
                melted = group_df.melt(
                    id_vars="group_value",
                    value_vars=["perc_won", "perc_lost", "perc_unkn"],
                    var_name="result",
                    value_name="percentage",
                )
                melted["result"] = melted["result"].map(
                    {"perc_won": "Won", "perc_lost": "Lost", "perc_unkn": "Unknown"}
                )
                fig_win = px.bar(
                    melted,
                    x="group_value",
                    y="percentage",
                    color="result",
                    barmode="stack",
                    title="Win / Loss / Unknown rate",
                    color_discrete_map={
                        "Won": "#2ECC71",
                        "Lost": "#E74C3C",
                        "Unknown": "#BDC3C7",
                    },
                    labels={"group_value": x_label, "percentage": "Rate"},
                )
                fig_win.update_layout(
                    yaxis_tickformat=".0%",
                    legend_title_text="",
                    margin={"t": 40},
                )
                st.plotly_chart(fig_win, use_container_width=True)

            with col_right:
                pl_values = group_df["total_profit_loss"].tolist()
                bar_colors = ["#2ECC71" if v >= 0 else "#E74C3C" for v in pl_values]
                fig_pl = go.Figure(
                    go.Bar(
                        x=group_df["group_value"].tolist(),
                        y=pl_values,
                        marker_color=bar_colors,
                    )
                )
                fig_pl.update_layout(
                    title="Total Profit / Loss",
                    xaxis_title=x_label,
                    yaxis_title="Profit / Loss",
                    margin={"t": 40},
                )
                st.plotly_chart(fig_pl, use_container_width=True)

        with st.expander("View data table", expanded=False):
            display_df = (
                group_df
                .drop(columns=["view_group"])
                .rename(columns={"group_value": x_label})
            )
            st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.markdown("---")
