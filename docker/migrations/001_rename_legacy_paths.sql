-- Rename legacy tracking tables if they still exist.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'db_paths') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = 'tdb_paths') THEN
            ALTER TABLE db_paths RENAME TO tdb_paths;
        ELSE
            DROP TABLE db_paths;
        END IF;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'vs_paths') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = 'vdb_paths') THEN
            ALTER TABLE vs_paths RENAME TO vdb_paths;
        ELSE
            DROP TABLE vs_paths;
        END IF;
    END IF;
END
$$;
