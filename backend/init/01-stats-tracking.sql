CREATE ROLE postgres WITH LOGIN SUPERUSER PASSWORD 'password';
ALTER SYSTEM SET track_counts = on;
ALTER SYSTEM SET track_io_timing = on;
ALTER SYSTEM SET track_activities = on;
SELECT pg_reload_conf();
