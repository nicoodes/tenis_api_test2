# Streamlit sample app for tennis fixtures
import datetime
import importlib
import os
import csv
from datetime import timedelta
import logging
import pandas as pd
import streamlit as st

from src.tenis_api import get_fixtures_history, get_fixtures_today, get_standings, get_tournaments, run_sql_file, get_odds
from src.logger_config import setup_logging
from tabs.tab_05 import render_tab_05
from tabs.tab_06 import render_tab_06

setup_logging()
st.set_page_config(page_title="Tenis fixtures data", layout="wide")

DATA_SQL = "main_todays_games_details.sql"
DATA_CHECK_SQL = "check_max_event_date.sql"
APP_PASSWORD = st.secrets.get("APP_PASSWORD", os.getenv("APP_PASSWORD", ""))

EVENT_STATUS_COLORS = {
  "Not yet started": "#3B76BA",
  "In progress": "#E1E346",
  "Finished": "#903304",
  "Interrupted": "#8D3399",
  "Cancelled": "#cc0058",
}

PERCENTAGE_EXPORT_COLUMNS = [
  "p1_perc_h2h",
  "p2_perc_h2h",
  "p1_rend_all",
  "p1_rend_sup",
  "p2_rend_all",
  "p2_rend_sup",
]
ODDS_EXPORT_COLUMNS = ["p1_odds", "p2_odds"]
DATE_EXPORT_COLUMNS = ["event_date", "event_date_only"]

@st.cache_data
def load_data(sql_filename: str) -> pd.DataFrame:
  res = run_sql_file(sql_filename)
  if not res.get("success"):
    return pd.DataFrame()
  return pd.DataFrame(res.get("result") or [], columns=res.get("columns") or [])


def get_max_event_date() -> datetime.date | None:
  res = run_sql_file(DATA_CHECK_SQL)
  if not res.get("success"):
    return None
  df = pd.DataFrame(res.get("result") or [], columns=res.get("columns") or [])
  if df.empty:
    return None
  max_value = df.iloc[0, 0]
  if pd.isna(max_value):
    return None
  return pd.to_datetime(max_value, errors="coerce").date()


def normalize_multiselect_options(series: pd.Series):
  return sorted(series.dropna().unique().tolist())


def normalize_date_options(series: pd.Series):
  dates = pd.to_datetime(series, errors="coerce").dt.date
  return sorted({d for d in dates if pd.notna(d)})


def filter_df(
  df: pd.DataFrame,
  event_types,
  event_statuses,
  event_dates,
  event_genders,
  tournaments,
  surfaces,
):
  out = df
  if event_types:
    out = out[out["event_type"].isin(event_types)]
  if event_statuses:
    out = out[out["event_status"].isin(event_statuses)]
  if event_dates:
    out = out[out["event_date_only"].isin(event_dates)]
  if event_genders:
    out = out[out["event_gender"].isin(event_genders)]
  if tournaments:
    out = out[out["tournament_name"].isin(tournaments)]
  if surfaces:
    out = out[out["tournament_sourface"].isin(surfaces)]
  return out


def format_number_spanish(value, multiply_by_100: bool = False):
  numeric_value = pd.to_numeric(value, errors="coerce")
  if pd.isna(numeric_value):
    return value
  if multiply_by_100:
    numeric_value = numeric_value * 100
  us_format = f"{numeric_value:,.2f}"
  return us_format.replace(",", "_").replace(".", ",").replace("_", ".")


def format_percentage_spanish(value):
  numeric_value = pd.to_numeric(value, errors="coerce")
  if pd.isna(numeric_value):
    return value
  return f"{format_number_spanish(numeric_value, multiply_by_100=True)}%"


def format_date_day_month_year(value):
  parsed_date = pd.to_datetime(value, errors="coerce")
  if pd.isna(parsed_date):
    return value
  return parsed_date.strftime("%d/%m/%Y")


def format_export_dataframe(df: pd.DataFrame, use_spanish_format: bool) -> pd.DataFrame:
  export_df = df.copy()
  if not use_spanish_format:
    return export_df

  for column_name in DATE_EXPORT_COLUMNS:
    if column_name in export_df.columns:
      export_df[column_name] = export_df[column_name].apply(format_date_day_month_year)

  for column_name in PERCENTAGE_EXPORT_COLUMNS:
    if column_name in export_df.columns:
      export_df[column_name] = export_df[column_name].apply(format_percentage_spanish)

  for column_name in ODDS_EXPORT_COLUMNS:
    if column_name in export_df.columns:
      export_df[column_name] = export_df[column_name].apply(format_number_spanish)

  return export_df


def add_empty_line_after_each_csv_row(csv_text: str) -> str:
  if not csv_text:
    return csv_text
  normalized_text = csv_text.replace("\r\n", "\n")
  lines = normalized_text.split("\n")
  if len(lines) <= 1:
    return csv_text

  output_lines = [lines[0]]
  data_lines = lines[1:]
  for index, line in enumerate(data_lines):
    output_lines.append(line)
    if line and index < len(data_lines) - 1:
      output_lines.append("")

  return "\n".join(output_lines)


def require_password_login() -> None:
  if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

  if not APP_PASSWORD:
    st.error(
      "APP_PASSWORD is not configured. Add it in Streamlit secrets (or APP_PASSWORD env var) before deploying."
    )
    st.stop()

  if st.session_state.authenticated:
    with st.sidebar:
      if st.button("Logout", key="logout_button"):
        st.session_state.authenticated = False
        st.rerun()
    return

  st.title("Login")
  with st.form("login_form", clear_on_submit=True):
    entered_password = st.text_input("Password", type="password")
    submitted = st.form_submit_button("Login", type="primary")

  if submitted:
    if entered_password == APP_PASSWORD:
      st.session_state.authenticated = True
      st.rerun()
    else:
      st.error("Invalid password")

  st.stop()


require_password_login()
st.title("Tenis fixtures data")

if "auto_refresh_done" not in st.session_state:
  st.session_state.auto_refresh_done = True
  today = datetime.date.today()
  yesterday = today - timedelta(days=1)
  max_event_date = get_max_event_date()
  utc_now = datetime.datetime.now(datetime.timezone.utc)
  after_refresh_cutoff_utc = utc_now.hour >= 8
  is_older_than_yesterday = max_event_date is None or max_event_date < yesterday
  needs_refresh = after_refresh_cutoff_utc and is_older_than_yesterday

  if not needs_refresh:
    st.success("Data up to date.")
    logging.info(
      "Data is up to date. Max event date in DB: %s | UTC now: %s | After 08:00 UTC: %s | Older than yesterday: %s",
      max_event_date,
      utc_now.isoformat(),
      after_refresh_cutoff_utc,
      is_older_than_yesterday,
    )
  else:
    st.info("Updating data...")
    logging.info(
      "Data is not up to date. Max event date in DB: %s | UTC now: %s | After 08:00 UTC: %s | Older than yesterday: %s. Updating data...",
      max_event_date,
      utc_now.isoformat(),
      after_refresh_cutoff_utc,
      is_older_than_yesterday,
    )
    with st.spinner("Refreshing data..."):
      history_start = max_event_date or yesterday
      logging.info("Loading fixtures history from %s to %s", history_start, yesterday)
      get_fixtures_history(
        date_start=history_start,
        date_stop=yesterday,
      )
      get_fixtures_today(
        date_start=today - timedelta(days=1),
        date_stop=today + timedelta(days=2),
        table_name="fixtures_for_today",
      )
      get_odds(
        date_start=today - timedelta(days=1),
        date_stop=today + timedelta(days=5),
        table_name="odds_for_today",
      )

      if today.weekday() == 0:
        get_tournaments()
        get_standings()

      for sql_name in [
        "query_01_players_results.sql",
        "query_02_h2h_process.sql",
        "query_03_final_fixture_for_next_days.sql",
      ]:
        run_sql_file(sql_name)

    load_data.clear()
    st.success("Update complete.")

raw_df = load_data(DATA_SQL)

required_cols = ["event_type", "event_status", "tournament_name", "tournament_sourface"]
missing_cols = [col for col in required_cols if col not in raw_df.columns]
if missing_cols:
  st.error("Missing required columns: " + ", ".join(missing_cols))
  st.stop()

if "event_date" in raw_df.columns:
  raw_df = raw_df.copy()
  raw_df["event_date_only"] = pd.to_datetime(
    raw_df["event_date"], errors="coerce"
  ).dt.date

# Sidebar filters with interdependent options
st.sidebar.header("Filters")

# Step 1: event_date selection (default today, else All)
event_date_options = ["All"]
selected_event_dates = []
if "event_date_only" in raw_df.columns:
  all_event_dates = normalize_date_options(raw_df["event_date"])
  event_date_labels = [d.isoformat() for d in all_event_dates]
  event_date_options = ["All"] + event_date_labels
  today_label = pd.Timestamp.today().date().isoformat()
  default_date_label = today_label if today_label in event_date_labels else "All"
  selected_date_label = st.sidebar.pills(
    "event_date",
    options=event_date_options,
    default=default_date_label,
    selection_mode="single",
  )
  if selected_date_label != "All":
    selected_event_dates = [pd.to_datetime(selected_date_label).date()]

# Step 2: event_type selection (default Singles)
all_event_types = normalize_multiselect_options(raw_df["event_type"])
event_type_options = ["All"] + all_event_types
default_event_type = "Singles" if "Singles" in all_event_types else "All"
selected_event_type_label = st.sidebar.pills(
  "event_type",
  options=event_type_options,
  default=default_event_type,
  selection_mode="single",
)
selected_event_types = []
if selected_event_type_label != "All":
  selected_event_types = [selected_event_type_label]

# Step 3: event_gender selection (default Men)
event_gender_options = ["All"]
selected_event_genders = []
if "event_gender" in raw_df.columns:
  all_event_genders = normalize_multiselect_options(raw_df["event_gender"])
  event_gender_options = ["All"] + all_event_genders
  default_event_gender = "Men" if "Men" in all_event_genders else "All"
  selected_event_gender_label = st.sidebar.pills(
    "event_gender",
    options=event_gender_options,
    default=default_event_gender,
    selection_mode="single",
  )
  if selected_event_gender_label != "All":
    selected_event_genders = [selected_event_gender_label]

# Step 4: event_status selection (default All)
event_status_options = [
  "All",
  "Not yet started",
  "In progress",
  "Finished",
  "Interrupted",
  "Cancelled",
]
selected_event_status_label = st.sidebar.pills(
  "event_status",
  options=event_status_options,
  default="All",
  selection_mode="single",
)
selected_event_statuses = []
if selected_event_status_label != "All":
  selected_event_statuses = [selected_event_status_label]

# Step 5: tournament options depend on event_date + event_type + event_gender + event_status
et_filtered = filter_df(
  raw_df,
  selected_event_types,
  selected_event_statuses,
  selected_event_dates,
  selected_event_genders,
  [],
  [],
)
all_tournaments = normalize_multiselect_options(et_filtered["tournament_name"])
selected_tournaments = st.sidebar.multiselect(
    "tournament_name",
    options=all_tournaments,
    default=[],
)

# Step 6: surface options depend on event_date + event_type + event_gender + event_status + tournaments
et_t_filtered = filter_df(
  raw_df,
  selected_event_types,
  selected_event_statuses,
  selected_event_dates,
  selected_event_genders,
  selected_tournaments,
  [],
)
all_surfaces = normalize_multiselect_options(et_t_filtered["tournament_sourface"])
selected_surfaces = st.sidebar.multiselect(
    "tournament_sourface",
    options=all_surfaces,
    default=[],
)

apply_filters_upcoming = st.sidebar.toggle("Apply to Upcoming", value=False)

# Final filtered dataframe
filtered_df = filter_df(
  raw_df,
  selected_event_types,
  selected_event_statuses,
  selected_event_dates,
  selected_event_genders,
  selected_tournaments,
  selected_surfaces,
)

# Insights block
col1, col2, col3 = st.columns(3)
col1.metric("Games displayed", len(filtered_df))
col2.metric("Tournaments", filtered_df["tournament_name"].nunique())

# Last refresh based on load_timestamp (max)
if "load_timestamp" in filtered_df.columns and not filtered_df.empty:
    last_refresh = pd.to_datetime(filtered_df["load_timestamp"]).max()
    col3.metric("Last DB refresh (UTC)", last_refresh.strftime("%Y-%m-%d %H:%M:%S"))
else:
    col3.metric("Last DB refresh (UTC)", "-")

# Tabs

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Data", "Refresh", "Insights", "Upcoming", "Full analysis", "Results analysis"])




display_columns = [
#   "event_key",
  "event_date",
  "event_time",
  "event_status",
  "event_winner",
  "event_first_player",
#   "first_player_key",
  "event_second_player",
#   "second_player_key",
  "tournament_sourface",
  "tournament_name",
  "event_type_3",
  "p1_wins_h2h", #*
  "p1_perc_h2h", #*
  "p2_wins_h2h", #*
  "p2_perc_h2h", #*
  "p1_rend_all", #*
  "p1_rend_sup", #*
  "p1_points", #*
  "p2_rend_all", #*
  "p2_rend_sup", #*
  "p2_points", #* 
  # "event_type",
  # "event_type_2",
  # "event_type_type",
  # "event_gender",
#   "p1_wins_sourface",
#   "p1_losses_sourface",
#   "p1_wins_all",
#   "p1_losses_all",
#   "p1_rend_all", #*
#   "p1_rend_sup", #*
#   "p1_points", #*
#   "p2_wins_sourface",
#   "p2_losses_sourface",
#   "p2_wins_all",
#   "p2_losses_all",
#   "p2_rend_all", #*
#   "p2_rend_sup", #*
#   "p2_points", #*
#   "p1_wins_h2h", #*
#   "p1_perc_h2h", #*
#   "p2_wins_h2h", #*
  # "p2_perc_h2h", #*
  "p1_odds",
  "p2_odds",
  # "event_first_player_logo",
  # "event_second_player_logo",
#   "load_timestamp",
]
display_columns = [col for col in display_columns if col in filtered_df.columns]
filtered_df_columns_needed = filtered_df[display_columns].copy()


display_columns_tsv_filter = [
  "tournament_name",
  "event_date",
  "event_first_player",
  "event_second_player",
  "tournament_sourface",
  "p1_wins_h2h", #*
  "p1_perc_h2h", #*
  "p2_wins_h2h", #*
  "p2_perc_h2h", #*
  "p1_rend_all", #*
  "p1_rend_sup", #*
  "p1_points", #*
  "p2_rend_all", #*
  "p2_rend_sup", #*
  "p2_points", #*
]
display_columns_tsv = [col for col in display_columns_tsv_filter if col in filtered_df.columns]
# filtered_df_tsv = filtered_df[display_columns_tsv].copy()




with tab1:
    only_needed_columns = st.toggle("Only needed columns", value=False)
    table_columns = display_columns
    if only_needed_columns:
      table_columns = display_columns_tsv.copy()
      odds_columns = ["p1_odds", "p2_odds"]
      if "tournament_sourface" in table_columns:
        # insert_at = table_columns.index("tournament_sourface") + 1
        insert_at = table_columns.index("p2_points") + 1
      else:
        insert_at = 0
      for col in reversed(odds_columns):
        if col in filtered_df.columns and col not in table_columns:
          table_columns.insert(insert_at, col)
    filtered_df_columns_needed = filtered_df[table_columns].copy()
    table_event = st.dataframe(
        filtered_df_columns_needed,
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun",
        key="games_table",
        height=500,
        hide_index=True,
        column_config={
            "event_date": st.column_config.Column(
                "Date",
                help="Event date",
                # width="medium",
                required=True,
            ),
            "event_first_player": st.column_config.Column(
                "Player 1",
                help="Player 1",
                # width="medium",
                required=True,
            ),
            "event_second_player": st.column_config.Column(
                "Player 2",
                help="Player 2",
                # width="medium",
                required=True,
            ),
            # "tournament_sourface": st.column_config.Column(
            #     "Sourface",
            #     help="Tournament sourface",
            #     # width="medium",
            #     required=True,
            # ),
            "p1_wins_h2h": st.column_config.Column(
                "H2H P1",
                help="H2h wins P1",
                # width="medium",
                required=True,
            ),
            "p1_perc_h2h": st.column_config.ProgressColumn(
                "H2H % P1",
                help="H2h percentage wins P1",
                format="percent",
                min_value=0,
                max_value=1,
                color="auto"
            ),
            "p2_wins_h2h": st.column_config.Column(
                "H2H P2",
                help="H2h wins P2",
                # width="medium",
                required=True,
            ),
            "p2_perc_h2h": st.column_config.ProgressColumn(
                "H2H % P2",
                help="H2h percentage wins P2",
                format="percent",
                min_value=0,
                max_value=1,
                color="auto"
            ),
            "p1_rend_all": st.column_config.NumberColumn(
                "P1 Rec. Performance",
                help="P1 last year performance",
                format="percent",
                # width="medium",
                required=True,
            ),
            "p1_rend_sup": st.column_config.NumberColumn(
                "P1 Sourface R. Perf.",
                help="P1 last year performance in sourface",
                format="percent",
                # width="medium",
                required=True,
            ),
            "p1_points": st.column_config.NumberColumn(
                "P1 ATP points",
                help="P1 ATP points",
                # width="medium",
                format="accounting",
                step='int',
                required=True,
            ),
            "p2_rend_all": st.column_config.NumberColumn(
                "P2 Rec. Performance",
                help="P2 last year performance",
                format="percent",
                # width="medium",
                required=True,
            ),
            "p2_rend_sup": st.column_config.NumberColumn(
                "P2 Sourface R. Perf.",
                help="P2 last year performance in sourface",
                format="percent",
                # width="medium",
                required=True,
            ),
            "p2_points": st.column_config.NumberColumn(
                "P2 ATP points",
                help="P2 ATP points",
                # width="medium",
                format="accounting",
                step='int',
                required=True,
            ),
            "tournament_sourface": st.column_config.MultiselectColumn(
                "Sourface",
                help="Tournament sourface",
                options=[
                    "Hard",
                    "Clay",
                    "Grass",
                ],
                color=["#336699", "#993300", "#339966"],
                # format_func=lambda x: x.capitalize(),
            ),
            "event_status": st.column_config.MultiselectColumn(
                "Event Status",
                help="Event status",
                options=[
                  "Not yet started",
                  "In progress",
                  "Finished",
                  "Interrupted",
                  "Cancelled",
                ],
                color=["#3B76BA","#E1E346", "#903304", "#8D3399", "#cc0058"],
            ),
            "event_winner": st.column_config.MultiselectColumn(
                "Winner",
                help="Event winner",
                options=[
                  "P1",
                  "P2",
                ],
                color=["#E37636","#9F3FE9"],
            ),
            "event_first_player_logo": st.column_config.ImageColumn(
                "P1 Logo", help="First player logo"
            ),
            "event_second_player_logo": st.column_config.ImageColumn(
                "P2 Logo", help="Second player logo"
            ),
            "p1_odds": st.column_config.Column(
                "P1 Odds",
                help="Odds for player 1",
                required=True,
            ),
            "p2_odds": st.column_config.Column(
                "P2 Odds",
                help="Odds for player 2",
                required=True,
            ),
            "tournament_name": st.column_config.Column(
                "Tournament",
                help="Name of the tournament",
                required=True,
            ),
            "event_type_3": st.column_config.Column(
                "Event type",
                help="Type of the event",
                required=True,
            ),
        }
    )
    st.markdown("---")
    st.subheader("Download table")
    export_spanish_format = st.toggle(
      "Spanish spreadsheet format",
      value=True,
      help="Formats selected numeric columns for Spanish locale at download time only.",
    )
    export_double_line_spacing = st.toggle(
      "Empty line after each row",
      value=True,
      help="Adds one blank line between rows in the downloaded CSV.",
    )
    # Sort from the full filtered data so hidden columns (for example event_time)
    # can still be used as ordering keys before selecting export columns.
    export_source_df = filtered_df.copy()
    sort_columns = [col for col in ["tournament_name", "event_time"] if col in export_source_df.columns]
    if sort_columns:
      export_source_df = export_source_df.sort_values(by=sort_columns)
    export_df = export_source_df[filtered_df_columns_needed.columns].copy()
    export_df = format_export_dataframe(export_df, export_spanish_format)
    export_csv = export_df.to_csv(index=False, sep=",", quoting=csv.QUOTE_ALL)
    if export_double_line_spacing:
      export_csv = add_empty_line_after_each_csv_row(export_csv)
    st.download_button(
      "Download filtered data",
      data=export_csv.encode("utf-8-sig"),
      file_name="tennis_fixtures_export.csv",
      mime="text/csv",
      use_container_width=True,
    )
    st.markdown("---")
    st.subheader("Copy Game Row (TSV)")
    include_odds = st.toggle("Include odds", value=False)
    if include_odds:
      odds_columns = ["p1_odds", "p2_odds"]
      # insert_at = display_columns_tsv.index("tournament_sourface") + 1
      insert_at = display_columns_tsv.index("p2_points") + 1
      for col in reversed(odds_columns):
        if col in filtered_df.columns:
          display_columns_tsv.insert(insert_at, col)
    if filtered_df.empty:
        st.info("No games to copy with the current filters.")
    else:
        display_labels = (
            filtered_df["event_date"].astype(str)
            + " | "
            + filtered_df["event_first_player"].astype(str)
            + " vs "
            + filtered_df["event_second_player"].astype(str)
            + " | "
            + filtered_df["tournament_name"].astype(str)
        )
        label_to_index = dict(zip(display_labels, filtered_df.index))
        row_keys = list(label_to_index.keys())
        selected_row = None
        if table_event and table_event.selection.rows:
          selected_pos = table_event.selection.rows[0]
          if 0 <= selected_pos < len(filtered_df):
            selected_row = filtered_df.iloc[selected_pos]
        if selected_row is None:
            selected_label = st.selectbox(
                "Select game",
                options=row_keys,
            )
            selected_index = label_to_index[selected_label]
            selected_row = filtered_df.loc[selected_index]

        tsv_row = selected_row.copy()
        if "event_date" in tsv_row.index:
          tsv_row["event_date"] = format_date_day_month_year(tsv_row["event_date"])
        tsv_percentage_cols = [
          "p1_perc_h2h",
          "p2_perc_h2h",
          "p1_rend_all",
          "p1_rend_sup",
          "p2_rend_all",
          "p2_rend_sup",
        ]
        for perc_col in tsv_percentage_cols:
          if perc_col in tsv_row.index:
            formatted_percentage = format_percentage_spanish(tsv_row[perc_col])
            if pd.isna(pd.to_numeric(tsv_row[perc_col], errors="coerce")):
              tsv_row[perc_col] = "-"
            else:
              tsv_row[perc_col] = formatted_percentage

        for odds_col in ["p1_odds", "p2_odds"]:
          if odds_col in tsv_row.index:
            odds_value = pd.to_numeric(tsv_row[odds_col], errors="coerce")
            if pd.isna(odds_value):
              tsv_row[odds_col] = "-"
            else:
              tsv_row[odds_col] = f"{odds_value:.2f}".replace(".", ",")

        tsv_line = "\t".join(str(v) for v in tsv_row[display_columns_tsv].values)
        st.markdown(
            f"""
            <style>
              .tsv-box {{
                border-radius: 6px;
                padding: 10px;
                border: 1px solid;
              }}
              .tsv-label {{
                font-size: 12px;
                margin-bottom: 6px;
              }}
              .tsv-pre {{
                margin: 0;
                white-space: pre-wrap;
                word-break: break-word;
              }}
              @media (prefers-color-scheme: dark) {{
                .tsv-box {{
                  background: #1f2430;
                  border-color: #3a455e;
                  color: #e6e9f2;
                }}
                .tsv-label {{
                  color: #b6c2e0;
                }}
              }}
              @media (prefers-color-scheme: light) {{
                .tsv-box {{
                  background: #f3f6ff;
                  border-color: #d6defa;
                  color: #1d2740;
                }}
                .tsv-label {{
                  color: #4a5b7a;
                }}
              }}
            </style>
            <div class="tsv-box">
              <div class="tsv-label">TSV</div>
              <pre class="tsv-pre">{tsv_line}</pre>
            </div>
            """,
            unsafe_allow_html=True,
        )
        safe_tsv = tsv_line.replace("`", "\\`").replace("\\", "\\\\")
        copy_html = f"""
            <div style='margin-top:6px'>
              <button id='copy-btn' style='padding:6px 12px;'>Copy TSV</button>
              <span id='copy-msg' style='margin-left:8px;color:#2e7d32;'></span>
            </div>
            <script>
              const btn = document.getElementById('copy-btn');
              const msg = document.getElementById('copy-msg');
              const text = `{safe_tsv}`;
              btn.onclick = async () => {{
                try {{
                  await navigator.clipboard.writeText(text);
                  msg.textContent = 'Copied';
                  setTimeout(() => msg.textContent = '', 1200);
                }} catch (e) {{
                  msg.textContent = 'Copy failed';
                }}
              }};
            </script>
        """
        st.components.v1.html(copy_html, height=50)

with tab2:
  if "refresh_results" not in st.session_state:
    st.session_state.refresh_results = []
  if "refresh_had_error" not in st.session_state:
    st.session_state.refresh_had_error = False

  refresh_tournaments = st.checkbox("refresh_tournaments", value=False)
  refresh_standings = st.checkbox("refresh_standings", value=False)
  refresh_fixture_players = st.checkbox("refresh_fixture_players", value=False)
  # col_fp, col_days, _ = st.columns([1, 1, 4])
  refresh_daily_fixture = st.checkbox("refresh_daily_fixture", value=True)
  days=4
  # refresh_daily_fixture = col_fp.checkbox("refresh_daily_fixture", value=True)
  # days = col_days.selectbox("days", [1, 2, 3, 4, 5], index=1)
  refresh_h2h = st.checkbox("refresh_h2h", value=False)
  refresh_odds = st.checkbox("refresh_odds", value=False)

  if st.button("refresh database"):
    results = []
    with st.spinner("Refreshing data..."):
      today = datetime.date.today()

      if refresh_daily_fixture:
        get_fixtures_today(
          date_start=today - timedelta(days=1),
          date_stop=today + timedelta(days=days),
          table_name="fixtures_for_today",
          fetch_h2h=refresh_h2h,
        )
        results.append(("ok", "fixtures_for_today refreshed"))
      
      if refresh_fixture_players:
        get_fixtures_history(
          date_start=today - timedelta(days=2),
          date_stop=today - timedelta(days=1),
        )
        results.append(("ok", "fixtures_history refreshed"))
      
      if refresh_odds:
        get_odds(
          date_start=today - timedelta(days=1),
          date_stop=today + timedelta(days=5),
          table_name="odds_for_today",
        )
        results.append(("ok", "odds_for_today refreshed"))

      if refresh_tournaments:
        get_tournaments()
        results.append(("ok", "tournaments refreshed"))

      if refresh_standings:
        get_standings()
        results.append(("ok", "standings refreshed"))

      for sql_name in [
        "query_01_players_results.sql",
        "query_02_h2h_process.sql",
        "query_03_final_fixture_for_next_days.sql",
      ]:
        res = run_sql_file(sql_name)
        if res.get("success"):
          results.append(("ok", res.get("message", f"{sql_name} executed")))
        else:
          results.append(("error", res.get("message", f"{sql_name} failed")))

    st.session_state.refresh_results = results
    st.session_state.refresh_had_error = any(
      status == "error" for status, _ in results
    )

    load_data.clear()
    st.rerun()

  if st.session_state.refresh_results:
    if st.session_state.refresh_had_error:
      st.error("One or more steps failed. See details below.")
    else:
      st.success("Refresh complete.")

    for status, message in st.session_state.refresh_results:
      if status == "error":
        st.write(f"- ERROR: {message}")
      else:
        st.write(f"- OK: {message}")

with tab3:
  st.subheader("Fixtures dashboard")

  px = None
  if importlib.util.find_spec("plotly.express") is not None:
    px = importlib.import_module("plotly.express")

  if px is None:
    st.warning("Plotly is not installed in this environment. Install it with: pip install plotly")
    st.stop()

  if filtered_df.empty:
    st.info("No fixtures available for the current filters.")
  else:
    insights_df = filtered_df.copy()

    if "event_date_only" not in insights_df.columns and "event_date" in insights_df.columns:
      insights_df["event_date_only"] = pd.to_datetime(
        insights_df["event_date"], errors="coerce"
      ).dt.date

    for numeric_col in ["p1_points", "p2_points", "p1_odds", "p2_odds", "p1_perc_h2h", "p2_perc_h2h"]:
      if numeric_col in insights_df.columns:
        insights_df[numeric_col] = pd.to_numeric(insights_df[numeric_col], errors="coerce")

    if {"p1_points", "p2_points"}.issubset(insights_df.columns):
      insights_df["points_gap"] = (insights_df["p1_points"] - insights_df["p2_points"]).abs()

    if {"p1_odds", "p2_odds"}.issubset(insights_df.columns):
      insights_df["odds_gap"] = (insights_df["p1_odds"] - insights_df["p2_odds"]).abs()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Fixtures", len(insights_df))
    kpi2.metric(
      "Date span",
      f"{insights_df['event_date_only'].nunique()} days" if "event_date_only" in insights_df.columns else "-",
    )
    kpi3.metric(
      "Tournaments",
      insights_df["tournament_name"].nunique() if "tournament_name" in insights_df.columns else 0,
    )
    kpi4.metric(
      "Surfaces",
      insights_df["tournament_sourface"].nunique() if "tournament_sourface" in insights_df.columns else 0,
    )

    row1_col1, row1_col2 = st.columns(2)

    if {"event_date_only", "event_status"}.issubset(insights_df.columns):
      by_day_status = (
        insights_df.groupby(["event_date_only", "event_status"], dropna=False)
        .size()
        .reset_index(name="fixtures")
        .sort_values("event_date_only")
      )
      fig_day_status = px.bar(
        by_day_status,
        x="event_date_only",
        y="fixtures",
        color="event_status",
        color_discrete_map=EVENT_STATUS_COLORS,
        barmode="stack",
        title="Fixtures by day and status",
        labels={"event_date_only": "Date", "fixtures": "Matches", "event_status": "Status"},
      )
      row1_col1.plotly_chart(fig_day_status, use_container_width=True)

    if "event_status" in insights_df.columns:
      status_count = (
        insights_df.groupby("event_status", dropna=False)
        .size()
        .reset_index(name="fixtures")
      )
      fig_status = px.pie(
        status_count,
        names="event_status",
        values="fixtures",
        title="Status distribution",
        hole=0.45,
        color="event_status",
        color_discrete_map=EVENT_STATUS_COLORS,
      )
      row1_col2.plotly_chart(fig_status, use_container_width=True)

    row2_col1, row2_col2 = st.columns(2)

    if "tournament_name" in insights_df.columns:
      by_tournament = (
        insights_df.groupby("tournament_name", dropna=False)
        .size()
        .reset_index(name="fixtures")
        .sort_values("fixtures", ascending=False)
        .head(12)
      )
      fig_tournament = px.bar(
        by_tournament,
        x="fixtures",
        y="tournament_name",
        orientation="h",
        title="Top tournaments by fixtures",
        labels={"fixtures": "Matches", "tournament_name": "Tournament"},
      )
      fig_tournament.update_layout(yaxis={"categoryorder": "total ascending"})
      row2_col1.plotly_chart(fig_tournament, use_container_width=True)

    if "tournament_sourface" in insights_df.columns:
      by_surface = (
        insights_df.groupby("tournament_sourface", dropna=False)
        .size()
        .reset_index(name="fixtures")
      )
      fig_surface = px.bar(
        by_surface,
        x="tournament_sourface",
        y="fixtures",
        color="tournament_sourface",
        title="Surface distribution",
        labels={"tournament_sourface": "Surface", "fixtures": "Matches"},
      )
      row2_col2.plotly_chart(fig_surface, use_container_width=True)

    if {"p1_odds", "p2_odds"}.issubset(insights_df.columns):
      hover_fields = {
        "event_first_player": True,
        "event_second_player": True,
        "tournament_name": True,
      }
      if "odds_gap" in insights_df.columns:
        hover_fields["odds_gap"] = ":.2f"

      size_column = None
      if "points_gap" in insights_df.columns:
        valid_size = pd.to_numeric(insights_df["points_gap"], errors="coerce")
        if valid_size.notna().any():
          insights_df["points_gap_plot"] = valid_size.fillna(0).clip(lower=0)
          size_column = "points_gap_plot"

      fig_odds = px.scatter(
        insights_df,
        x="p1_odds",
        y="p2_odds",
        color="event_status" if "event_status" in insights_df.columns else None,
        color_discrete_map=EVENT_STATUS_COLORS,
        size=size_column,
        hover_data=hover_fields,
        title="Odds map (P1 vs P2)",
        labels={"p1_odds": "P1 odds", "p2_odds": "P2 odds", "event_status": "Status"},
      )
      fig_odds.update_traces(marker={"opacity": 0.75})
      st.plotly_chart(fig_odds, use_container_width=True)

with tab4:
  st.subheader("Upcoming games")

  if apply_filters_upcoming:
    upcoming_df = filtered_df.copy()
    st.info("Apply to Upcoming is On. Showing upcoming games using active filters.")
    st.markdown("---")
  else:
    upcoming_df = filter_df(
      raw_df,
      ["Singles"],
      ["Not yet started"],
      [],
      ["Men"],
      [],
      [],
    )
    st.warning(
      "Apply to Upcoming is Off. Showing the next 10 upcoming games for: Men | Singles | Not yet started"
    )
    st.markdown("---")

  if upcoming_df.empty:
    st.info("No fixtures available for the current filters")
  else:
    if "event_date" in upcoming_df.columns:
      upcoming_df["event_date_str"] = pd.to_datetime(
        upcoming_df["event_date"], errors="coerce"
      ).dt.date.astype(str)
    else:
      upcoming_df["event_date_str"] = ""

    if "event_time" in upcoming_df.columns:
      upcoming_df["event_time_str"] = upcoming_df["event_time"].astype(str)
    else:
      upcoming_df["event_time_str"] = ""

    upcoming_df["_sort_dt"] = pd.to_datetime(
      upcoming_df["event_date_str"] + " " + upcoming_df["event_time_str"],
      errors="coerce",
    )
    if upcoming_df["_sort_dt"].notna().any():
      upcoming_df = upcoming_df.sort_values(["_sort_dt"])
      if not apply_filters_upcoming:
        upcoming_df = upcoming_df.head(10)

    def format_value(value, suffix=""):
      if pd.isna(value):
        return "-"
      if isinstance(value, float):
        return f"{value:.2f}{suffix}" if suffix else f"{value:.2f}"
      return f"{value}{suffix}"

    def percent_value(value):
      if pd.isna(value):
        return "-"
      try:
        return f"{float(value) * 100:.1f}%"
      except (TypeError, ValueError):
        return "-"

    def pick_first(row, candidates):
      for col in candidates:
        if col in row and pd.notna(row[col]):
          return row[col]
      return None

    p1_standings_cols = ["p1_rank", "p1_ranking", "p1_position", "p1_points"]
    p2_standings_cols = ["p2_rank", "p2_ranking", "p2_position", "p2_points"]

    for _, row in upcoming_df.iterrows():
      event_line = ""
      if row.get("event_date_str"):
        event_line += row.get("event_date_str", "")
      if row.get("event_time_str"):
        event_line += f" {row.get('event_time_str', '')}"
      if row.get("tournament_name"):
        event_line += f" | {row.get('tournament_name', '')}"
      if event_line:
        st.markdown(f"**{event_line}**")

      status_value = row.get("event_status", "-")
      winner_value = row.get("event_winner", "-")
      status_color = EVENT_STATUS_COLORS.get(status_value, "#9aa0a6")
      st.markdown(
        """
        <div style="display:flex;align-items:center;gap:10px;margin:6px 0 2px;">
          <div style="width:10px;height:10px;border-radius:50%;background:{status_color};"></div>
          <div><strong>Status:</strong> {status_value}</div>
          <div><strong>Winner:</strong> {winner_value}</div>
        </div>
        """.format(status_color=status_color, status_value=status_value, winner_value=winner_value),
        unsafe_allow_html=True,
      )

      col_left, col_right = st.columns(2)

      with col_left:
        if "event_first_player_logo" in row and pd.notna(row["event_first_player_logo"]):
          st.image(row["event_first_player_logo"], width=120)
        st.markdown(f"**{row.get('event_first_player', '-') }**")
        st.caption(
          f"H2H wins: {format_value(row.get('p1_wins_h2h'))} | "
          f"H2H %: {percent_value(row.get('p1_perc_h2h'))}"
        )
        p1_standings = pick_first(row, p1_standings_cols)
        st.caption(f"Standings: {format_value(p1_standings)}")

      with col_right:
        if "event_second_player_logo" in row and pd.notna(row["event_second_player_logo"]):
          st.image(row["event_second_player_logo"], width=120)
        st.markdown(f"**{row.get('event_second_player', '-') }**")
        st.caption(
          f"H2H wins: {format_value(row.get('p2_wins_h2h'))} | "
          f"H2H %: {percent_value(row.get('p2_perc_h2h'))}"
        )
        p2_standings = pick_first(row, p2_standings_cols)
        st.caption(f"Standings: {format_value(p2_standings)}")

      st.divider()

    # if {"event_date_only", "event_time", "event_first_player", "event_second_player", "tournament_name", "event_status"}.issubset(insights_df.columns):
    #   upcoming_view = insights_df[
    #     [
    #       "event_date_only",
    #       "event_time",
    #       "event_first_player",
    #       "event_second_player",
    #       "tournament_name",
    #       "event_status",
    #     ]
    #   ].copy()
    #   upcoming_view = upcoming_view.sort_values(["event_date_only", "event_time"])
      # st.markdown("### Upcoming fixtures overview")
      # st.dataframe(upcoming_view, use_container_width=True, height=260)

with tab5:
  render_tab_05(run_sql_file)

with tab6:
  render_tab_06()
