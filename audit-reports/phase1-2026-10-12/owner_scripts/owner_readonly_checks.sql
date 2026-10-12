-- READ-ONLY checks of the production database, to be run by the OWNER (never by an assistant).
-- Every statement is a SELECT. The wrapper run_owner_readonly_checks.ps1 also forces default_transaction_read_only=on, so a write would be refused by the server.
-- No column holding a secret is selected (jwt_signing_keys.secret is NOT read: counts and dates only).
\echo === 1. Alembic revision actually applied
SELECT version_num FROM alembic_version;

\echo === 2. Role used by this connection and whether it bypasses row level security
SELECT current_user AS connection_role, rolsuper, rolbypassrls, rolcanlogin, rolcreatedb, rolcreaterole
FROM pg_roles WHERE rolname = current_user;

\echo === 3. Row level security: tables, policies
SELECT count(*) AS public_tables FROM pg_tables WHERE schemaname = 'public';
SELECT count(*) AS public_tables_without_rls FROM pg_tables WHERE schemaname = 'public' AND NOT rowsecurity;
SELECT count(*) AS public_policies FROM pg_policies WHERE schemaname = 'public';
SELECT count(*) AS tables_with_force_rls FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relforcerowsecurity;

\echo === 4. Table owners (who owns the application tables)
SELECT tableowner, count(*) AS tables FROM pg_tables WHERE schemaname = 'public' GROUP BY tableowner ORDER BY tables DESC;

\echo === 5. Privileges granted to the Supabase API roles on the public schema
SELECT grantee, count(DISTINCT table_name) AS tables_granted
FROM information_schema.role_table_grants
WHERE table_schema = 'public' AND grantee IN ('anon', 'authenticated')
GROUP BY grantee;

\echo === 6. Signing keys: counts and dates only (no secret column)
SELECT count(*) AS rows, min(created_at) AS oldest, max(created_at) AS newest, count(*) FILTER (WHERE is_active) AS active
FROM jwt_signing_keys;

\echo === 7. Test pollution (see docs/FINAL_STATUS.md of 2026-10-06: 1523 of 1576 organizations named test)
SELECT count(*) AS organizations, count(*) FILTER (WHERE name = 'test') AS named_test, min(created_at) AS oldest, max(created_at) AS newest FROM organizations;
SELECT count(*) AS users, count(*) FILTER (WHERE email LIKE '%@example.com') AS example_com FROM users;

\echo === 8. Extensions and server version
SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector') ORDER BY 1;
SELECT version();
