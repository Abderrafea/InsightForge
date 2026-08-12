CREATE ROLE dashboard_reader LOGIN PASSWORD 'dashboard_reader_dev';

CREATE TABLE customers (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(320) NOT NULL UNIQUE,
    country VARCHAR(2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(180) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customers(id),
    total_amount NUMERIC(12, 2) NOT NULL CHECK (total_amount >= 0),
    status VARCHAR(30) NOT NULL CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0)
);

CREATE INDEX ix_customers_country ON customers(country);
CREATE INDEX ix_products_category ON products(category);
CREATE INDEX ix_orders_customer_id ON orders(customer_id);
CREATE INDEX ix_orders_created_at ON orders(created_at);
CREATE INDEX ix_orders_status ON orders(status);
CREATE INDEX ix_order_items_order_id ON order_items(order_id);
CREATE INDEX ix_order_items_product_id ON order_items(product_id);

INSERT INTO customers (name, email, country, created_at)
SELECT
    'Customer ' || customer_number,
    'customer' || customer_number || '@example.com',
    (ARRAY['MA', 'FR', 'ES', 'US', 'GB'])[1 + ((customer_number - 1) % 5)],
    now() - ((customer_number * 7) || ' days')::interval
FROM generate_series(1, 30) AS customer_number;

INSERT INTO products (name, category, price, created_at) VALUES
    ('Analytics Starter', 'Software', 49.00, now() - interval '180 days'),
    ('Analytics Pro', 'Software', 129.00, now() - interval '175 days'),
    ('Data Connector', 'Software', 79.00, now() - interval '160 days'),
    ('Team Workspace', 'Software', 199.00, now() - interval '150 days'),
    ('Mechanical Keyboard', 'Hardware', 110.00, now() - interval '140 days'),
    ('Ultrawide Monitor', 'Hardware', 520.00, now() - interval '130 days'),
    ('USB-C Dock', 'Hardware', 145.00, now() - interval '125 days'),
    ('Webcam', 'Hardware', 95.00, now() - interval '120 days'),
    ('SQL Fundamentals', 'Education', 39.00, now() - interval '110 days'),
    ('Dashboard Design', 'Education', 59.00, now() - interval '105 days'),
    ('Data Strategy Workshop', 'Services', 900.00, now() - interval '100 days'),
    ('Implementation Package', 'Services', 1500.00, now() - interval '90 days');

INSERT INTO orders (customer_id, total_amount, status, created_at)
SELECT
    1 + ((order_number * 7) % 30),
    (45 + ((order_number * 83) % 1500))::numeric(12, 2),
    (ARRAY['paid', 'shipped', 'paid', 'pending', 'shipped', 'cancelled'])[1 + ((order_number - 1) % 6)],
    now() - ((order_number * 2) || ' days')::interval
FROM generate_series(1, 90) AS order_number;

INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT
    order_record.id,
    1 + ((order_record.id * item_number * 5) % 12),
    1 + ((order_record.id + item_number) % 4),
    product_record.price
FROM orders AS order_record
CROSS JOIN generate_series(1, 1 + (order_record.id % 3)) AS item_number
JOIN products AS product_record
  ON product_record.id = 1 + ((order_record.id * item_number * 5) % 12);

GRANT CONNECT ON DATABASE demo_ecommerce TO dashboard_reader;
GRANT USAGE ON SCHEMA public TO dashboard_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO dashboard_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO dashboard_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO dashboard_reader;

REVOKE CREATE ON SCHEMA public FROM dashboard_reader;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
ON ALL TABLES IN SCHEMA public FROM dashboard_reader;
