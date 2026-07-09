-- Announcements table
CREATE TABLE IF NOT EXISTS tblannouncement (
    idno            BIGSERIAL PRIMARY KEY,
    property_id     BIGINT NOT NULL REFERENCES tblproperty(idno),
    created_by      BIGINT NOT NULL REFERENCES tbluser(idno),
    title           VARCHAR(200) NOT NULL,
    body            TEXT NOT NULL,
    target          VARCHAR(20) DEFAULT 'all', -- all | resident
    target_room_id  BIGINT REFERENCES tblroom(idno),
    target_user_id  BIGINT REFERENCES tbluser(idno),
    send_email      BOOLEAN DEFAULT FALSE,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW() NOT NULL,
    expires_at      TIMESTAMP
);

-- Read receipts
CREATE TABLE IF NOT EXISTS tblannouncement_read (
    idno                BIGSERIAL PRIMARY KEY,
    announcement_id     BIGINT NOT NULL REFERENCES tblannouncement(idno),
    user_id             BIGINT NOT NULL REFERENCES tbluser(idno),
    read_at             TIMESTAMP DEFAULT NOW(),
    UNIQUE(announcement_id, user_id)
);

-- Invoices table
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
    status          VARCHAR(20) DEFAULT 'unpaid', -- unpaid | paid | cancelled
    paid_at         TIMESTAMP,
    paid_by         BIGINT REFERENCES tbluser(idno),
    note            TEXT,
    created_at      TIMESTAMP DEFAULT NOW() NOT NULL,
    created_by      BIGINT REFERENCES tbluser(idno)
);

-- Invite code reset log
ALTER TABLE tblroom ADD COLUMN IF NOT EXISTS invite_reset_at TIMESTAMP;

SELECT 'Announcements & invoices migration complete!' AS result;
