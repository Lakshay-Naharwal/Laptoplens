-- Price history table — append-only, never overwrite
CREATE TABLE IF NOT EXISTS price_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  TEXT    NOT NULL,          -- stable hash of product name + source
    product_name TEXT   NOT NULL,
    source      TEXT    NOT NULL,          -- 'flipkart' | 'amazon' | 'mock'
    price       REAL    NOT NULL,          -- INR
    scraped_at  DATETIME DEFAULT (datetime('now', 'localtime'))
);

-- Fast lookups by product over time
CREATE INDEX IF NOT EXISTS idx_product_time
    ON price_history (product_id, scraped_at);

-- Metadata table for product details (image, link, specs)
CREATE TABLE IF NOT EXISTS products (
    product_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    image_url    TEXT,
    buy_url      TEXT,
    source       TEXT,
    specs_json   TEXT,                    -- JSON blob of raw specs
    first_seen   DATETIME DEFAULT (datetime('now', 'localtime')),
    last_updated DATETIME DEFAULT (datetime('now', 'localtime'))
);
