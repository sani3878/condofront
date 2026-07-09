-- CondoFront Admin Migration
-- Run this on local machine to add missing columns
-- Safe to run — uses IF NOT EXISTS / DO NOTHING

-- Add customer_name and is_active to tblcustomer if missing
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS customer_name VARCHAR(150);
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS mobile VARCHAR(20);
ALTER TABLE tblcustomer ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();

-- Update customer_name from property if empty
UPDATE tblcustomer c
SET customer_name = (
    SELECT property_name FROM tblproperty p
    WHERE p.customer_id = c.idno LIMIT 1
)
WHERE customer_name IS NULL OR customer_name = '';

-- Add customer_id to tblproperty if missing
ALTER TABLE tblproperty ADD COLUMN IF NOT EXISTS customer_id BIGINT REFERENCES tblcustomer(idno);

-- Add customer_id to tbluser if missing  
ALTER TABLE tbluser ADD COLUMN IF NOT EXISTS customer_id BIGINT REFERENCES tblcustomer(idno);

-- Backfill customer_id in tbluser from property
UPDATE tbluser u
SET customer_id = (
    SELECT p.customer_id FROM tblproperty p
    WHERE p.idno = u.property_id LIMIT 1
)
WHERE u.customer_id IS NULL AND u.property_id IS NOT NULL;

SELECT 'Admin migration completed!' AS result;
