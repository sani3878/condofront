-- ============================================================
-- CondoFront Phase 5 — Self-Serve Billing Migration
-- ============================================================

-- Add plan_type and dates to tblsubscription
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS plan_type  VARCHAR(10) DEFAULT 'monthly';
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS start_date DATE DEFAULT CURRENT_DATE;
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS end_date   DATE;
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS trial_ends DATE;
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS auto_renew BOOLEAN DEFAULT FALSE;

-- Add trial fields to tblcustomer
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS trial_ends_at  TIMESTAMP;
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS notes          TEXT;

-- Payment records (slip uploads)
CREATE TABLE IF NOT EXISTS tblpayment (
    idno            BIGSERIAL PRIMARY KEY,
    invoice_id      BIGINT REFERENCES tblinvoice(idno),
    customer_id     BIGINT NOT NULL REFERENCES tblcustomer(idno),
    package_id      BIGINT REFERENCES tblpackage(idno),
    plan_type       VARCHAR(10) DEFAULT 'monthly',
    amount          NUMERIC(10,2) NOT NULL,
    payment_method  VARCHAR(30) DEFAULT 'promptpay',
    slip_path       VARCHAR(500),
    status          VARCHAR(20) DEFAULT 'pending',
    submitted_at    TIMESTAMP DEFAULT NOW() NOT NULL,
    verified_at     TIMESTAMP,
    verified_by     BIGINT REFERENCES tbluser(idno),
    rejected_reason TEXT,
    note            TEXT
);

CREATE INDEX IF NOT EXISTS idx_payment_customer ON tblpayment(customer_id, status);
CREATE INDEX IF NOT EXISTS idx_payment_status   ON tblpayment(status, submitted_at);

-- Add upload path to invoices
ALTER TABLE tblinvoice ADD COLUMN IF NOT EXISTS payment_id BIGINT REFERENCES tblpayment(idno);

-- Set trial period for existing customers (30 days from registration)
UPDATE tblcustomer
SET trial_ends_at = created_at + INTERVAL '30 days'
WHERE trial_ends_at IS NULL AND created_at IS NOT NULL;

SELECT 'Phase 5 billing migration complete!' AS result;
