import pandas as pd
import streamlit as st

FULL_ANALYSIS_SQL = "refresh_and_get_full_analysis.sql"
FULL_ANALYSIS_SESSION_KEY = "tab5_full_analysis_df"
FULL_ANALYSIS_ERROR_KEY = "tab5_full_analysis_error"

EVENT_STATUS_COLORS = {
  "Not yet started": "#3B76BA",
  "In progress": "#E1E346",
  "Finished": "#903304",
  "Interrupted": "#8D3399",
  "Cancelled": "#cc0058",
}

SUMMARY_COLUMNS = [
  "tournament_name",
  "event_date",
  "event_time",
  "event_first_player",
  "event_second_player",
  "event_winner",
  "tournament_sourface",
  "jugador_a_apostar_vb",
  "jugador_a_apostar_cons",
  "monto_apuesta_vb",
  "monto_apuesta_cons",
]


def _sorted_unique_values(series: pd.Series):
  return sorted(series.dropna().unique().tolist())


def _filter_equals(df: pd.DataFrame, column_name: str, selected_value: str):
  if column_name not in df.columns or selected_value == "All":
    return df
  return df[df[column_name] == selected_value]


def _build_filters(df: pd.DataFrame) -> pd.DataFrame:
  st.markdown("#### Filters")

  working_df = df.copy()
  if "event_date" in working_df.columns:
    working_df["event_date_only"] = pd.to_datetime(
      working_df["event_date"], errors="coerce"
    ).dt.date

  row_1_col_1, row_1_col_2 = st.columns(2)

  selected_event_date_label = "All"
  if "event_date_only" in working_df.columns:
    event_dates = [d for d in sorted(working_df["event_date_only"].dropna().unique())]
    event_date_options = ["All"] + [d.isoformat() for d in event_dates]
    selected_event_date_label = row_1_col_1.pills(
      "event_date",
      options=event_date_options,
      default="All",
      selection_mode="single",
      key="tab5_filter_event_date",
    )

  date_filtered_df = working_df
  if selected_event_date_label != "All":
    selected_event_date = pd.to_datetime(selected_event_date_label, errors="coerce").date()
    date_filtered_df = working_df[working_df["event_date_only"] == selected_event_date]

  event_type_options = ["All"]
  if "event_type" in date_filtered_df.columns:
    event_type_options += _sorted_unique_values(date_filtered_df["event_type"])
  selected_event_type = row_1_col_2.pills(
    "event_type",
    options=event_type_options,
    default="All",
    selection_mode="single",
    key="tab5_filter_event_type",
  )

  type_filtered_df = _filter_equals(date_filtered_df, "event_type", selected_event_type)

  row_2_col_1, row_2_col_2 = st.columns(2)

  event_status_options = ["All"]
  if "event_status" in type_filtered_df.columns:
    event_status_options += _sorted_unique_values(type_filtered_df["event_status"])
  selected_event_status = row_2_col_1.pills(
    "event_status",
    options=event_status_options,
    default="All",
    selection_mode="single",
    key="tab5_filter_event_status",
  )

  status_filtered_df = _filter_equals(type_filtered_df, "event_status", selected_event_status)

  tournament_options = []
  if "tournament_name" in status_filtered_df.columns:
    tournament_options = _sorted_unique_values(status_filtered_df["tournament_name"])
  selected_tournaments = row_2_col_2.multiselect(
    "tournament_name",
    options=tournament_options,
    default=[],
    key="tab5_filter_tournament_name",
  )

  out = status_filtered_df
  if selected_tournaments and "tournament_name" in out.columns:
    out = out[out["tournament_name"].isin(selected_tournaments)]

  return out


def render_tab_05(run_sql_file_fn) -> None:
  st.subheader("Full analysis")

  if FULL_ANALYSIS_SESSION_KEY not in st.session_state:
    st.session_state[FULL_ANALYSIS_SESSION_KEY] = None
  if FULL_ANALYSIS_ERROR_KEY not in st.session_state:
    st.session_state[FULL_ANALYSIS_ERROR_KEY] = ""

  if st.button("Run full analysis", type="primary", key="tab5_run_full_analysis"):
    with st.spinner("Running full analysis query..."):
      response = run_sql_file_fn(FULL_ANALYSIS_SQL)
      if response.get("success"):
        analysis_df = pd.DataFrame(
          response.get("result") or [], columns=response.get("columns") or []
        )
        st.session_state[FULL_ANALYSIS_SESSION_KEY] = analysis_df
        st.session_state[FULL_ANALYSIS_ERROR_KEY] = ""
        st.success(f"Full analysis completed. Rows: {len(analysis_df)}")
      else:
        st.session_state[FULL_ANALYSIS_SESSION_KEY] = None
        st.session_state[FULL_ANALYSIS_ERROR_KEY] = response.get(
          "message", "Error running full analysis query"
        )

  error_message = st.session_state.get(FULL_ANALYSIS_ERROR_KEY, "")
  if error_message:
    st.error(error_message)

  source_df = st.session_state.get(FULL_ANALYSIS_SESSION_KEY)
  if source_df is None:
    st.info("Press 'Run full analysis' to refresh and load data.")
    return

  filtered_df = _build_filters(source_df)

  st.caption(f"Rows after filters: {len(filtered_df)}")

  summary_columns = [col for col in SUMMARY_COLUMNS if col in filtered_df.columns]
  missing_summary_columns = [col for col in SUMMARY_COLUMNS if col not in filtered_df.columns]

  st.markdown("#### Summary table")
  if missing_summary_columns:
    st.warning("Missing columns in summary table: " + ", ".join(missing_summary_columns))

  if summary_columns:
    st.dataframe(
      filtered_df[summary_columns],
      use_container_width=True,
      hide_index=True,
      height=460,
      column_config={
        "tournament_name": st.column_config.Column(
          "Tournament",
          help="Name of the tournament",
          required=True,
        ),
        "event_date": st.column_config.Column(
          "Date",
          help="Event date",
          required=True,
        ),
        "event_time": st.column_config.Column(
          "Time",
          help="Event time",
          required=True,
        ),
        "event_first_player": st.column_config.Column(
          "Player 1",
          help="First player",
          required=True,
        ),
        "event_second_player": st.column_config.Column(
          "Player 2",
          help="Second player",
          required=True,
        ),
        "event_winner": st.column_config.MultiselectColumn(
          "Winner",
          help="Event winner",
          options=["P1", "P2"],
          color=["#E37636", "#9F3FE9"],
        ),
        "tournament_sourface": st.column_config.MultiselectColumn(
          "Sourface",
          help="Tournament sourface",
          options=["Hard", "Clay", "Grass"],
          color=["#336699", "#993300", "#339966"],
        ),
        "jugador_a_apostar_vb": st.column_config.Column(
          "Jugador VB",
          help="Suggested player (VB model)",
          required=True,
        ),
        "jugador_a_apostar_cons": st.column_config.Column(
          "Jugador Cons",
          help="Suggested player (Conservative model)",
          required=True,
        ),
        "monto_apuesta_vb": st.column_config.NumberColumn(
          "Monto VB",
          help="Stake amount for VB model",
          format="%.2f",
          required=True,
        ),
        "monto_apuesta_cons": st.column_config.NumberColumn(
          "Monto Cons",
          help="Stake amount for conservative model",
          format="%.2f",
          required=True,
        ),
        "event_status": st.column_config.MultiselectColumn(
          "Event Status",
          help="Event status",
          options=list(EVENT_STATUS_COLORS.keys()),
          color=list(EVENT_STATUS_COLORS.values()),
        ),
      },
    )
  else:
    st.info("No columns available for the summary table.")

  with st.expander("Show full analysis data"):
    st.dataframe(filtered_df, use_container_width=True, hide_index=True, height=560)
