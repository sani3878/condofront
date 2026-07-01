ALTER TABLE tblcustomer ADD COLUMN package_id BIGINT REFERENCES tblpackage(idno);
ALTER TABLE tbluser ADD COLUMN email_verified BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE tbluser ADD COLUMN verify_token VARCHAR(64);
ALTER TABLE tbluser ADD COLUMN verify_sent_at TIMESTAMP;
UPDATE tbluser SET email_verified = TRUE WHERE email_verified = FALSE;