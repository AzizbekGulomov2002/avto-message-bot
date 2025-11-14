-- User Payments table migration
CREATE TABLE IF NOT EXISTS user_payments (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    payed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deadline DATE NOT NULL,
    sum DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_user_payments_user_id ON user_payments(user_id);
CREATE INDEX IF NOT EXISTS idx_user_payments_deadline ON user_payments(deadline);
CREATE INDEX IF NOT EXISTS idx_user_payments_user_deadline ON user_payments(user_id, deadline);

