-- Fixed catalog-only queries for an explicitly approved PostgreSQL test DB.
-- Run in a READ ONLY transaction. No DDL, DML, row data, or credentials.
BEGIN TRANSACTION READ ONLY;

SELECT current_database() AS database_name,
       current_user AS current_user,
       current_setting('server_version') AS server_version,
       current_setting('transaction_read_only') AS transaction_read_only,
       role.rolsuper AS is_superuser,
       role.rolbypassrls AS bypasses_rls
FROM pg_roles AS role
WHERE role.rolname = current_user;

SELECT n.nspname AS schema_name,
       c.relname AS table_name,
       c.relrowsecurity AS rls_enabled,
       c.relforcerowsecurity AS force_rls,
       pg_get_userbyid(c.relowner) AS owner_name
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
ORDER BY c.relname;

SELECT schemaname, tablename, policyname, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';

SELECT to_regclass('public.alembic_version') IS NOT NULL AS alembic_table_exists;

SELECT table_name, privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public' AND grantee = current_user
ORDER BY table_name, privilege_type;

ROLLBACK;
