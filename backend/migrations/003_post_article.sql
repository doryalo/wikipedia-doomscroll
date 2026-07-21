ALTER TABLE posts ADD COLUMN article_id TEXT REFERENCES articles(id) ON DELETE SET NULL;

CREATE INDEX idx_posts_article_id ON posts(article_id);

UPDATE posts
SET article_id = (
    SELECT articles.id
    FROM articles
    WHERE articles.url = posts.source_url
    LIMIT 1
)
WHERE article_id IS NULL AND source_url IS NOT NULL;
