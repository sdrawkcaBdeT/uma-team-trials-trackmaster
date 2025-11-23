# trackmaster/core/database.py

import psycopg2
from psycopg2 import pool, extras
import logging
import os
import pandas as pd
from typing import List, Dict, Any, Optional
from trackmaster.config import settings
import datetime
from trackmaster.core.utils import get_current_season_id

logger = logging.getLogger(__name__)

# The schema name you specified
SCHEMA_NAME = "team_trails_trackmaster"
RUNS_TABLE = f"{SCHEMA_NAME}.team_trial_runs"
SCORES_TABLE = f"{SCHEMA_NAME}.uma_scores"
ROSTER_TABLE = f"{SCHEMA_NAME}.user_roster_settings"

class DatabaseManager:
    """
    Manages all database operations using a synchronous psycopg2 connection pool.
    """
    def __init__(self):
        self.pool = None
        try:
            # Create a thread-safe connection pool
            self.pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                database=settings.DB_NAME
            )
            logger.info("Database connection pool created successfully.")
        except psycopg2.Error as e:
            logger.critical(f"Error creating database connection pool: {e}")
            raise

    def get_conn(self):
        """Gets a connection from the pool."""
        if self.pool is None:
            raise Exception("Database pool is not initialized.")
        return self.pool.getconn()

    def release_conn(self, conn):
        """Releases a connection back to the pool."""
        if self.pool:
            self.pool.putconn(conn)

    def close_all(self):
        """Closes all connections in the pool."""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connection pool closed.")

    def initialize_database(self):
        """
        Creates the schema and all necessary tables, based on your function.
        """
        conn = self.get_conn()
        if not conn:
            logger.error("Could not get DB connection to initialize.")
            return

        with conn.cursor() as cursor:
            try:
                # Use SQL from our dedicated file
                sql_file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'sql', '01_create_tables.sql')
                
                with open(sql_file_path, 'r') as f:
                    sql_commands = f.read()
                
                cursor.execute(sql_commands)
                conn.commit()
                logger.info("Database tables created or verified successfully.")
            except (psycopg2.Error, FileNotFoundError) as e:
                logger.error(f"Error initializing tables: {e}")
                conn.rollback()
            finally:
                self.release_conn(conn)

    def create_pending_run(self, user_id: int, user_name: str, roster_id: int, scores: List[Dict[str, Any]]) -> str:
        """
        Saves a new run and its scores to the DB in a single transaction.
        This is a SYNCHRONOUS function.
        """
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                # 1. Create the event ID
                now = datetime.datetime.now(datetime.UTC)
                week_str = get_current_season_id(now)
                
                # Get next event ID for this week
                cursor.execute(
                    f"SELECT COUNT(*) FROM {RUNS_TABLE} WHERE run_week = %s", (week_str,)
                )
                next_id = cursor.fetchone()[0] + 1
                event_id = f"{week_str}-EVT-{next_id:03d}"
                
                # 2. Insert the main run record
                cursor.execute(
                    f"""
                    INSERT INTO {RUNS_TABLE} 
                        (event_id, discord_user_id, roster_id, discord_user_name, run_date, run_week, status) 
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending_validation')
                    """,
                    (event_id, user_id, roster_id, user_name, now.date(), week_str)
                )
                
                # 3. Insert all scores
                score_data_tuples = [
                    (event_id, uma['name'], uma.get('epithet'), uma['team'], uma['score'])
                    for uma in scores
                ]
                
                extras.execute_values(
                    cursor,
                    f"INSERT INTO {SCORES_TABLE} (event_id, uma_name, epithet, team, score) VALUES %s",
                    score_data_tuples
                )
                
                conn.commit()
                return event_id
        except psycopg2.Error as e:
            logger.error(f"Error creating pending run: {e}")
            conn.rollback()
            raise # Re-raise the exception to be caught by the cog
        finally:
            self.release_conn(conn)

    def set_run_status(self, event_id: str, status: str) -> bool:
        """Sets the status of a run (e.g., 'approved' or 'rejected')."""
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                if status == 'rejected':
                    # We use ON DELETE CASCADE, so this deletes linked scores too
                    cursor.execute(f"DELETE FROM {RUNS_TABLE} WHERE event_id = %s", (event_id,))
                else:
                    cursor.execute(
                        f"UPDATE {RUNS_TABLE} SET status = %s WHERE event_id = %s",
                        (status, event_id)
                    )
                conn.commit()
                return True
        except psycopg2.Error as e:
            logger.error(f"Error setting run status: {e}")
            conn.rollback()
            return False
        finally:
            self.release_conn(conn)

    def get_leaderboard_data(self, user_id: int = None, roster_id: int = None, week: str = None) -> Optional[pd.DataFrame]:
        """Fetches the main leaderboard data, with optional filters."""
        conn = self.get_conn()
        try:
            params = []
            where_clauses = ["r.status = 'approved'"]
            
            if user_id is not None:
                where_clauses.append("r.discord_user_id = %s")
                params.append(user_id)

            if roster_id is not None:
                where_clauses.append("r.roster_id = %s")
                params.append(roster_id)
            
            if week is not None:
                where_clauses.append("r.run_week = %s")
                params.append(week)

            where_sql = " AND ".join(where_clauses)
            
            # We join user_roster_settings (urs) to get the display_name if it exists
            # We use ARRAY_AGG(... ORDER BY s.score DESC)[1] to pick the user associated with the MAX score.
            sql_query = f"""
                SELECT 
                    s.uma_name,
                    s.epithet,
                    s.team,
                    MAX(s.score) as max_score,
                    AVG(s.score) as avg_score,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY s.score DESC) as p95_score,
                    (ARRAY_AGG(COALESCE(urs.display_name, r.discord_user_name) ORDER BY s.score DESC))[1] as trainer_name
                FROM {SCORES_TABLE} s
                JOIN {RUNS_TABLE} r ON s.event_id = r.event_id
                LEFT JOIN {ROSTER_TABLE} urs ON r.discord_user_id = urs.discord_user_id
                WHERE {where_sql}
                GROUP BY s.uma_name, s.epithet, s.team
                ORDER BY max_score DESC;
            """
            df = pd.read_sql(sql_query, conn, params=params)

            if not df.empty:
                df['avg_score'] = df['avg_score'].round(0).astype(int)
                df['p95_score'] = df['p95_score'].round(0).astype(int)
            
            return df
        except psycopg2.Error as e:
            logger.error(f"Error getting leaderboard data: {e}")
            return None
        finally:
            self.release_conn(conn)
    
    # --- UPDATED FUNCTION ---
    def get_team_summary_data(self, user_id: int = None, roster_id: int = None, week: str = None) -> Optional[pd.DataFrame]:
        """
        Fetches the team summary data, with optional filters.
        """
        conn = self.get_conn()
        try:
            # Build query dynamically
            params = []
            where_clauses = ["r.status = 'approved'"]
            
            # --- THIS IS THE NEW LOGIC ---
            if user_id is not None:
                where_clauses.append("r.discord_user_id = %s")
                params.append(user_id)
            # --- END NEW LOGIC ---

            if roster_id is not None:
                where_clauses.append("r.roster_id = %s")
                params.append(roster_id)
            
            if week is not None:
                where_clauses.append("r.run_week = %s")
                params.append(week)

            where_sql = " AND ".join(where_clauses)
            
            sql_query = f"""
                SELECT 
                    s.event_id, 
                    s.team, 
                    SUM(s.score) as team_total_score
                FROM {SCORES_TABLE} s
                JOIN {RUNS_TABLE} r ON s.event_id = r.event_id
                WHERE {where_sql}
                GROUP BY s.event_id, s.team;
            """
            
            df_team_scores = pd.read_sql(sql_query, conn, params=params)

            if df_team_scores.empty:
                return pd.DataFrame(columns=["team", "AvgTeamBest", "MedianTeamBest", "P95TeamBest"])

            # Step 2: Aggregate with pandas
            team_summary = df_team_scores.groupby('team')['team_total_score'].agg(
                AvgTeamBest='mean',
                MedianTeamBest='median',
                P95TeamBest=lambda x: x.quantile(0.95)
            ).reset_index()
            
            # Format numbers
            team_summary['AvgTeamBest'] = team_summary['AvgTeamBest'].round(0).astype(int)
            team_summary['MedianTeamBest'] = team_summary['MedianTeamBest'].round(0).astype(int)
            team_summary['P95TeamBest'] = team_summary['P95TeamBest'].round(0).astype(int)

            return team_summary

        except psycopg2.Error as e:
            logger.error(f"Error getting team summary data: {e}")
            return None
        finally:
            self.release_conn(conn)
    
    def update_single_score(self, event_id: str, original_name: str, new_name: str, new_epithet: str, new_team: str, new_score: int) -> bool:
        """Updates a single uma_score record based on user correction."""
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {SCORES_TABLE}
                    SET 
                        uma_name = %s,
                        epithet = %s,
                        team = %s,
                        score = %s
                    WHERE
                        event_id = %s AND uma_name = %s
                    """,
                    (new_name, new_epithet, new_team, new_score, event_id, original_name)
                )

                updated_rows = cursor.rowcount
                conn.commit()

                if updated_rows == 0:
                    logger.warning(f"Edit failed: No row found for {original_name} in {event_id}")
                    return False
                return True

        except psycopg2.Error as e:
            logger.error(f"Error updating single score: {e}")
            conn.rollback()
            return False
        finally:
            self.release_conn(conn)
            
    def set_user_active_roster(self, user_id: int, roster_id: int) -> bool:
        """Sets or updates a user's active roster ID."""
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {ROSTER_TABLE} (discord_user_id, active_roster_id)
                    VALUES (%s, %s)
                    ON CONFLICT (discord_user_id) DO UPDATE SET active_roster_id = %s
                    """,
                    (user_id, roster_id, roster_id)
                )
                conn.commit()
                return True
        except psycopg2.Error as e:
            logger.error(f"Error setting active roster: {e}")
            conn.rollback()
            return False
        finally:
            self.release_conn(conn)

    def get_user_active_roster(self, user_id: int) -> int:
        """Gets a user's active roster ID, defaulting to 1."""
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT active_roster_id FROM {ROSTER_TABLE} WHERE discord_user_id = %s",
                    (user_id,)
                )
                row = cursor.fetchone()
                if row:
                    return row[0]
                else:
                    return 1 # Default to 1
        except psycopg2.Error as e:
            logger.error(f"Error getting active roster: {e}")
            return 1 # Default to 1 on error
        finally:
            self.release_conn(conn)
            
    def set_user_display_name(self, user_id: int, display_name: str) -> bool:
        """Sets a custom display name for the user."""
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                # Upsert: Update if exists, Insert if not (using default roster 1)
                cursor.execute(
                    f"""
                    INSERT INTO {ROSTER_TABLE} (discord_user_id, active_roster_id, display_name)
                    VALUES (%s, 1, %s)
                    ON CONFLICT (discord_user_id) 
                    DO UPDATE SET display_name = %s
                    """,
                    (user_id, display_name, display_name)
                )
                conn.commit()
                return True
        except psycopg2.Error as e:
            logger.error(f"Error setting display name: {e}")
            conn.rollback()
            return False
        finally:
            self.release_conn(conn)
    
    def get_coach_data(self, user_id: int, roster_id: int = None):
        """
        Fetches complex analytics for the Coach Panel.
        Returns:
            - bottleneck_df: Which teams are the bottleneck and how often.
            - underperformer_df: Umas ranked by lowest Team Delta (The "Weak Links").
        """
        conn = self.get_conn()
        try:
            params = [user_id]
            roster_filter = ""
            if roster_id:
                roster_filter = "AND r.roster_id = %s"
                params.append(roster_id)
            
            # 1. Identify the Team Bottlenecks (Lowest Scoring Teams)
            sql_bottleneck = f"""
                SELECT 
                    b.team,
                    COUNT(*) as times_bottleneck,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY b.team_total) as median_score
                FROM v_event_bottlenecks b
                JOIN {RUNS_TABLE} r ON b.event_id = r.event_id
                WHERE r.discord_user_id = %s 
                  AND r.status = 'approved'
                  AND b.rank_asc = 1 -- Only the lowest scoring team
                  {roster_filter}
                GROUP BY b.team
                ORDER BY times_bottleneck DESC, median_score ASC;
            """
            bottleneck_df = pd.read_sql(sql_bottleneck, conn, params=params)

            # 2. Identify the Weakest Umas (Lowest Delta vs their own Team)
            # We filter for Umas who are typically on the Bottleneck teams
            sql_umas = f"""
                SELECT 
                    s.uma_name,
                    s.team,
                    COUNT(s.score) as run_count,
                    AVG(s.score) as avg_score,
                    MAX(s.score) as max_score,
                    AVG(s.delta_team) as avg_delta_team -- Negative means they drag the team down
                FROM v_score_details s
                JOIN {RUNS_TABLE} r ON s.event_id = r.event_id
                WHERE r.discord_user_id = %s 
                  AND r.status = 'approved'
                  {roster_filter}
                GROUP BY s.uma_name, s.team
                HAVING COUNT(s.score) >= 2 -- Ignore one-offs
                ORDER BY avg_delta_team ASC; -- Worst relative performers first
            """
            uma_df = pd.read_sql(sql_umas, conn, params=params)

            return bottleneck_df, uma_df

        except psycopg2.Error as e:
            logger.error(f"Error getting coach data: {e}")
            return None, None
        finally:
            self.release_conn(conn)