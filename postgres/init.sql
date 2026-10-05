-- Run by python -m app.database AFTER SQLAlchemy creates the tables.
-- Repeating initialization preserves existing products and orders.
INSERT INTO products (id, name, price_cents, currency)
VALUES
    (1, 'ShopSphere T-shirt', 2499, 'USD'),
    (2, 'ShopSphere Backpack', 4999, 'USD'),
    (3, 'ShopSphere Mug', 1299, 'USD')
ON CONFLICT (id) DO NOTHING;
