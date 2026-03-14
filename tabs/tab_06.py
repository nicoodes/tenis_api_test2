import pandas as pd
import streamlit as st

from src.tenis_api import run_swl_query

ANALYSIS_QUERY = "SELECT * FROM tenis_api.hist_full_analysis_metrics"
SESSION_KEY = "tab06_df"

GROUP_LABELS = {
    "event_date": "Date",
    "event_gender": "Gender",
    "event_type": "Event Type",
    "event_type_3": "Event Type (detailed)",
    "jugador_a_apostar": "Player",
    "tournament_name": "Tournament",
    "tournament_sourface": "Surface",
}

# Groups that get horizontal bars limited to top 10 by count
HORIZONTAL_TOP10_GROUPS = {"jugador_a_apostar", "tournament_name"}
# Group where we cap to last 10 dates
DATE_GROUP = "event_date"

GROUP_ORDER = [
    "event_date",
    "event_gender",
    "event_type",
    "event_type_3",
    "tournament_name",
    "tournament_sourface",
    "jugador_a_apostar",
]


def _load_data() -> pd.DataFrame | None:
    res = run_swl_query(ANALYSIS_QUERY)
    if not res.get("success"):
        st.error(f"Query failed: {res.get('message', 'Unknown error')}")
        return None
    rows = res.get("result") or []
    cols = res.get("columns") or []
    df = pd.DataFrame(rows, columns=cols)
    # normalise: the group-value column might be named 'event_date' from older views
    if "event_date" in df.columns and "group_value" not in df.columns:
        df = df.rename(columns={"event_date": "group_value"})
    elif "group_value" not in df.columns:
        # second column is the group value regardless of its name
        second_col = df.columns[1]
        df = df.rename(columns={second_col: "group_value"})
    return df


def _prepare_group(group_df: pd.DataFrame, group: str) -> pd.DataFrame:
    """Apply any group-specific filtering / sorting."""
    gdf = group_df.copy()
    gdf["_total_count"] = (
        pd.to_numeric(gdf.get("total_won", 0), errors="coerce").fillna(0)
        + pd.to_numeric(gdf.get("total_lost", 0), errors="coerce").fillna(0)
        + pd.to_numeric(gdf.get("total_unkn", 0), errors="coerce").fillna(0)
    )

    if group == DATE_GROUP:
        gdf["_date_parsed"] = pd.to_datetime(gdf["group_value"], errors="coerce")
        gdf = gdf.sort_values("_date_parsed")
        gdf = gdf.tail(10)
        gdf = gdf.drop(columns=["_date_parsed"])

    if group in HORIZONTAL_TOP10_GROUPS:
        gdf = gdf.sort_values("_total_count", ascending=False).head(10)

    return gdf


def _plot_count(px, go, group_df: pd.DataFrame, group: str, x_label: str) -> None:
    gdf = group_df.copy()
    melted = gdf.melt(
        id_vars="group_value",
        value_vars=["total_won", "total_lost", "total_unkn"],
        var_name="result",
        value_name="count",
    )
    melted["result"] = melted["result"].map(
        {"total_won": "Won", "total_lost": "Lost", "total_unkn": "Unknown"}
    )
    color_map = {"Won": "#2ECC71", "Lost": "#E74C3C", "Unknown": "#BDC3C7"}

    if group in HORIZONTAL_TOP10_GROUPS:
        # Order bars by total count descending
        order = (
            gdf.sort_values("_total_count", ascending=True)["group_value"].tolist()
        )
        fig = px.bar(
            melted,
            y="group_value",
            x="count",
            color="result",
            barmode="stack",
            orientation="h",
            title="Count (top 10)",
            color_discrete_map=color_map,
            labels={"group_value": x_label, "count": "Games"},
            category_orders={"group_value": order},
        )
        fig.update_layout(legend_title_text="", margin={"t": 40})
    else:
        fig = px.bar(
            melted,
            x="group_value",
            y="count",
            color="result",
            barmode="stack",
            title="Count",
            color_discrete_map=color_map,
            labels={"group_value": x_label, "count": "Games"},
        )
        fig.update_layout(legend_title_text="", margin={"t": 40})

    st.plotly_chart(fig, use_container_width=True)


def _plot_winrate(px, group_df: pd.DataFrame, group: str, x_label: str) -> None:
    melted = group_df.melt(
        id_vars="group_value",
        value_vars=["perc_won", "perc_lost", "perc_unkn"],
        var_name="result",
        value_name="percentage",
    )
    melted["result"] = melted["result"].map(
        {"perc_won": "Won", "perc_lost": "Lost", "perc_unkn": "Unknown"}
    )
    color_map = {"Won": "#2ECC71", "Lost": "#E74C3C", "Unknown": "#BDC3C7"}

    if group in HORIZONTAL_TOP10_GROUPS:
        order = (
            group_df.sort_values("_total_count", ascending=True)["group_value"].tolist()
        )
        fig = px.bar(
            melted,
            y="group_value",
            x="percentage",
            color="result",
            barmode="stack",
            orientation="h",
            title="Win / Loss / Unknown rate",
            color_discrete_map=color_map,
            labels={"group_value": x_label, "percentage": "Rate"},
            category_orders={"group_value": order},
        )
        fig.update_layout(xaxis_tickformat=".0%", legend_title_text="", margin={"t": 40})
    else:
        fig = px.bar(
            melted,
            x="group_value",
            y="percentage",
            color="result",
            barmode="stack",
            title="Win / Loss / Unknown rate",
            color_discrete_map=color_map,
            labels={"group_value": x_label, "percentage": "Rate"},
        )
        fig.update_layout(yaxis_tickformat=".0%", legend_title_text="", margin={"t": 40})

    st.plotly_chart(fig, use_container_width=True)


def _plot_profitloss(go, group_df: pd.DataFrame, group: str, x_label: str) -> None:
    pl_values = pd.to_numeric(group_df["total_profit_loss"], errors="coerce").tolist()
    labels = group_df["group_value"].astype(str).tolist()
    bar_colors = ["#2ECC71" if (v or 0) >= 0 else "#E74C3C" for v in pl_values]

    if group in HORIZONTAL_TOP10_GROUPS:
        fig = go.Figure(
            go.Bar(
                y=labels,
                x=pl_values,
                orientation="h",
                marker_color=bar_colors,
            )
        )
        fig.update_layout(
            title="Total Profit / Loss",
            yaxis_title=x_label,
            xaxis_title="Profit / Loss",
            margin={"t": 40},
        )
    else:
        fig = go.Figure(
            go.Bar(
                x=labels,
                y=pl_values,
                marker_color=bar_colors,
            )
        )
        fig.update_layout(
            title="Total Profit / Loss",
            xaxis_title=x_label,
            yaxis_title="Profit / Loss",
            margin={"t": 40},
        )

    st.plotly_chart(fig, use_container_width=True)


def render_tab_06() -> None:
    st.subheader("Results Analysis")

    col_btn, _ = st.columns([1, 5])
    if col_btn.button("Load analysis data", type="primary"):
        with st.spinner("Querying database..."):
            df = _load_data()
        if df is not None:
            st.session_state[SESSION_KEY] = df
            st.rerun()

    df = st.session_state.get(SESSION_KEY)
    if df is None or df.empty:
        st.info("Press **Load analysis data** to fetch results from the database.")
        return

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
        raw_group_df = df[df["view_group"] == group].copy()
        group_df = _prepare_group(raw_group_df, group)
        x_label = GROUP_LABELS.get(group, group)

        st.markdown(f"### By {x_label}")

        if px is not None and go is not None:
            col1, col2, col3 = st.columns(3)
            with col1:
                _plot_count(px, go, group_df, group, x_label)
            with col2:
                _plot_winrate(px, group_df, group, x_label)
            with col3:
                _plot_profitloss(go, group_df, group, x_label)

        with st.expander("View data table", expanded=False):
            display_df = (
                group_df
                .drop(columns=["view_group", "_total_count"], errors="ignore")
                .rename(columns={"group_value": x_label})
            )
            st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.markdown("---")
