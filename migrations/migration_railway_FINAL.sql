-- ============================================================
-- CondoFront Railway — COMPLETE MIGRATION
-- Covers ALL changes from Day 1 to v1.5
-- Safe to run even if some already exist (IF NOT EXISTS)
-- Run ONCE on Railway — covers everything
-- ============================================================

-- ── tblpackage ──────────────────────────────────────────────
ALTER TABLE tblpackage ADD COLUMN IF NOT EXISTS max_property    INTEGER       DEFAULT 1;
ALTER TABLE tblpackage ADD COLUMN IF NOT EXISTS max_user        INTEGER       DEFAULT 5;
ALTER TABLE tblpackage ADD COLUMN IF NOT EXISTS max_parcel      INTEGER       DEFAULT 1000;
ALTER TABLE tblpackage ADD COLUMN IF NOT EXISTS annual_discount NUMERIC(4,2)  DEFAULT 10.00;
ALTER TABLE tblpackage ADD COLUMN IF NOT EXISTS is_active       BOOLEAN       DEFAULT TRUE;

UPDATE tblpackage SET
    max_property = 1, annual_discount = 0
WHERE package_name = 'Free';

UPDATE tblpackage SET
    max_property = 1, annual_discount = 10
WHERE package_name = 'Starter';

UPDATE tblpackage SET
    max_property = 3, annual_discount = 10
WHERE package_name = 'Pro';

UPDATE tblpackage SET
    max_property = 99, annual_discount = 15
WHERE package_name = 'Enterprise';

-- ── tblcustomer ─────────────────────────────────────────────
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS customer_name  VARCHAR(150);
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS is_active      BOOLEAN       DEFAULT TRUE;
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS mobile         VARCHAR(20);
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS created_at     TIMESTAMP     DEFAULT NOW();
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS trial_ends_at  TIMESTAMP;
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS notes          TEXT;

-- Backfill customer_name from property
UPDATE tblcustomer c
SET customer_name = (
    SELECT property_name FROM tblproperty p
    WHERE p.customer_id = c.idno LIMIT 1
)
WHERE customer_name IS NULL OR customer_name = '';

-- ── tblproperty ─────────────────────────────────────────────
ALTER TABLE tblproperty ADD COLUMN IF NOT EXISTS customer_id    BIGINT REFERENCES tblcustomer(idno);
ALTER TABLE tblproperty ADD COLUMN IF NOT EXISTS property_code  VARCHAR(20);
ALTER TABLE tblproperty ADD COLUMN IF NOT EXISTS is_active      BOOLEAN DEFAULT TRUE;

-- ── tblrole (seed if empty) ─────────────────────────────────
INSERT INTO tblrole (idno, role_name) VALUES
    (1,'Manager'),(2,'Reception'),(3,'Security'),
    (4,'Resident'),(5,'SuperAdmin')
ON CONFLICT DO NOTHING;

-- ── tbluser ─────────────────────────────────────────────────
ALTER TABLE tbluser ADD COLUMN IF NOT EXISTS customer_id      BIGINT REFERENCES tblcustomer(idno);
ALTER TABLE tbluser ADD COLUMN IF NOT EXISTS email_verified   BOOLEAN   DEFAULT FALSE;
ALTER TABLE tbluser ADD COLUMN IF NOT EXISTS verify_token     VARCHAR(64);
ALTER TABLE tbluser ADD COLUMN IF NOT EXISTS verify_sent_at   TIMESTAMP;
ALTER TABLE tbluser ADD COLUMN IF NOT EXISTS reset_token      VARCHAR(64);
ALTER TABLE tbluser ADD COLUMN IF NOT EXISTS reset_sent_at    TIMESTAMP;
ALTER TABLE tbluser ADD COLUMN IF NOT EXISTS remember_token   VARCHAR(64);

-- Backfill customer_id
UPDATE tbluser u
SET customer_id = (
    SELECT p.customer_id FROM tblproperty p
    WHERE p.idno = u.property_id LIMIT 1
)
WHERE u.customer_id IS NULL AND u.property_id IS NOT NULL;

-- Fix juristic registrants to Manager role
UPDATE tbluser
SET role_id = 1
WHERE role_id = 2
AND customer_id IS NOT NULL
AND unit_id IS NULL;

-- ── tblroom ─────────────────────────────────────────────────
ALTER TABLE tblroom ADD COLUMN IF NOT EXISTS invite_code      VARCHAR(12);
ALTER TABLE tblroom ADD COLUMN IF NOT EXISTS invite_used      BOOLEAN   DEFAULT FALSE;
ALTER TABLE tblroom ADD COLUMN IF NOT EXISTS invite_reset_at  TIMESTAMP;
ALTER TABLE tblroom ADD COLUMN IF NOT EXISTS owner_email      VARCHAR(120);
ALTER TABLE tblroom ADD COLUMN IF NOT EXISTS owner_mobile     VARCHAR(20);

-- ── tblparcel ───────────────────────────────────────────────
ALTER TABLE tblparcel ADD COLUMN IF NOT EXISTS parcel_type    VARCHAR(30) DEFAULT 'box';
ALTER TABLE tblparcel ADD COLUMN IF NOT EXISTS pickup_code    VARCHAR(12);
ALTER TABLE tblparcel ADD COLUMN IF NOT EXISTS note           TEXT;
ALTER TABLE tblparcel ADD COLUMN IF NOT EXISTS updated_at     TIMESTAMP;
ALTER TABLE tblparcel ADD COLUMN IF NOT EXISTS deleted_at     TIMESTAMP;

-- ── tblpickup ───────────────────────────────────────────────
ALTER TABLE tblpickup ADD COLUMN IF NOT EXISTS pickup_method  VARCHAR(10) DEFAULT 'manual';
ALTER TABLE tblpickup ADD COLUMN IF NOT EXISTS pickup_note    TEXT;
ALTER TABLE tblpickup ADD COLUMN IF NOT EXISTS resident_id    BIGINT REFERENCES tbluser(idno);

-- ── tblvisitor ──────────────────────────────────────────────
ALTER TABLE tblvisitor ADD COLUMN IF NOT EXISTS visitor_code  VARCHAR(12);
ALTER TABLE tblvisitor ADD COLUMN IF NOT EXISTS visit_date    DATE;
ALTER TABLE tblvisitor ADD COLUMN IF NOT EXISTS registered_by BIGINT REFERENCES tbluser(idno);
ALTER TABLE tblvisitor ADD COLUMN IF NOT EXISTS logged_by     BIGINT REFERENCES tbluser(idno);
ALTER TABLE tblvisitor ADD COLUMN IF NOT EXISTS time_in       TIMESTAMP;
ALTER TABLE tblvisitor ADD COLUMN IF NOT EXISTS time_out      TIMESTAMP;
ALTER TABLE tblvisitor ADD COLUMN IF NOT EXISTS status        VARCHAR(20) DEFAULT 'pending';
ALTER TABLE tblvisitor ADD COLUMN IF NOT EXISTS note          TEXT;
ALTER TABLE tblvisitor ADD COLUMN IF NOT EXISTS id_card       VARCHAR(30);
ALTER TABLE tblvisitor ADD COLUMN IF NOT EXISTS purpose       VARCHAR(100);

-- ── tblsubscription ─────────────────────────────────────────
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS plan_type   VARCHAR(10) DEFAULT 'monthly';
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS start_date  DATE        DEFAULT CURRENT_DATE;
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS end_date    DATE;
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS trial_ends  DATE;
ALTER TABLE tblsubscription ADD COLUMN IF NOT EXISTS auto_renew  BOOLEAN     DEFAULT FALSE;

-- ── tblservice_category ─────────────────────────────────────
ALTER TABLE tblservice_category ADD COLUMN IF NOT EXISTS icon       VARCHAR(10) DEFAULT '🔧';
ALTER TABLE tblservice_category ADD COLUMN IF NOT EXISTS default_fee NUMERIC(10,2);
ALTER TABLE tblservice_category ADD COLUMN IF NOT EXISTS is_active  BOOLEAN DEFAULT TRUE;

-- ── tblservice_request ──────────────────────────────────────
ALTER TABLE tblservice_request ADD COLUMN IF NOT EXISTS assigned_to  BIGINT REFERENCES tbluser(idno);
ALTER TABLE tblservice_request ADD COLUMN IF NOT EXISTS closed_by    BIGINT REFERENCES tbluser(idno);
ALTER TABLE tblservice_request ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMP;
ALTER TABLE tblservice_request ADD COLUMN IF NOT EXISTS fee          NUMERIC(10,2);
ALTER TABLE tblservice_request ADD COLUMN IF NOT EXISTS fee_paid     BOOLEAN DEFAULT FALSE;
ALTER TABLE tblservice_request ADD COLUMN IF NOT EXISTS note         TEXT;
ALTER TABLE tblservice_request ADD COLUMN IF NOT EXISTS updated_at   TIMESTAMP DEFAULT NOW();
ALTER TABLE tblservice_request ADD COLUMN IF NOT EXISTS closed_at    TIMESTAMP;

-- ── tblfacility ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tblfacility (
    idno                BIGSERIAL PRIMARY KEY,
    property_id         BIGINT NOT NULL REFERENCES tblproperty(idno),
    name                VARCHAR(100) NOT NULL,
    name_en             VARCHAR(100),
    icon                VARCHAR(10) DEFAULT '🏢',
    is_active           BOOLEAN DEFAULT FALSE,
    booking_required    BOOLEAN DEFAULT TRUE,
    opening_time        TIME DEFAULT '06:00',
    closing_time        TIME DEFAULT '22:00',
    slot_duration_mins  INTEGER DEFAULT 60,
    max_capacity        INTEGER,
    approval_required   BOOLEAN DEFAULT FALSE,
    fee_amount          NUMERIC(10,2) DEFAULT 0,
    payment_method      VARCHAR(10) DEFAULT 'free',
    sort_order          INTEGER DEFAULT 0,
    note                TEXT
);

-- ── tblfacility_booking ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS tblfacility_booking (
    idno            BIGSERIAL PRIMARY KEY,
    facility_id     BIGINT NOT NULL REFERENCES tblfacility(idno),
    property_id     BIGINT NOT NULL REFERENCES tblproperty(idno),
    unit_id         BIGINT NOT NULL REFERENCES tblroom(idno),
    booked_by       BIGINT NOT NULL REFERENCES tbluser(idno),
    cancelled_by    BIGINT REFERENCES tbluser(idno),
    booking_date    DATE NOT NULL,
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    status          VARCHAR(20) DEFAULT 'confirmed',
    fee_amount      NUMERIC(10,2) DEFAULT 0,
    fee_paid        BOOLEAN DEFAULT FALSE,
    payment_method  VARCHAR(10) DEFAULT 'free',
    note            TEXT,
    cancelled_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ── tblannouncement ─────────────────────────────────────────
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
    created_at      TIMESTAMP DEFAULT NOW(),
    expires_at      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tblannouncement_read (
    idno                BIGSERIAL PRIMARY KEY,
    announcement_id     BIGINT NOT NULL REFERENCES tblannouncement(idno),
    user_id             BIGINT NOT NULL REFERENCES tbluser(idno),
    read_at             TIMESTAMP DEFAULT NOW(),
    UNIQUE(announcement_id, user_id)
);

-- ── tblinvoice ──────────────────────────────────────────────
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
    created_at      TIMESTAMP DEFAULT NOW(),
    created_by      BIGINT REFERENCES tbluser(idno)
);

-- ── tblpayment ──────────────────────────────────────────────
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
    submitted_at    TIMESTAMP DEFAULT NOW(),
    verified_at     TIMESTAMP,
    verified_by     BIGINT REFERENCES tbluser(idno),
    rejected_reason TEXT,
    note            TEXT
);

-- Add payment FK to invoice safely
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'tblinvoice'
        AND constraint_name = 'fk_invoice_payment'
    ) THEN
        ALTER TABLE tblinvoice
        ADD CONSTRAINT fk_invoice_payment
        FOREIGN KEY (payment_id) REFERENCES tblpayment(idno);
    END IF;
END $$;

-- ── Trial period backfill ────────────────────────────────────
UPDATE tblcustomer
SET trial_ends_at = created_at + INTERVAL '30 days'
WHERE trial_ends_at IS NULL AND created_at IS NOT NULL;

-- ── Indexes ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_parcel_property       ON tblparcel(property_id);
CREATE INDEX IF NOT EXISTS idx_parcel_room           ON tblparcel(room_id, status_id);
CREATE INDEX IF NOT EXISTS idx_parcel_code           ON tblparcel(pickup_code);
CREATE INDEX IF NOT EXISTS idx_visitor_property      ON tblvisitor(property_id, visit_date);
CREATE INDEX IF NOT EXISTS idx_visitor_code          ON tblvisitor(visitor_code);
CREATE INDEX IF NOT EXISTS idx_user_property         ON tbluser(property_id);
CREATE INDEX IF NOT EXISTS idx_user_unit             ON tbluser(unit_id);
CREATE INDEX IF NOT EXISTS idx_booking_facility      ON tblfacility_booking(facility_id, booking_date);
CREATE INDEX IF NOT EXISTS idx_booking_unit          ON tblfacility_booking(unit_id, booking_date);
CREATE INDEX IF NOT EXISTS idx_announcement_property ON tblannouncement(property_id, is_active);
CREATE INDEX IF NOT EXISTS idx_invoice_customer      ON tblinvoice(customer_id, status);
CREATE INDEX IF NOT EXISTS idx_payment_customer      ON tblpayment(customer_id, status);
CREATE INDEX IF NOT EXISTS idx_payment_status        ON tblpayment(status, submitted_at);

-- ============================================================
SELECT 'CondoFront COMPLETE migration done! v1.5 ready 🚀' AS result;

-- ── tblroom additional columns (may be missing on Railway) ──
ALTER TABLE tblroom ADD COLUMN IF NOT EXISTS owner_name   VARCHAR(100);
ALTER TABLE tblroom ADD COLUMN IF NOT EXISTS owner_email  VARCHAR(120);
ALTER TABLE tblroom ADD COLUMN IF NOT EXISTS owner_mobile VARCHAR(20);

-- ── Multi-unit resident support ──────────────────────────────
CREATE TABLE IF NOT EXISTS tblresident_unit (
    idno        BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES tbluser(idno),
    unit_id     BIGINT NOT NULL REFERENCES tblroom(idno),
    property_id BIGINT NOT NULL REFERENCES tblproperty(idno),
    is_primary  BOOLEAN DEFAULT FALSE,
    joined_at   TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, unit_id)
);

CREATE INDEX IF NOT EXISTS idx_resident_unit_user ON tblresident_unit(user_id);

-- Migrate existing residents into tblresident_unit
INSERT INTO tblresident_unit (user_id, unit_id, property_id, is_primary)
SELECT u.idno, u.unit_id, u.property_id, TRUE
FROM tbluser u
WHERE u.role_id = 4
AND u.unit_id IS NOT NULL
ON CONFLICT DO NOTHING;
