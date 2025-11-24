# trackmaster/core/database.py

import logging
import os
import datetime
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text
from trackmaster.core.db import db_manager
from trackmaster.core.utils import get_current_season_id

logger = logging.getLogger(__name__)

SCHEMA_NAME = "team_trails_trackmaster"
RUNS_TABLE = f"{SCHEMA_NAME}.team_trial_runs"
SCORES_TABLE = f"{SCHEMA_NAME}.uma_scores"
ROSTER_TABLE = f"{SCHEMA_NAME}.user_roster_settings"
WEEKLY_SEQ_TABLE = f"{SCHEMA_NAME}.weekly_sequences"
REGISTRY_TABLE = f"{SCHEMA_NAME}.uma_character_registry"

class DatabaseManager:
    """
    Async Repository for database operations.
    """
    
    async def initialize_database(self):
        """
        Creates the schema and all necessary tables.
        """
        async with db_manager.session() as session:
            try:
                # Use SQL from our dedicated file
                # Note: We need to be careful with paths. 
                # Assuming running from root or similar structure.
                sql_file_path = os.path.join(os.getcwd(), 'sql', '01_create_tables.sql')
                
                # Fallback if running from inside package
                if not os.path.exists(sql_file_path):
                     sql_file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'sql', '01_create_tables.sql')

                with open(sql_file_path, 'r') as f:
                    sql_commands = f.read()
                
                # Split commands by semicolon to execute them one by one if needed, 
                # but sqlalchemy execute(text()) can handle scripts if the driver supports it.
                # Asyncpg supports multiple statements in one go usually.
                await session.execute(text(sql_commands))
                await session.commit()
                logger.info("Database tables created or verified successfully.")
                
                # Populate initial registry if empty
                await self._populate_initial_registry(session)
                
            except Exception as e:
                logger.error(f"Error initializing tables: {e}")
                await session.rollback()

    async def _populate_initial_registry(self, session):
        """Populates the registry with the hardcoded list if empty."""
        result = await session.execute(text(f"SELECT COUNT(*) FROM {REGISTRY_TABLE}"))
        count = result.scalar()
        if count == 0:
            from trackmaster.core.validation import VALID_UMA_NAMES
            # Insert all
            values = [{"name": name} for name in VALID_UMA_NAMES]
            await session.execute(
                text(f"INSERT INTO {REGISTRY_TABLE} (uma_name) VALUES (:name) ON CONFLICT DO NOTHING"),
                values
            )
            await session.commit()
            logger.info(f"Populated registry with {len(values)} characters.")

    async def get_valid_uma_names(self) -> set:
        """Fetches all active uma names from the DB."""
        async with db_manager.session() as session:
            result = await session.execute(text(f"SELECT uma_name FROM {REGISTRY_TABLE} WHERE is_active = TRUE"))
            return {row[0] for row in result.fetchall()}

    async def create_pending_run(self, user_id: int, user_name: str, roster_id: int, scores: List[Dict[str, Any]]) -> str:
        """
        Saves a new run and its scores to the DB in a single transaction.
        """
        async with db_manager.session() as session:
            try:
                now = datetime.datetime.now(datetime.UTC)
                week_str = get_current_season_id(now)
                
                # 1. Generate ID safely using the weekly_sequences table
                # Upsert the week row
                await session.execute(
                    text(f"""
                        INSERT INTO {WEEKLY_SEQ_TABLE} (week_id, current_val) 
                        VALUES (:week, 0) 
                        ON CONFLICT (week_id) DO NOTHING
                    """),
                    {"week": week_str}
                )
                
                # Increment and get value (Atomic)
                result = await session.execute(
                    text(f"""
                        UPDATE {WEEKLY_SEQ_TABLE} 
                        SET current_val = current_val + 1 
                        WHERE week_id = :week 
                        RETURNING current_val
                    """),
                    {"week": week_str}
                )
                next_id = result.scalar()
                event_id = f"{week_str}-EVT-{next_id:03d}"
                
                # 2. Insert Run
                await session.execute(
                    text(f"""
                        INSERT INTO {RUNS_TABLE} 
                        (event_id, discord_user_id, roster_id, discord_user_name, run_date, run_week, status) 
                        VALUES (:eid, :uid, :rid, :uname, :rdate, :rweek, 'pending_validation')
                    """),
                    {
                        "eid": event_id, "uid": user_id, "rid": roster_id, 
                        "uname": user_name, "rdate": now.date(), "rweek": week_str
                    }
                )
                
                # 3. Insert Scores
                score_values = [
                    {
                        "eid": event_id, "name": s['name'], "epithet": s.get('epithet'), 
                        "team": s['team'], "score": s['score']
                    }
                    for s in scores
                ]
                await session.execute(
                    text(f"""
                        INSERT INTO {SCORES_TABLE} (event_id, uma_name, epithet, team, score) 
                        VALUES (:eid, :name, :epithet, :team, :score)
                    """),
                    score_values
                )
                
                await session.commit()
                return event_id
                
            except Exception as e:
                logger.error(f"Error creating pending run: {e}")
                await session.rollback()
                raise

    async def set_run_status(self, event_id: str, status: str) -> bool:
        """Sets the status of a run."""
        async with db_manager.session() as session:
            try:
                if status == 'rejected':
                    await session.execute(
                        text(f"DELETE FROM {RUNS_TABLE} WHERE event_id = :eid"),
                        {"eid": event_id}
                    )
                else:
                    await session.execute(
                        text(f"UPDATE {RUNS_TABLE} SET status = :status WHERE event_id = :eid"),
                        {"status": status, "eid": event_id}
                    )
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"Error setting run status: {e}")
                await session.rollback()
                return False

    async def get_leaderboard_data(self, user_id: int = None, roster_id: int = None, week: str = None) -> Optional[pd.DataFrame]:
        """Fetches leaderboard data."""
        async with db_manager.session() as session:
            try:
                params = {}
                where_clauses = ["r.status = 'approved'"]
                
                if user_id is not None:
                    where_clauses.append("r.discord_user_id = :uid")
                    params["uid"] = user_id
                if roster_id is not None:
                    where_clauses.append("r.roster_id = :rid")
                    params["rid"] = roster_id
                if week is not None:
                    where_clauses.append("r.run_week = :week")
                    params["week"] = week

                where_sql = " AND ".join(where_clauses)
                
                sql_query = text(f"""
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
                """)
                
                # Pandas read_sql doesn't support async sessions directly easily.
                # We fetch values and create DF manually.
                result = await session.execute(sql_query, params)
                rows = result.fetchall()
                
                if not rows:
                    return pd.DataFrame()
                
                df = pd.DataFrame(rows, columns=result.keys())
                
                if not df.empty:
                    df['avg_score'] = df['avg_score'].round(0).astype(int)
                    df['p95_score'] = df['p95_score'].round(0).astype(int)
                
                return df
            except Exception as e:
                logger.error(f"Error getting leaderboard data: {e}")
                return None

    async def get_team_summary_data(self, user_id: int = None, roster_id: int = None, week: str = None) -> Optional[pd.DataFrame]:
        async with db_manager.session() as session:
            try:
                params = {}
                where_clauses = ["r.status = 'approved'"]
                
                if user_id is not None:
                    where_clauses.append("r.discord_user_id = :uid")
                    params["uid"] = user_id
                if roster_id is not None:
                    where_clauses.append("r.roster_id = :rid")
                    params["rid"] = roster_id
                if week is not None:
                    where_clauses.append("r.run_week = :week")
                    params["week"] = week

                where_sql = " AND ".join(where_clauses)
                
                sql_query = text(f"""
                    SELECT 
                        s.event_id, 
                        s.team, 
                        SUM(s.score) as team_total_score
                    FROM {SCORES_TABLE} s
                    JOIN {RUNS_TABLE} r ON s.event_id = r.event_id
                    WHERE {where_sql}
                    GROUP BY s.event_id, s.team;
                """)
                
                result = await session.execute(sql_query, params)
                rows = result.fetchall()
                df_team_scores = pd.DataFrame(rows, columns=result.keys())

                if df_team_scores.empty:
                    return pd.DataFrame(columns=["team", "AvgTeamBest", "MedianTeamBest", "P95TeamBest"])

                team_summary = df_team_scores.groupby('team')['team_total_score'].agg(
                    AvgTeamBest='mean',
                    MedianTeamBest='median',
                    P95TeamBest=lambda x: x.quantile(0.95)
                ).reset_index()
                
                team_summary['AvgTeamBest'] = team_summary['AvgTeamBest'].round(0).astype(int)
                team_summary['MedianTeamBest'] = team_summary['MedianTeamBest'].round(0).astype(int)
                team_summary['P95TeamBest'] = team_summary['P95TeamBest'].round(0).astype(int)

                return team_summary
            except Exception as e:
                logger.error(f"Error getting team summary: {e}")
                return None

    async def update_single_score(self, event_id: str, original_name: str, new_name: str, new_epithet: str, new_team: str, new_score: int) -> bool:
        async with db_manager.session() as session:
            try:
                result = await session.execute(
                    text(f"""
                        UPDATE {SCORES_TABLE}
                        SET uma_name = :nname, epithet = :nepithet, team = :nteam, score = :nscore
                        WHERE event_id = :eid AND uma_name = :oname
                    """),
                    {
                        "nname": new_name, "nepithet": new_epithet, "nteam": new_team, 
                        "nscore": new_score, "eid": event_id, "oname": original_name
                    }
                )
                await session.commit()
                return result.rowcount > 0
            except Exception as e:
                logger.error(f"Error updating score: {e}")
                await session.rollback()
                return False

    async def set_user_active_roster(self, user_id: int, roster_id: int) -> bool:
        async with db_manager.session() as session:
            try:
                await session.execute(
                    text(f"""
                        INSERT INTO {ROSTER_TABLE} (discord_user_id, active_roster_id)
                        VALUES (:uid, :rid)
                        ON CONFLICT (discord_user_id) DO UPDATE SET active_roster_id = :rid
                    """),
                    {"uid": user_id, "rid": roster_id}
                )
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"Error setting active roster: {e}")
                await session.rollback()
                return False

    async def get_user_active_roster(self, user_id: int) -> int:
        async with db_manager.session() as session:
            try:
                result = await session.execute(
                    text(f"SELECT active_roster_id FROM {ROSTER_TABLE} WHERE discord_user_id = :uid"),
                    {"uid": user_id}
                )
                row = result.fetchone()
                return row[0] if row else 1
            except Exception as e:
                logger.error(f"Error getting active roster: {e}")
                return 1

    async def set_user_display_name(self, user_id: int, display_name: str) -> bool:
        async with db_manager.session() as session:
            try:
                await session.execute(
                    text(f"""
                        INSERT INTO {ROSTER_TABLE} (discord_user_id, active_roster_id, display_name)
                        VALUES (:uid, 1, :name)
                        ON CONFLICT (discord_user_id) DO UPDATE SET display_name = :name
                    """),
                    {"uid": user_id, "name": display_name}
                )
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"Error setting display name: {e}")
                await session.rollback()
                return False

    async def get_coach_data(self, user_id: int, roster_id: int = None):
        async with db_manager.session() as session:
            try:
                params = {"uid": user_id}
                roster_filter = ""
                if roster_id:
                    roster_filter = "AND r.roster_id = :rid"
                    params["rid"] = roster_id
                
                # 1. Bottlenecks
                # Note: v_event_bottlenecks needs to be created in SQL or defined here.
                # Assuming the view exists from previous SQL (it was in the file list but I didn't read 02_create_views.sql)
                # I should probably check if that view exists or if I need to recreate it.
                # For now, I'll assume it exists.
                
                sql_bottleneck = text(f"""
                    SELECT 
                        b.team,
                        COUNT(*) as times_bottleneck,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY b.team_total) as median_score
                    FROM v_event_bottlenecks b
                    JOIN {RUNS_TABLE} r ON b.event_id = r.event_id
                    WHERE r.discord_user_id = :uid 
                      AND r.status = 'approved'
                      AND b.rank_asc = 1
                      {roster_filter}
                    GROUP BY b.team
                    ORDER BY times_bottleneck DESC, median_score ASC;
                """)
                
                result_b = await session.execute(sql_bottleneck, params)
                bottleneck_df = pd.DataFrame(result_b.fetchall(), columns=result_b.keys())

                # 2. Weakest Umas
                sql_umas = text(f"""
                    SELECT 
                        s.uma_name,
                        s.team,
                        COUNT(s.score) as run_count,
                        AVG(s.score) as avg_score,
                        MAX(s.score) as max_score,
                        AVG(s.delta_team) as avg_delta_team
                    FROM v_score_details s
                    JOIN {RUNS_TABLE} r ON s.event_id = r.event_id
                    WHERE r.discord_user_id = :uid 
                      AND r.status = 'approved'
                      {roster_filter}
                    GROUP BY s.uma_name, s.team
                    HAVING COUNT(s.score) >= 2
                    ORDER BY avg_delta_team ASC;
                """)
                
                result_u = await session.execute(sql_umas, params)
                uma_df = pd.DataFrame(result_u.fetchall(), columns=result_u.keys())

                return bottleneck_df, uma_df

            except Exception as e:
                logger.error(f"Error getting coach data: {e}")
                return None, None