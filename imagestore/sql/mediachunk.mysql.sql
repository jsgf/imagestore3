ALTER TABLE imagestore_mediachunk AVG_ROW_LENGTH = 65536, MAX_ROWS=1000000;
ALTER TABLE imagestore_mediachunk MODIFY COLUMN data LONGBLOB NOT NULL;
