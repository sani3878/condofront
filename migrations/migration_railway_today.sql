-- ============================================================
-- CondoFront Railway Migration — 09/07/2026
-- Covers: Phase 5 (Announcements, Invoices, Billing, Payments)
--         Multi-property, Admin improvements
-- Safe to run — uses IF NOT EXISTS / DO NOTHING
-- ============================================================

-- ── tblcustomer additions ───────────────────────────────────
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS customer_name   VARCHAR(150);
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS is_active       BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS mobile          VARCHAR(20);
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS created_at      TIMESTAMP DEFAULT NOW();
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS trial_ends_at   TIMESTAMP;
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS notes           TEXT;

-- Backfill customer_name from property if empty
UPDATE tblcustomer c
SET customer_name = (
    SELECT property_name FROM tblproperty p
    WHERE p.customer_id = c.idno LIMIT 1
)
WHERE customer_name IS NULL OR customer_name = '';

-- ── tblproperty additions ───────────────────────────────────
ALTER TABLE tblproperty ADD COLUMN IF NOT EXISTS customer_id   BIGINT REFERENCES tblcustomer(idno);
ALTER TABLE tblproperty ADD COLUMN IF NOT EXISTS property_code VARCHAR(20);

-- ── tbluser additions ───────────────────────────────────────
ALTER TABLE tbluser ADD COLUMN IF NOT EXISTS customer_id BIGINT REFERENCES tblcustomer(idno);

-- Backfill customer_id in tbluser from their property
UPDATE tbluser u
SET customer_id = (
    SELECT p.customer_id FROM tblproperty p
    WHERE p.idno = u.property_id LIMIT 1
)
WHERE u.customer_id IS NULL AND u.property_id IS NOT NULL;

-- Fix juristic registrants to role_id=1 (Manager) not role_id=2
UPDATE tbluser
SET role_id = 1
WHERE role_id = 2
AND customer_id IS NOT NULL
AND unit_id IS NULL;

-- ── tblpackage additions ────────────────────────────────────
ALTER TABLE tblpackage ADD COLUMN IF NOT EXISTS max_property INTEGER DEFAULT 1;

UPDATE tblpackage SET max_property = 1  WHERE package_name IN ('Free', 'Starter') AND max_property IS NULL;
UPDATE tblpackage SET max_property = 3  WHERE package_name = 'Pro'        AND max_property IS NULL;
UPDATE tblpackage SET max_property = 99 WHERE package_name = 'Enterprise' AND max_property IS NULL;

-- ── tblroom additions ───────────────────────────────────────
ALTER TABLE tblroom ADD COLUMN IF NOT EXISTS invite_reset_at TIMESTAMP;

-- ── tblsubscription additions ───────────────────────────────
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS plan_type  VARCHAR(10) DEFAULT 'monthly';
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS start_date DATE DEFAULT CURRENT_DATE;
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS end_date   DATE;
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS trial_ends DATE;
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS auto_renew BOOLEAN DEFAULT FALSE;

-- ── Announcements ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tblannouncement (
    idno            BIGSERIAL PRIMARY KEY,
    property_id     BIGINT NOT NULL REFERENCES tblproperty(idno),
    created_by      BIGINT NOT NULL REFERENCES tbluser(idno),
    title           VARCHAR(200) NOT NULL,
    body            TEXT NOT NULL,
    target          VARCHAR(20) DEFAULT 'all',
    target_room_id  BIGINT REFERENCES tblroom(idno),
    target_user_id  BIGINT REFERENCES tbluser(idno),
    send_email      BOOLEAN DEFAULT FALSE,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW() NOT NULL,
    expires_at      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tblannouncement_read (
    idno                BIGSERIAL PRIMARY KEY,
    announcement_id     BIGINT NOT NULL REFERENCES tblannouncement(idno),
    user_id             BIGINT NOT NULL REFERENCES tbluser(idno),
    read_at             TIMESTAMP DEFAULT NOW(),
    UNIQUE(announcement_id, user_id)
);

-- ── Invoices ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tblinvoice (
    idno            BIGSERIAL PRIMARY KEY,
    customer_id     BIGINT NOT NULL REFERENCES tblcustomer(idno),
    property_id     BIGINT REFERENCES tblproperty(idno),
    package_id      BIGINT REFERENCES tblpackage(idno),
    invoice_no      VARCHAR(20) UNIQUE NOT NULL,
    amount          NUMERIC(10,2) NOT NULL,
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    due_date        DATE NOT NULL,
    status          VARCHAR(20) DEFAULT 'unpaid',
    paid_at         TIMESTAMP,
    paid_by         BIGINT REFERENCES tbluser(idno),
    note            TEXT,
    payment_id      BIGINT,
    created_at      TIMESTAMP DEFAULT NOW() NOT NULL,
    created_by      BIGINT REFERENCES tbluser(idno)
);

-- ── Payments (slip uploads) ─────────────────────────────────
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

-- Add payment_id FK to invoices (after tblpayment exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='tblinvoice' AND column_name='payment_id'
    ) THEN
        ALTER TABLE tblinvoice ADD COLUMN payment_id BIGINT REFERENCES tblpayment(idno);
    END IF;
END $$;

-- ── Trial period for existing customers ─────────────────────
UPDATE tblcustomer
SET trial_ends_at = created_at + INTERVAL '30 days'
WHERE trial_ends_at IS NULL AND created_at IS NOT NULL;

-- ── Indexes ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_announcement_property ON tblannouncement(property_id, is_active);
CREATE INDEX IF NOT EXISTS idx_invoice_customer      ON tblinvoice(customer_id, status);

-- ============================================================
SELECT 'Railway migration complete! All Phase 5 tables ready.' AS result;

-- Add annual discount per package
ALTER TABLE tblpackage ADD COLUMN IF NOT EXISTS annual_discount NUMERIC(4,2) DEFAULT 10.00;

-- Set sensible defaults
UPDATE tblpackage SET annual_discount = 0   WHERE package_name = 'Free';
UPDATE tblpackage SET annual_discount = 10  WHERE package_name = 'Starter';
UPDATE tblpackage SET annual_discount = 10  WHERE package_name = 'Pro';
UPDATE tblpackage SET annual_discount = 15  WHERE package_name = 'Enterprise';
