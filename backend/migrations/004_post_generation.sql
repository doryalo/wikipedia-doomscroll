ALTER TABLE posts ADD COLUMN enrichment_run_id INTEGER
    REFERENCES enrichment_runs(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX one_post_per_enrichment_run
    ON posts(enrichment_run_id) WHERE enrichment_run_id IS NOT NULL;
