-- =========================================================
-- AI STUDENT SYSTEM - FINAL CALLING SUPPORT
-- Run this only if the tables do not already exist.
-- =========================================================

USE student_ai_system;

CREATE TABLE IF NOT EXISTS calling_queue (
    queue_id INT AUTO_INCREMENT PRIMARY KEY,
    college_id INT NOT NULL,
    teacher_id INT NOT NULL,
    student_id INT NOT NULL,
    parent_name VARCHAR(255) NULL,
    parent_mobile VARCHAR(50) NULL,
    attendance_date DATE NOT NULL,
    call_status VARCHAR(50) NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS call_history (
    call_id INT AUTO_INCREMENT PRIMARY KEY,
    college_id INT NULL,
    teacher_id INT NOT NULL,
    student_id INT NOT NULL,
    attendance_date DATE NULL,
    parent_name VARCHAR(255) NULL,
    parent_mobile VARCHAR(50) NULL,
    call_status VARCHAR(50) NOT NULL DEFAULT 'Pending',
    call_duration VARCHAR(50) NULL,
    parent_response TEXT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    call_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    remarks TEXT NULL
);
