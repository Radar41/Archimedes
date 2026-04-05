-- Create the Langfuse database so it does not share the application schema.
-- This script runs once via the postgres docker-entrypoint-initdb.d mechanism.
CREATE DATABASE langfuse_dev OWNER archimedes;
