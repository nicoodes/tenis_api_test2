import calendar
from datetime import date
import json
import time
import pandas as pd
import requests
import logging
from pathlib import Path
from src.logger_config import setup_logging

from dotenv import load_dotenv
from src.db_utils import get_db_connection, insert_dataframe_to_db
from src.secrets_utils import get_secret

import asyncio
import aiohttp

setup_logging()
load_dotenv()

BASE_URL = f"https://api.api-tennis.com/tennis/?method="
SCHEMA = "tenis_api"
SQL_DIR = Path(__file__).parent / "sql"  # added

API_KEY = get_secret("API_KEY")

def run_sql_file(filename: str) -> dict:
    """
    Read and execute a SQL query from a file in the sql/ directory.
    
    Args:
        filename: Name of the SQL file (e.g., 'queries_test.sql')
        
    Returns:
        dict with 'success' (bool), 'message' (str), 'result' (list of tuples or None),
        and 'columns' (list of column names or None)
    """
    sql_path = SQL_DIR / filename
    
    if not sql_path.exists():
        return {
            "success": False,
            "message": f"SQL file not found: {sql_path}",
            "result": None,
            "columns": None
        }
    
    connection = None
    cursor = None
    
    try:
        # Read the SQL file
        with open(sql_path, 'r') as f:
            query = f.read().strip()
        
        if not query:
            return {
                "success": False,
                "message": f"SQL file is empty: {filename}",
                "result": None,
                "columns": None
            }
        
        # Execute the query
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute(query)
        
        # Check if this is a SELECT query
        if cursor.description:
            result = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            rows_affected = len(result)
            return {
                "success": True,
                "message": f"Query executed successfully. Rows returned: {rows_affected}",
                "result": result,
                "columns": columns
            }
        else:
            # INSERT, UPDATE, DELETE, etc.
            connection.commit()
            rows_affected = cursor.rowcount
            return {
                "success": True,
                "message": f"Query executed successfully. Rows affected: {rows_affected}",
                "result": None,
                "columns": None
            }
    
    except Exception as e:
        if connection:
            connection.rollback()
        return {
            "success": False,
            "message": f"Failed to execute SQL file: {str(e)}",
            "result": None
        }
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def _ensure_schema(cursor, schema: str) -> None:
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

def _ensure_fixtures_table_pg(cursor, schema: str, table_name: str) -> None:
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.{table_name} (
            event_key BIGINT,
            event_date TEXT,
            event_time TEXT,
            event_first_player TEXT,
            first_player_key BIGINT,
            event_second_player TEXT,
            second_player_key BIGINT,
            event_final_result TEXT,
            event_game_result TEXT,
            event_serve TEXT,
            event_winner TEXT,
            event_status TEXT,
            event_type_type TEXT,
            tournament_name TEXT,
            tournament_key BIGINT,
            tournament_round TEXT,
            tournament_season TEXT,
            download_time TIMESTAMPTZ DEFAULT now()
        )
        """
    )

def _ensure_fixtures_today_table_pg(cursor, schema: str, table_name: str) -> None:
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.{table_name} (
            event_key BIGINT,
            event_date TEXT,
            event_time TEXT,
            event_first_player TEXT,
            first_player_key BIGINT,
            event_second_player TEXT,
            second_player_key BIGINT,
            event_first_player_logo TEXT,
            event_second_player_logo TEXT,
            event_final_result TEXT,
            event_game_result TEXT,
            event_serve TEXT,
            event_winner TEXT,
            event_status TEXT,
            event_type_type TEXT,
            tournament_name TEXT,
            tournament_key BIGINT,
            tournament_round TEXT,
            tournament_season TEXT,
            download_time TIMESTAMPTZ DEFAULT now()
        )
        """
    )

def _ensure_tournaments_table_pg(cursor, schema: str, table_name: str) -> None:
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.{table_name} (
            tournament_key BIGINT,
            tournament_name TEXT,
            event_type_key BIGINT,
            event_type_type TEXT,
            tournament_sourface TEXT,
            download_time TIMESTAMPTZ DEFAULT now()
        )
        """
    )

def _ensure_standings_table_pg(cursor, schema: str, table_name: str) -> None:
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.{table_name} (
            place TEXT,
            player TEXT,
            player_key BIGINT,
            league TEXT,
            movement TEXT,
            country TEXT,
            points TEXT,
            event_type TEXT,
            download_time TIMESTAMPTZ DEFAULT now()
        )
        """
    )

def _ensure_odds_table_pg(cursor, schema: str, table_name: str) -> None:
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.{table_name} (
            event_key BIGINT,
            betting_house TEXT,
            home_odds NUMERIC,
            away_odds NUMERIC,
            event_date TEXT,
            download_time TIMESTAMPTZ DEFAULT now()
        )
        """
    )

def _ensure_h2h_table_pg(cursor, schema: str, table_name: str) -> None:
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.{table_name} (
            event_key BIGINT,
            event_date TEXT,
            event_time TEXT,
            event_first_player TEXT,
            first_player_key BIGINT,
            event_second_player TEXT,
            second_player_key BIGINT,
            event_final_result TEXT,
            event_game_result TEXT,
            event_serve TEXT,
            event_winner TEXT,
            event_status TEXT,
            event_type_type TEXT,
            tournament_name TEXT,
            tournament_key BIGINT,
            tournament_round TEXT,
            tournament_season TEXT,
            download_time TIMESTAMPTZ DEFAULT now()
        )
        """
    )

def _fetch_fixtures_df(
    date_start: str,
    date_stop: str,
    base_url: str,
    method: str,
    api_key: str,
    include_logos: bool,
) -> pd.DataFrame | None:
    if not api_key:
        logging.error("Missing API_KEY environment variable")
        return None

    search = f"&date_start={date_start}&date_stop={date_stop}"
    authentication = f"&APIkey={api_key}"
    url = base_url + method + search + authentication

    try:
        response = requests.get(url, timeout=30)
    except requests.RequestException as exc:
        logging.error("Request to tennis API failed: %s", exc)
        return None

    if response.status_code == 500:
        logging.error("Server error (500)")
        logging.error(response.text)
        return None

    if response.status_code != 200:
        logging.error("HTTP Error %s", response.status_code)
        logging.error(response.text)
        return None

    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError:
        logging.error("Response is not valid JSON despite Content-Type header")
        logging.error(response.text[:1000])
        return None

    if not data.get("result"):
        logging.info("No live scores available at the moment.")
        return None

    events_records = []
    for event in data["result"]:
        event_record = {
            "event_key": event.get("event_key"),
            "event_date": event.get("event_date"),
            "event_time": event.get("event_time"),
            "event_first_player": event.get("event_first_player"),
            "first_player_key": event.get("first_player_key"),
            "event_second_player": event.get("event_second_player"),
            "second_player_key": event.get("second_player_key"),
            "event_final_result": event.get("event_final_result"),
            "event_game_result": event.get("event_game_result"),
            "event_serve": event.get("event_serve"),
            "event_winner": event.get("event_winner"),
            "event_status": event.get("event_status"),
            "event_type_type": event.get("event_type_type"),
            "tournament_name": event.get("tournament_name"),
            "tournament_key": event.get("tournament_key"),
            "tournament_round": event.get("tournament_round"),
            "tournament_season": event.get("tournament_season"),
        }

        if include_logos:
            event_record["event_first_player_logo"] = event.get(
                "event_first_player_logo"
            )
            event_record["event_second_player_logo"] = event.get(
                "event_second_player_logo"
            )

        events_records.append(event_record)

    if not events_records:
        logging.info("No event records to persist.")
        return None

    df_events = pd.DataFrame(events_records)
    for col in ["event_key", "first_player_key", "second_player_key", "tournament_key"]:
        if col in df_events.columns:
            df_events[col] = pd.to_numeric(df_events[col], errors="coerce").astype("Int64")

    return df_events


def get_fixtures_history(
    date_start: str,
    date_stop: str,
    base_url: str = BASE_URL,
    method: str = "get_fixtures",
    api_key: str = API_KEY,
    table_name: str = "fixtures_results",
) -> None:
    """Retrieve fixtures for historical ranges (no logos, no H2H)."""

    if not api_key:
        api_key = get_secret("API_KEY")

    df_events = _fetch_fixtures_df(
        date_start=date_start,
        date_stop=date_stop,
        base_url=base_url,
        method=method,
        api_key=api_key,
        include_logos=False,
    )
    if df_events is None or df_events.empty:
        return None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        _ensure_schema(cur, SCHEMA)
        _ensure_fixtures_table_pg(cur, SCHEMA, table_name)
        conn.commit()

        cur.execute(
            f"DELETE FROM {SCHEMA}.{table_name} WHERE event_date::date >= %s::date AND event_date::date <= %s::date",
            (date_start, date_stop),
        )
        rows_deleted = cur.rowcount
        conn.commit()

        if rows_deleted > 0:
            logging.info(
                "Deleted %s existing fixtures from %s.%s for date range %s to %s",
                rows_deleted,
                SCHEMA,
                table_name,
                date_start,
                date_stop,
            )

        res = insert_dataframe_to_db(df_events, SCHEMA, table_name)
        if res["success"]:
            logging.info(
                "Inserted %s fixtures into %s.%s",
                res["rows_inserted"],
                SCHEMA,
                table_name,
            )
        else:
            logging.error(res["message"])
    except Exception as exc:
        logging.error("Failed to insert fixtures into Postgres: %s", exc)
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


def get_fixtures_today(
    date_start: str,
    date_stop: str,
    base_url: str = BASE_URL,
    method: str = "get_fixtures",
    api_key: str = API_KEY,
    table_name: str = "fixtures_for_today",
    fetch_h2h: bool = True,
) -> None:
    """Retrieve fixtures for today/next days with logos and H2H."""

    if not api_key:
        api_key = get_secret("API_KEY")

    df_events = _fetch_fixtures_df(
        date_start=date_start,
        date_stop=date_stop,
        base_url=base_url,
        method=method,
        api_key=api_key,
        include_logos=True,
    )
    if df_events is None or df_events.empty:
        return None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        _ensure_schema(cur, SCHEMA)
        _ensure_fixtures_today_table_pg(cur, SCHEMA, table_name)
        conn.commit()

        cur.execute(f"DELETE FROM {SCHEMA}.{table_name}")
        rows_deleted = cur.rowcount
        conn.commit()

        if rows_deleted > 0:
            logging.info(
                "Deleted %s existing fixtures from %s.%s",
                rows_deleted,
                SCHEMA,
                table_name,
            )

        res = insert_dataframe_to_db(df_events, SCHEMA, table_name)
        if res["success"]:
            logging.info(
                "Inserted %s fixtures into %s.%s",
                res["rows_inserted"],
                SCHEMA,
                table_name,
            )
        else:
            logging.error(res["message"])
    except Exception as exc:
        logging.error("Failed to insert fixtures into Postgres: %s", exc)
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

    if fetch_h2h:
        player_pairs = df_events[["first_player_key", "second_player_key"]].drop_duplicates()

        logging.info("Fetching H2H data for %s player pairs asynchronously...", len(player_pairs))

        all_h2h_dfs = asyncio.run(_fetch_all_h2h_async(player_pairs, api_key))

        if all_h2h_dfs:
            df_all_h2h = pd.concat(all_h2h_dfs, ignore_index=True)

            try:
                conn = get_db_connection()
                cur = conn.cursor()
                _ensure_schema(cur, SCHEMA)
                _ensure_h2h_table_pg(cur, SCHEMA, "h2h_for_today2")

                cur.execute(f"DELETE FROM {SCHEMA}.h2h_for_today2")
                rows_deleted = cur.rowcount
                conn.commit()

                if rows_deleted > 0:
                    logging.info(
                        "Deleted %s existing H2H records from %s.h2h_for_today2",
                        rows_deleted,
                        SCHEMA,
                    )

                res = insert_dataframe_to_db(df_all_h2h, SCHEMA, "h2h_for_today2")
                if res["success"]:
                    logging.info(
                        "Inserted %s total H2H records into %s.h2h_for_today2 for %s player pairs",
                        res["rows_inserted"],
                        SCHEMA,
                        len(player_pairs),
                    )
                else:
                    logging.error(res["message"])
            except Exception as exc:
                logging.error("Failed to insert H2H data into Postgres: %s", exc)
            finally:
                try:
                    cur.close()
                    conn.close()
                except Exception:
                    pass


def get_fixtures(
    date_start: str,
    date_stop: str,
    base_url: str = BASE_URL,
    method: str = "get_fixtures",
    api_key: str = API_KEY,
    table_name: str = "fixtures_results",
    is_todays_data: bool = False,
) -> None:
    """Backward-compatible wrapper for fixtures loading."""
    if is_todays_data or table_name == "fixtures_for_today":
        return get_fixtures_today(
            date_start=date_start,
            date_stop=date_stop,
            base_url=base_url,
            method=method,
            api_key=api_key,
            table_name=table_name,
            fetch_h2h=True,
        )

    return get_fixtures_history(
        date_start=date_start,
        date_stop=date_stop,
        base_url=base_url,
        method=method,
        api_key=api_key,
        table_name=table_name,
    )


def get_tournaments(
    base_url: str = BASE_URL,
    method: str = "get_tournaments",
    api_key: str = API_KEY,
    table_name: str = "tournaments",
) -> None:
    """Function to retrieve all tournaments from the tennis API."""

    if not api_key:
        api_key = get_secret("API_KEY")

    if not api_key:
        logging.error("Missing API_KEY environment variable")
        return None

    authentication = f"&APIkey={api_key}"
    url = base_url + method + authentication

    try:
        response = requests.get(url, timeout=30)
    except requests.RequestException as exc:
        logging.error("Request to tennis API failed: %s", exc)
        return None

    if response.status_code == 500:
        logging.error("Server error (500)")
        logging.error(response.text)
        return None

    if response.status_code != 200:
        logging.error("HTTP Error %s", response.status_code)
        logging.error(response.text)
        return None

    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError:
        logging.error("Response is not valid JSON despite Content-Type header")
        logging.error(response.text[:1000])
        return None

    if not data.get("result"):
        logging.info("No tournaments available.")
        return None

    tournament_records = []

    for tournament in data["result"]:
        tournament_record = {
            "tournament_key": tournament.get("tournament_key"),
            "tournament_name": tournament.get("tournament_name"),
            "event_type_key": tournament.get("event_type_key"),
            "event_type_type": tournament.get("event_type_type"),
            "tournament_sourface": tournament.get("tournament_sourface"),
        }
        tournament_records.append(tournament_record)

    if not tournament_records:
        logging.info("No tournament records to persist.")
        return None

    df_tournaments = pd.DataFrame(tournament_records)

    # Normalize numeric IDs
    for col in ["tournament_key", "event_type_key"]:
        if col in df_tournaments.columns:
            df_tournaments[col] = pd.to_numeric(df_tournaments[col], errors="coerce").astype("Int64")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        _ensure_schema(cur, SCHEMA)
        _ensure_tournaments_table_pg(cur, SCHEMA, table_name)
        # Refresh data
        cur.execute(f"DELETE FROM {SCHEMA}.{table_name}")
        conn.commit()

        res = insert_dataframe_to_db(df_tournaments, SCHEMA, table_name)
        if res["success"]:
            logging.info(
                "Refreshed %s tournaments in %s.%s",
                res["rows_inserted"],
                SCHEMA,
                table_name,
            )
        else:
            logging.error(res["message"])
    except Exception as exc:
        logging.error("Failed to insert tournaments into Postgres: %s", exc)
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass



def get_standings(
    event_types: list[str] | tuple[str, ...] = ("ATP", "WTA"),
    base_url: str = BASE_URL,
    method: str = "get_standings",
    api_key: str = API_KEY,
    table_name: str = "standings",
) -> None:
    """Function to retrieve all standings (ATP/WTA) from the tennis API."""

    if not api_key:
        api_key = get_secret("API_KEY")

    if not api_key:
        logging.error("Missing API_KEY environment variable")
        return None

    authentication = f"&APIkey={api_key}"
    standings_records = []

    for event_type in event_types:
        search = f"&event_type={event_type}"
        url = base_url + method + search + authentication

        try:
            response = requests.get(url, timeout=30)
        except requests.RequestException as exc:
            logging.error("Request to tennis API failed for event_type=%s: %s", event_type, exc)
            return None

        if response.status_code == 500:
            logging.error("Server error (500) for event_type=%s", event_type)
            logging.error(response.text)
            return None

        if response.status_code != 200:
            logging.error("HTTP Error %s for event_type=%s", response.status_code, event_type)
            logging.error(response.text)
            return None

        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            logging.error("Response is not valid JSON despite Content-Type header for event_type=%s", event_type)
            logging.error(response.text[:1000])
            return None

        if not data.get("result"):
            logging.info("No standings available for event_type=%s.", event_type)
            continue

        for row in data["result"]:
            standings_records.append(
                {
                    "place": row.get("place"),
                    "player": row.get("player"),
                    "player_key": row.get("player_key"),
                    "league": row.get("league"),
                    "movement": row.get("movement"),
                    "country": row.get("country"),
                    "points": row.get("points"),
                    "event_type": event_type,
                }
            )

    if not standings_records:
        logging.info("No standings records to persist for event_types=%s.", event_types)
        return None

    df_standings = pd.DataFrame(standings_records)

    # Clean player_key that might come as '2382.0'
    if "player_key" in df_standings.columns:
        df_standings["player_key"] = pd.to_numeric(df_standings["player_key"], errors="coerce").astype("Int64")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        _ensure_schema(cur, SCHEMA)
        _ensure_standings_table_pg(cur, SCHEMA, table_name)
        # Refresh data
        cur.execute(f"DELETE FROM {SCHEMA}.{table_name}")
        conn.commit()

        res = insert_dataframe_to_db(df_standings, SCHEMA, table_name)
        if res["success"]:
            logging.info(
                "Refreshed %s standings (event_types=%s) in %s.%s",
                res["rows_inserted"],
                event_types,
                SCHEMA,
                table_name,
            )
        else:
            logging.error(res["message"])
    except Exception as exc:
        logging.error("Failed to insert standings into Postgres: %s", exc)
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


def get_odds(
    date_start: str,
    date_stop: str,
    base_url: str = BASE_URL,
    method: str = "get_odds",
    api_key: str = API_KEY,
    table_name: str = "raw_odds_today",
) -> None:
    """Function to retrieve odds (Home/Away) from the tennis API."""

    if not api_key:
        api_key = get_secret("API_KEY")

    if not api_key:
        logging.error("Missing API_KEY environment variable")
        return None

    search = f"&date_start={date_start}&date_stop={date_stop}"
    authentication = f"&APIkey={api_key}"
    url = base_url + method + search + authentication

    try:
        response = requests.get(url, timeout=30)
    except requests.RequestException as exc:
        logging.error("Request to tennis API failed: %s", exc)
        return None

    if response.status_code == 500:
        logging.error("Server error (500)")
        logging.error(response.text)
        return None

    if response.status_code != 200:
        logging.error("HTTP Error %s", response.status_code)
        logging.error(response.text)
        return None

    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError:
        logging.error("Response is not valid JSON despite Content-Type header")
        logging.error(response.text[:1000])
        return None

    if not data.get("result"):
        logging.info("No odds available at the moment.")
        return None

    # Lists to collect odds data
    odds_records = []

    for event_key, event_odds in data["result"].items():
        # Extract Home/Away odds only
        home_away = event_odds.get("Home/Away", {})
        
        if not home_away:
            continue
            
        home_odds = home_away.get("Home", {})
        away_odds = home_away.get("Away", {})
        
        # Get all betting houses from home odds
        for betting_house, home_odd_value in home_odds.items():
            away_odd_value = away_odds.get(betting_house)
            
            if away_odd_value:  # Only add if both home and away odds exist
                odds_record = {
                    "event_key": event_key,
                    "betting_house": betting_house,
                    "home_odds": home_odd_value,
                    "away_odds": away_odd_value,
                    "event_date": date_start,  # Using the date_start as event_date
                }
                odds_records.append(odds_record)

    if not odds_records:
        logging.info("No odds records to persist.")
        return None

    df_odds = pd.DataFrame(odds_records)

    # Normalize event_key to Int64
    if "event_key" in df_odds.columns:
        df_odds["event_key"] = pd.to_numeric(df_odds["event_key"], errors="coerce").astype("Int64")
    
    # Normalize odds to numeric
    for col in ["home_odds", "away_odds"]:
        if col in df_odds.columns:
            df_odds[col] = pd.to_numeric(df_odds[col], errors="coerce")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        _ensure_schema(cur, SCHEMA)
        _ensure_odds_table_pg(cur, SCHEMA, table_name)
        
        # Delete all existing records to refresh the table
        cur.execute(f"DELETE FROM {SCHEMA}.{table_name}")
        rows_deleted = cur.rowcount
        conn.commit()
        
        if rows_deleted > 0:
            logging.info(
                "Deleted %s existing odds from %s.%s",
                rows_deleted,
                SCHEMA,
                table_name,
            )

        res = insert_dataframe_to_db(df_odds, SCHEMA, table_name)
        if res["success"]:
            logging.info(
                "Inserted %s odds records into %s.%s for date %s",
                res["rows_inserted"],
                SCHEMA,
                table_name,
                date_start,
            )
        else:
            logging.error(res["message"])
    except Exception as exc:
        logging.error("Failed to insert odds into Postgres: %s", exc)
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

async def _fetch_all_h2h_async(player_pairs, api_key: str, max_concurrent: int = 20):
    """Helper function to fetch all H2H data concurrently with a limit on simultaneous requests.
    
    Args:
        player_pairs: DataFrame with columns 'first_player_key' and 'second_player_key'
        api_key: API key for authentication
        max_concurrent: Maximum number of concurrent API requests (default: 20)
        
    Returns:
        List of DataFrames with H2H data
    """
    all_h2h_dfs = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_with_semaphore(first_player_key, second_player_key, session):
        """Wrapper to limit concurrent requests using a semaphore."""
        async with semaphore:
            return await get_h2h_async(
                first_player_key=first_player_key,
                second_player_key=second_player_key,
                session=session,
                api_key=api_key,
            )
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for _, row in player_pairs.iterrows():
            first_player_key = int(row["first_player_key"])
            second_player_key = int(row["second_player_key"])
            
            task = fetch_with_semaphore(
                first_player_key=first_player_key,
                second_player_key=second_player_key,
                session=session,
            )
            tasks.append(task)
        
        # Execute all requests with max_concurrent limit
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None results and exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logging.error("Exception occurred while fetching H2H data: %s", result)
            elif result is not None:
                all_h2h_dfs.append(result)
    
    logging.info("Successfully fetched H2H data for %s out of %s player pairs", len(all_h2h_dfs), len(player_pairs))
    return all_h2h_dfs

async def get_h2h_async(
    first_player_key: int,
    second_player_key: int,
    session: aiohttp.ClientSession,
    base_url: str = BASE_URL,
    method: str = "get_H2H",
    api_key: str = API_KEY,
):
    """Async function to retrieve head-to-head data between two players from the tennis API.
    
    Args:
        first_player_key: First player's key
        second_player_key: Second player's key
        session: aiohttp ClientSession for making requests
        base_url: Base API URL
        method: API method name (must be 'get_H2H')
        api_key: API key
        
    Returns:
        DataFrame with H2H records or None if no data available
    """

    if not api_key:
        api_key = get_secret("API_KEY")

    if not api_key:
        logging.error("Missing API_KEY environment variable")
        return None

    search = f"&first_player_key={first_player_key}&second_player_key={second_player_key}"
    authentication = f"&APIkey={api_key}"
    url = base_url + method + search + authentication

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status == 500:
                text = await response.text()
                logging.error("Server error (500) for H2H players %s vs %s", first_player_key, second_player_key)
                logging.error(text)
                return None

            if response.status != 200:
                text = await response.text()
                logging.error("HTTP Error %s for H2H players %s vs %s", response.status, first_player_key, second_player_key)
                logging.error(text)
                return None

            try:
                data = await response.json()
            except Exception as exc:
                text = await response.text()
                logging.error("Response is not valid JSON for H2H players %s vs %s: %s", first_player_key, second_player_key, exc)
                logging.error(text[:1000])
                return None

    except asyncio.TimeoutError:
        logging.error("Request timeout for H2H players %s vs %s", first_player_key, second_player_key)
        return None
    except Exception as exc:
        logging.error("Request to tennis API failed for H2H players %s vs %s: %s", first_player_key, second_player_key, exc)
        return None

    if not data.get("result"):
        logging.info("No H2H data available for players %s vs %s.", first_player_key, second_player_key)
        return None

    result = data["result"]
    h2h_records = []

    # Process H2H matches only
    for h2h_match in result.get("H2H", []):
        h2h_record = {
            "event_key": h2h_match.get("event_key"),
            "event_date": h2h_match.get("event_date"),
            "event_time": h2h_match.get("event_time"),
            "event_first_player": h2h_match.get("event_first_player"),
            "first_player_key": h2h_match.get("first_player_key"),
            "event_second_player": h2h_match.get("event_second_player"),
            "second_player_key": h2h_match.get("second_player_key"),
            "event_final_result": h2h_match.get("event_final_result"),
            "event_game_result": h2h_match.get("event_game_result"),
            "event_serve": h2h_match.get("event_serve"),
            "event_winner": h2h_match.get("event_winner"),
            "event_status": h2h_match.get("event_status"),
            "event_type_type": h2h_match.get("event_type_type"),
            "tournament_name": h2h_match.get("tournament_name"),
            "tournament_key": h2h_match.get("tournament_key"),
            "tournament_round": h2h_match.get("tournament_round"),
            "tournament_season": h2h_match.get("tournament_season"),
        }
        h2h_records.append(h2h_record)

    if not h2h_records:
        logging.info("No H2H records found for players %s vs %s.", first_player_key, second_player_key)
        return None

    df_h2h = pd.DataFrame(h2h_records)

    # Normalize numeric IDs to Int64
    for col in ["event_key", "first_player_key", "second_player_key", "tournament_key"]:
        if col in df_h2h.columns:
            df_h2h[col] = pd.to_numeric(df_h2h[col], errors="coerce").astype("Int64")

    logging.info(
        "Retrieved %s H2H records for players %s vs %s",
        len(df_h2h),
        first_player_key,
        second_player_key,
    )
    
    return df_h2h


def get_h2h(
    first_player_key: int,
    second_player_key: int,
    base_url: str = BASE_URL,
    method: str = "get_H2H",
    api_key: str = API_KEY,
    table_name: str = "h2h_for_today2",
):
    """Synchronous function to retrieve head-to-head data between two players from the tennis API.
    
    Args:
        first_player_key: First player's key
        second_player_key: Second player's key
        base_url: Base API URL
        method: API method name (must be 'get_H2H')
        api_key: API key
        table_name: Table name to store H2H data (not used, kept for compatibility)
        
    Returns:
        DataFrame with H2H records or None if no data available
    """

    if not api_key:
        api_key = get_secret("API_KEY")

    if not api_key:
        logging.error("Missing API_KEY environment variable")
        return None

    search = f"&first_player_key={first_player_key}&second_player_key={second_player_key}"
    authentication = f"&APIkey={api_key}"
    url = base_url + method + search + authentication

    try:
        response = requests.get(url, timeout=30)
    except requests.RequestException as exc:
        logging.error("Request to tennis API failed for H2H: %s", exc)
        return None

    if response.status_code == 500:
        logging.error("Server error (500) for H2H")
        logging.error(response.text)
        return None

    if response.status_code != 200:
        logging.error("HTTP Error %s for H2H", response.status_code)
        logging.error(response.text)
        return None

    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError:
        logging.error("Response is not valid JSON despite Content-Type header for H2H")
        logging.error(response.text[:1000])
        return None

    if not data.get("result"):
        logging.info("No H2H data available for players %s vs %s.", first_player_key, second_player_key)
        return None

    result = data["result"]
    h2h_records = []

    # Process H2H matches only
    for h2h_match in result.get("H2H", []):
        h2h_record = {
            "event_key": h2h_match.get("event_key"),
            "event_date": h2h_match.get("event_date"),
            "event_time": h2h_match.get("event_time"),
            "event_first_player": h2h_match.get("event_first_player"),
            "first_player_key": h2h_match.get("first_player_key"),
            "event_second_player": h2h_match.get("event_second_player"),
            "second_player_key": h2h_match.get("second_player_key"),
            "event_final_result": h2h_match.get("event_final_result"),
            "event_game_result": h2h_match.get("event_game_result"),
            "event_serve": h2h_match.get("event_serve"),
            "event_winner": h2h_match.get("event_winner"),
            "event_status": h2h_match.get("event_status"),
            "event_type_type": h2h_match.get("event_type_type"),
            "tournament_name": h2h_match.get("tournament_name"),
            "tournament_key": h2h_match.get("tournament_key"),
            "tournament_round": h2h_match.get("tournament_round"),
            "tournament_season": h2h_match.get("tournament_season"),
        }
        h2h_records.append(h2h_record)

    if not h2h_records:
        logging.info("No H2H records found for players %s vs %s.", first_player_key, second_player_key)
        return None

    df_h2h = pd.DataFrame(h2h_records)

    # Normalize numeric IDs to Int64
    for col in ["event_key", "first_player_key", "second_player_key", "tournament_key"]:
        if col in df_h2h.columns:
            df_h2h[col] = pd.to_numeric(df_h2h[col], errors="coerce").astype("Int64")

    logging.info(
        "Retrieved %s H2H records for players %s vs %s",
        len(df_h2h),
        first_player_key,
        second_player_key,
    )
    
    return df_h2h







if __name__ == "__main__":
    get_tournaments()
    get_standings()
