-- ============================================================
-- CondoFront v1.2 — Complete Database Schema
-- Generated: 2026-07-08
-- Stack: PostgreSQL
-- ============================================================

-- ── SEQUENCES ───────────────────────────────────────────────
-- All tables use BIGSERIAL which auto-creates sequences

-- ── 1. PACKAGES ─────────────────────────────────────────────
CREATE TABLE tblpackage (
    idno            BIGSERIAL PRIMARY KEY,
    package_name    VARCHAR(50) NOT NULL,
    monthly_fee     NUMERIC(10,2) DEFAULT 0,
    max_room        INTEGER DEFAULT 10,
    max_user        INTEGER DEFAULT 2,
    max_parcel      INTEGER DEFAULT 100,
    is_active       BOOLEAN DEFAULT TRUE NOT NULL
);

-- ── 2. CUSTOMERS ────────────────────────────────────────────
CREATE TABLE tblcustomer (
    idno            BIGSERIAL PRIMARY KEY,
    email           VARCHAR(120) UNIQUE NOT NULL,
    package_id      BIGINT REFERENCES tblpackage(idno),
    is_approved     BOOLEAN DEFAULT FALSE NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ── 3. PROPERTIES ───────────────────────────────────────────
CREATE TABLE tblproperty (
    idno            BIGSERIAL PRIMARY KEY,
    property_name   VARCHAR(150) NOT NULL,
    address         TEXT,
    phone           VARCHAR(20),
    email           VARCHAR(120),
    logo_path       VARCHAR(255),
    is_active       BOOLEAN DEFAULT TRUE NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ── 4. ROLES ────────────────────────────────────────────────
CREATE TABLE tblrole (
    idno            BIGSERIAL PRIMARY KEY,
    role_name       VARCHAR(50) NOT NULL
);

-- ── 5. ROOMS ────────────────────────────────────────────────
CREATE TABLE tblroom (
    idno            BIGSERIAL PRIMARY KEY,
    property_id     BIGINT NOT NULL REFERENCES tblproperty(idno),
    building        VARCHAR(10),
    room_no         VARCHAR(20) NOT NULL,
    floor           INTEGER,
    room_type       VARCHAR(30),
    owner_name      VARCHAR(100),
    owner_mobile    VARCHAR(20),
    owner_email     VARCHAR(120),
    is_active       BOOLEAN DEFAULT TRUE NOT NULL,
    invite_code     VARCHAR(12) UNIQUE,
    invite_used     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_room_property ON tblroom(property_id);

-- ── 6. USERS ────────────────────────────────────────────────
CREATE TABLE tbluser (
    idno            BIGSERIAL PRIMARY KEY,
    property_id     BIGINT REFERENCES tblproperty(idno),
    unit_id         BIGINT REFERENCES tblroom(idno),
    role_id         BIGINT NOT NULL REFERENCES tblrole(idno),
    fullname        VARCHAR(100) NOT NULL,
    email           VARCHAR(120) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    mobile          VARCHAR(20),
    is_active       BOOLEAN DEFAULT TRUE NOT NULL,
    email_verified  BOOLEAN DEFAULT FALSE NOT NULL,
    verify_token    VARCHAR(64),
    verify_sent_at  TIMESTAMP,
    reset_token     VARCHAR(64),
    reset_sent_at   TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_property ON tbluser(property_id);
CREATE INDEX idx_user_unit     ON tbluser(unit_id);
CREATE INDEX idx_user_email    ON tbluser(email);

-- ── 7. SUBSCRIPTIONS ────────────────────────────────────────
CREATE TABLE tblsubscription (
    idno            BIGSERIAL PRIMARY KEY,
    property_id     BIGINT NOT NULL REFERENCES tblproperty(idno),
    package_id      BIGINT NOT NULL REFERENCES tblpackage(idno),
    start_date      DATE DEFAULT CURRENT_DATE,
    end_date        DATE,
    is_active       BOOLEAN DEFAULT TRUE NOT NULL
);

-- ── 8. COURIERS ─────────────────────────────────────────────
CREATE TABLE tblcourier (
    idno            BIGSERIAL PRIMARY KEY,
    courier_name    VARCHAR(80) NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE NOT NULL
);

-- ── 9. STATUS ───────────────────────────────────────────────
CREATE TABLE tblstatus (
    idno            BIGSERIAL PRIMARY KEY,
    status_name     VARCHAR(50) NOT NULL
);

-- ── 10. PARCELS ─────────────────────────────────────────────
CREATE TABLE tblparcel (
    idno            BIGSERIAL PRIMARY KEY,
    property_id     BIGINT NOT NULL REFERENCES tblproperty(idno),
    room_id         BIGINT NOT NULL REFERENCES tblroom(idno),
    courier_id      BIGINT REFERENCES tblcourier(idno),
    received_by     BIGINT REFERENCES tbluser(idno),
    updated_by      BIGINT REFERENCES tbluser(idno),
    pickup_id       BIGINT,
    tracking_no     VARCHAR(100),
    parcel_type     VARCHAR(30) DEFAULT 'box',
    pickup_code     VARCHAR(12) UNIQUE,
    note            TEXT,
    status_id       INTEGER DEFAULT 0 NOT NULL,
    received_at     TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at      TIMESTAMP,
    deleted_at      TIMESTAMP
);

CREATE INDEX idx_parcel_property ON tblparcel(property_id);
CREATE INDEX idx_parcel_room     ON tblparcel(room_id, status_id);
CREATE INDEX idx_parcel_code     ON tblparcel(pickup_code);

-- ── 11. PICKUPS ─────────────────────────────────────────────
CREATE TABLE tblpickup (
    idno            BIGSERIAL PRIMARY KEY,
    property_id     BIGINT NOT NULL REFERENCES tblproperty(idno),
    room_id         BIGINT NOT NULL REFERENCES tblroom(idno),
    parcel_id       BIGINT REFERENCES tblparcel(idno),
    resident_id     BIGINT REFERENCES tbluser(idno),
    handled_by      BIGINT REFERENCES tbluser(idno),
    signature_path  TEXT,
    pickup_note     TEXT,
    pickup_method   VARCHAR(10) DEFAULT 'manual',
    pickup_at       TIMESTAMP DEFAULT NOW() NOT NULL
);

-- ── 12. VISITORS ────────────────────────────────────────────
CREATE TABLE tblvisitor (
    idno            BIGSERIAL PRIMARY KEY,
    property_id     BIGINT NOT NULL REFERENCES tblproperty(idno),
    room_id         BIGINT REFERENCES tblroom(idno),
    registered_by   BIGINT REFERENCES tbluser(idno),
    logged_by       BIGINT REFERENCES tbluser(idno),
    visitor_name    VARCHAR(100) NOT NULL,
    id_card         VARCHAR(30),
    purpose         VARCHAR(100),
    visitor_code    VARCHAR(12) UNIQUE,
    visit_date      DATE,
    time_in         TIMESTAMP,
    time_out        TIMESTAMP,
    status          VARCHAR(20) DEFAULT 'pending',
    note            TEXT
);

CREATE INDEX idx_visitor_property ON tblvisitor(property_id, visit_date);
CREATE INDEX idx_visitor_code     ON tblvisitor(visitor_code);

-- ── 13. SERVICE CATEGORIES ──────────────────────────────────
CREATE TABLE tblservice_category (
    idno            BIGSERIAL PRIMARY KEY,
    property_id     BIGINT NOT NULL REFERENCES tblproperty(idno),
    name            VARCHAR(100) NOT NULL,
    icon            VARCHAR(10) DEFAULT '🔧',
    default_fee     NUMERIC(10,2),
    is_active       BOOLEAN DEFAULT TRUE NOT NULL
);

-- ── 14. SERVICE REQUESTS ────────────────────────────────────
CREATE TABLE tblservice_request (
    idno            BIGSERIAL PRIMARY KEY,
    property_id     BIGINT NOT NULL REFERENCES tblproperty(idno),
    room_id         BIGINT REFERENCES tblroom(idno),
    category_id     BIGINT REFERENCES tblservice_category(idno),
    submitted_by    BIGINT REFERENCES tbluser(idno),
    assigned_to     BIGINT REFERENCES tbluser(idno),
    closed_by       BIGINT REFERENCES tbluser(idno),
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    status          VARCHAR(20) DEFAULT 'open' NOT NULL,
    scheduled_at    TIMESTAMP,
    fee             NUMERIC(10,2),
    fee_paid        BOOLEAN DEFAULT FALSE,
    note            TEXT,
    created_at      TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at      TIMESTAMP DEFAULT NOW(),
    closed_at       TIMESTAMP
);

CREATE INDEX idx_service_property ON tblservice_request(property_id, status);

-- ── 15. FACILITIES ──────────────────────────────────────────
CREATE TABLE tblfacility (
    idno                BIGSERIAL PRIMARY KEY,
    property_id         BIGINT NOT NULL REFERENCES tblproperty(idno),
    name                VARCHAR(100) NOT NULL,
    name_en             VARCHAR(100),
    icon                VARCHAR(10) DEFAULT '🏢',
    is_active           BOOLEAN DEFAULT FALSE NOT NULL,
    booking_required    BOOLEAN DEFAULT TRUE NOT NULL,
    opening_time        TIME DEFAULT '06:00',
    closing_time        TIME DEFAULT '22:00',
    slot_duration_mins  INTEGER DEFAULT 60,
    max_capacity        INTEGER,
    approval_required   BOOLEAN DEFAULT FALSE NOT NULL,
    fee_amount          NUMERIC(10,2) DEFAULT 0,
    payment_method      VARCHAR(10) DEFAULT 'free',
    sort_order          INTEGER DEFAULT 0,
    note                TEXT
);

CREATE INDEX idx_facility_property ON tblfacility(property_id, is_active);

-- ── 16. FACILITY BOOKINGS ───────────────────────────────────
CREATE TABLE tblfacility_booking (
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
    created_at      TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_booking_facility ON tblfacility_booking(facility_id, booking_date, status);
CREATE INDEX idx_booking_unit     ON tblfacility_booking(unit_id, booking_date);

-- ============================================================
-- SEED DATA
-- ============================================================

-- Roles
INSERT INTO tblrole (idno, role_name) VALUES
(1, 'Manager'),
(2, 'Reception'),
(3, 'Security'),
(4, 'Resident'),
(5, 'SuperAdmin');

-- Parcel statuses
INSERT INTO tblstatus (idno, status_name) VALUES
(0, 'Waiting'),
(1, 'Picked Up'),
(2, 'Returned');

-- Packages
INSERT INTO tblpackage (package_name, monthly_fee, max_room, max_user, max_parcel, is_active) VALUES
('Free',       0,    10,  2,  100,  true),
('Starter',    299,  50,  5,  1000, true),
('Pro',        599,  100, 10, 5000, true),
('Enterprise', 0,    999, 99, 9999, true);

-- Default couriers
INSERT INTO tblcourier (courier_name, is_active) VALUES
('ไปรษณีย์ไทย',    true),
('Kerry Express',  true),
('Flash Express',  true),
('J&T Express',    true),
('Ninja Van',      true),
('DHL',            true),
('FedEx',          true),
('Lazada Logistics', true),
('Shopee Express', true),
('Best Express',   true);

-- ============================================================
-- FOREIGN KEY BACKFILL (parcel → pickup)
-- ============================================================
ALTER TABLE tblparcel ADD CONSTRAINT fk_parcel_pickup
    FOREIGN KEY (pickup_id) REFERENCES tblpickup(idno)
    DEFERRABLE INITIALLY DEFERRED;

-- ============================================================
-- DONE
-- ============================================================
SELECT 'CondoFront v1.2 schema created successfully!' AS result;
