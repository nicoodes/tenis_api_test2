# Streamlit app to get tenis data

# Filters and Considerations Summary (for analysis scope)

This document summarizes **what data is being considered/excluded** and **column corrections/standardizations** in each SQL file.

## 1) `src/sql/query_01_players_results.sql`

### Data scope and filters

- Player universe is built from distinct `first_player_key` and `second_player_key` in `tenis_api.fixtures_for_today`.
- From `tenis_api.fixtures_results`, only matches where either player is in that universe are considered.
- Date filter applied: `event_date::date between current_date-365 and current_date` (last 365 days).
- Event status filter applied: only `('Finished', 'Retired', 'Awarded', 'Walk Over')`.
- Exhibition matches are excluded: `lower(event_type_type) not like '%exhibition%'`.

### Data quality / corrections

- Duplicate handling: dedup by `event_key` using `row_number()`, keeping `rn = 1`.
- Surface normalization for output tables:
  - remove `" (Indoor)"`
  - apply `initcap(...)`
  - empty/null surface mapped to `'unkn'`.

### Output notes

- Creates:
  - `tenis_api.stg_players_results_by_sourface`
  - `tenis_api.stg_players_results_all`
- Includes `draws_or_other_*` where winner is null.

---

## 2) `src/sql/query_02_h2h_process.sql`

### Data scope and filters

- Source table: `tenis_api.h2h_for_today2`.
- **No explicit filter is currently applied** for status/type/exhibition in this script.

### Data quality / corrections

- Player keys are normalized into a consistent pair order (`p1_final`, `p2_final`) to avoid directional duplicates.
- Win flags are only set when `event_winner` is exactly:
  - `'First Player'` for player 1 win
  - `'Second Player'` for player 2 win
- Final output is expanded to both directions of each pair (so each matchup is available for both player orders).
- H2H percentages are rounded to 4 decimals and protected with `nullif(...,0)` for division safety.

### Output notes

- Creates: `tenis_api.stg_h2h_for_today_processed`.

---

## 3) `src/sql/query_03_final_fixture_for_next_days.sql`

### Data scope and filters

- Base source: `tenis_api.fixtures_for_today` (joined with tournaments/standings/staging tables).
- No explicit exhibition exclusion is applied in this file.
- Odds join is filtered to one bookmaker: `betting_house = 'bet365'`.

### Column standardization / corrections

- `event_status` remapped to analysis labels:
  - `('Finished', 'Retired', 'Awarded', 'Walk Over')` -> `'Finished'`
  - statuses like `'Set%'` -> `'In progress'`
  - `'Cancelled'` and `'Interrupted'` preserved
  - everything else -> `'Not yet started'`
- `event_winner` normalized:
  - `'First Player'` -> `'P1'`
  - `'Second Player'` -> `'P2'`
- `event_type` normalized from `event_type_type`:
  - contains `'Singles'` -> `'Singles'`
  - contains `'Doubles'` -> `'Doubles'`
  - else -> `'unkn'`
- `event_type_2` cleanup:
  - remove `' Singles'`, `' Doubles'`, and `'-'`
  - then `trim(...)`
- `event_gender` normalization:
  - contains `'Men'` or `'Atp'` -> `'Men'`
  - contains `'Women'` or `'Wta'` -> `'Women'`
  - else -> `'unkn'`
- `tournament_sourface` normalized same as Query 1:
  - remove `" (Indoor)"`, `initcap`, null/empty -> `'unkn'`
- Default player image URL applied when logos are null.
- Null fallback values in final output:
  - H2H fields coalesced to `0`
  - standings points coalesced to `'0'`.

### Output notes

- Creates: `tenis_api.main_todays_games_details`.

---

## Quick caveats to share

- Exhibition exclusion is explicitly active in Query 1, but not explicitly applied in Query 2 and Query 3.
- Query 1 dedup keeps `rn = 1` by `download_time` order (current implementation detail).
- Several text dimensions are intentionally standardized to `'unkn'` when missing/empty to keep downstream tables consistent.
