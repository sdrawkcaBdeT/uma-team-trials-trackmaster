-- sql/01_create_tables.sql

-- The schema name you requested
CREATE SCHEMA IF NOT EXISTS team_trails_trackmaster;

SET search_path TO team_trails_trackmaster;

-- Drop tables if they exist (for easy re-running during dev)
DROP TABLE IF EXISTS uma_scores;
DROP TABLE IF EXISTS team_trial_runs;
DROP TYPE IF EXISTS run_status;

-- Create the ENUM type for our validation flow
CREATE TYPE run_status AS ENUM ('pending_validation', 'approved', 'rejected');

-- Main table to log each /submit command
CREATE TABLE team_trial_runs (
    event_id VARCHAR(32) PRIMARY KEY, -- "2025-W46-EVT-001"
    discord_user_id BIGINT NOT NULL,
    discord_user_name VARCHAR(100) NOT NULL,
    run_date DATE NOT NULL,
    run_week VARCHAR(10) NOT NULL, -- "2025-W46"
    notes VARCHAR(255),
    status run_status NOT NULL DEFAULT 'pending_validation'
);

-- Table to store all 15 scores associated with one run
CREATE TABLE uma_scores (
    score_id SERIAL PRIMARY KEY,
    event_id VARCHAR(32) NOT NULL 
        REFERENCES team_trial_runs(event_id) ON DELETE CASCADE,
    uma_name VARCHAR(100) NOT NULL,
    team VARCHAR(20) NOT NULL, -- 'Mile', 'Sprint', etc.
    score INT NOT NULL
);

-- Create indexes for faster querying
CREATE INDEX idx_uma_scores_event_id ON uma_scores (event_id);
CREATE INDEX idx_uma_scores_uma_name ON uma_scores (uma_name);
CREATE INDEX idx_uma_scores_team ON uma_scores (team);
CREATE INDEX idx_runs_status ON team_trial_runs (status);