USE student_ai_system;

-- Compatibility column: user-facing College ID is the numeric college_id.
ALTER TABLE colleges
ADD COLUMN IF NOT EXISTS college_login_id VARCHAR(20) NULL UNIQUE AFTER college_id;

-- Assign IDs to colleges that already exist.
UPDATE colleges
SET college_login_id = CAST(college_id AS CHAR)
WHERE college_login_id IS NULL OR TRIM(college_login_id) = '' OR college_login_id LIKE 'COL%';

-- Verify.
SELECT college_id, college_login_id, college_name, college_code, username
FROM colleges
ORDER BY college_id;
