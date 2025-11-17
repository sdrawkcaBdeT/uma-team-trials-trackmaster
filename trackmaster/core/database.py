# trackmaster/core/database.py

import psycopg2
from psycopg2 import pool, extras
import logging
import os
import pandas as pd
from typing import List, Dict, Any, Optional
from trackmaster.config import settings # Using our new config file
import datetime

logger = logging.getLogger(__name__)

# The schema name you specified
SCHEMA_NAME = "team_trails_trackmaster"
RUNS_TABLE = f"{SCHEMA_NAME}.team_trial_runs"
SCORES_TABLE = f"{SCHEMA_NAME}.uma_scores"

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

    def create_pending_run(self, user_id: int, user_name: str, scores: List[Dict[str, Any]]) -> str:
        """
        Saves a new run and its scores to the DB in a single transaction.
        This is a SYNCHRONOUS function.
        """
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                # 1. Create the event ID
                now = datetime.datetime.now(datetime.UTC)
                week_str = now.strftime("%Y-W%W")
                
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
                        (event_id, discord_user_id, discord_user_name, run_date, run_week, status) 
                    VALUES (%s, %s, %s, %s, %s, 'pending_validation')
                    """,
                    (event_id, user_id, user_name, now.date(), week_str)
                )
                
                # 3. Insert all scores
                score_data_tuples = [
                    (event_id, uma['name'], uma['team'], uma['score'])
                    for uma in scores
                ]
                
                extras.execute_values(
                    cursor,
                    f"INSERT INTO {SCORES_TABLE} (event_id, uma_name, team, score) VALUES %s",
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

    def get_leaderboard_data(self) -> Optional[pd.DataFrame]:
        """Fetches the main leaderboard data, replicating your sheet."""
        conn = self.get_conn()
        try:
            # Your "Leaderboard" tab
            sql_query = f"""
                SELECT 
                    uma_name,
                    team,
                    MAX(score) as max_score,
                    AVG(score) as avg_score,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY score DESC) as p95_score
                FROM {SCORES_TABLE} s
                JOIN {RUNS_TABLE} r ON s.event_id = r.event_id
                WHERE r.status = 'approved'
                GROUP BY uma_name, team
                ORDER BY max_score DESC;
            """
            df = pd.read_sql(sql_query, conn)
            return df
        except psycopg2.Error as e:
            logger.error(f"Error getting leaderboard data: {e}")
            return None
        finally:
            self.release_conn(conn)
    
    def get_team_summary_data(self) -> Optional[pd.DataFrame]:
        """
        Fetches the team summary data, replicating your sheet's logic.
        This calculates the total score per team, per run, and then
        aggregates those totals to get the Avg, Median, and P95.
        """
        conn = self.get_conn()
        try:
            # Step 1: Get the total score for each team (Sprint, Mile, etc.)
            # within each approved event (run).
            sql_query = f"""
                SELECT 
                    event_id, 
                    team, 
                    SUM(score) as team_total_score
                FROM {SCORES_TABLE} s
                JOIN {RUNS_TABLE} r ON s.event_id = r.event_id
                WHERE r.status = 'approved'
                GROUP BY event_id, team;
            """
            df_team_scores = pd.read_sql(sql_query, conn)

            if df_team_scores.empty:
                return pd.DataFrame(columns=["Team", "AvgTeamBest", "MedianTeamBest", "P95TeamBest"])

            # Step 2: Now, aggregate *those* results using pandas
            # This replicates your sheet's AvgTeamBest, MedianTeamBest, etc.
            team_summary = df_team_scores.groupby('team')['team_total_score'].agg(
                AvgTeamBest='mean',
                MedianTeamBest='median',
                P95TeamBest=lambda x: x.quantile(0.95)
            ).reset_index()
            
            # Format numbers for cleaner display
            team_summary['AvgTeamBest'] = team_summary['AvgTeamBest'].round(0).astype(int)
            team_summary['MedianTeamBest'] = team_summary['MedianTeamBest'].round(0).astype(int)
            team_summary['P95TeamBest'] = team_summary['P95TeamBest'].round(0).astype(int)

            return team_summary

        except psycopg2.Error as e:
            logger.error(f"Error getting team summary data: {e}")
            return None
        finally:
            self.release_conn(conn)
    
    def update_single_score(self, event_id: str, original_name: str, new_name: str, new_team: str, new_score: int) -> bool:
        """Updates a single uma_score record based on user correction."""
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {SCORES_TABLE}
                    SET 
                        uma_name = %s,
                        team = %s,
                        score = %s
                    WHERE
                        event_id = %s AND uma_name = %s
                    """,
                    (new_name, new_team, new_score, event_id, original_name)
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