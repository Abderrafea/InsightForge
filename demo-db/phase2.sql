CREATE TABLE IF NOT EXISTS payments (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    payment_method VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
    paid_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_payments_order_id ON payments(order_id);
CREATE INDEX IF NOT EXISTS ix_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS ix_payments_paid_at ON payments(paid_at);

INSERT INTO payments (order_id, amount, payment_method, status, paid_at)
SELECT
    order_record.id,
    order_record.total_amount,
    (ARRAY['card', 'bank_transfer', 'wallet'])[1 + ((order_record.id - 1) % 3)],
    CASE
        WHEN order_record.status = 'cancelled' THEN 'refunded'
        WHEN order_record.status = 'pending' THEN 'pending'
        ELSE 'completed'
    END,
    CASE
        WHEN order_record.status = 'pending' THEN NULL
        ELSE order_record.created_at + interval '1 hour'
    END
FROM orders AS order_record
WHERE NOT EXISTS (
    SELECT 1
    FROM payments AS existing_payment
    WHERE existing_payment.order_id = order_record.id
);

GRANT SELECT ON payments TO dashboard_reader;
GRANT SELECT ON SEQUENCE payments_id_seq TO dashboard_reader;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
ON payments FROM dashboard_reader;
