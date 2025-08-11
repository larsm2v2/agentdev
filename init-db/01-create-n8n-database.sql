-- Create additional databases required by the services
-- This script runs during PostgreSQL container initialization

-- Create n8n database
CREATE DATABASE n8n OWNER librarian_user;
GRANT ALL PRIVILEGES ON DATABASE n8n TO librarian_user;

-- Optional: Create additional schemas or users if needed in the future
-- CREATE USER n8n_user WITH PASSWORD 'n8n_password';
-- GRANT ALL PRIVILEGES ON DATABASE n8n TO n8n_user;

\echo 'Additional databases created successfully'
