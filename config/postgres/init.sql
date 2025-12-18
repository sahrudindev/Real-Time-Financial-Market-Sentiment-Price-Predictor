-- PostgreSQL Initialization Script
-- Creates separate schemas for different components

-- Create schemas
CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS airflow;
CREATE SCHEMA IF NOT EXISTS mlflow;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA warehouse TO mlops_user;
GRANT ALL PRIVILEGES ON SCHEMA airflow TO mlops_user;
GRANT ALL PRIVILEGES ON SCHEMA mlflow TO mlops_user;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully at %', NOW();
END $$;
