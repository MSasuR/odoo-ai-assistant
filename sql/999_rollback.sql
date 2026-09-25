-- Reverts everything created by 001/002. Odoo's own tables are never touched.
DROP SCHEMA IF EXISTS ai CASCADE;
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'ai_readonly') THEN
        EXECUTE 'DROP OWNED BY ai_readonly';
        DROP ROLE ai_readonly;
    END IF;
END $$;
