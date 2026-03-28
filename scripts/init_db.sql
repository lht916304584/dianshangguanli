-- Run once on first postgres container start
-- Alembic handles schema after this point

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- fast LIKE/ILIKE search

-- Optional: create a read-only reporting user
-- CREATE ROLE readonly_user LOGIN PASSWORD 'readonlypass';
-- GRANT CONNECT ON DATABASE appdb TO readonly_user;
-- GRANT USAGE ON SCHEMA public TO readonly_user;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;
