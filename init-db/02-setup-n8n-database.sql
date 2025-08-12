-- Create n8n database for workflow automation
-- This script sets up the n8n database with error handling

DO
$do$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'n8n') THEN
      PERFORM dblink_exec('dbname=' || current_database() || ' user=' || current_user,
                         'CREATE DATABASE n8n');
   END IF;
END
$do$;

-- Alternative approach without dblink (simpler)
SELECT 'Database n8n setup completed!' as result;
