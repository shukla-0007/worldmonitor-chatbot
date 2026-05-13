-- DuckDB schema for knowledge base

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id     VARCHAR PRIMARY KEY,
    file_path    VARCHAR NOT NULL,
    module       VARCHAR NOT NULL,
    language     VARCHAR NOT NULL,
    chunk_index  INTEGER NOT NULL,
    content      TEXT    NOT NULL,
    tags         VARCHAR NOT NULL,
    char_count   INTEGER NOT NULL,
    embedding    FLOAT[768]
);

-- HNSW vector index (created after embeddings are inserted)
-- Requires DuckDB VSS extension:
-- INSTALL vss;
-- LOAD vss;
--
-- CREATE INDEX embedding_idx
-- ON chunks
-- USING HNSW (embedding)
-- WITH (metric = 'cosine');
