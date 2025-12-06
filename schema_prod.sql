-- =========================================================
-- Exam Registration System (ERS)
-- PRODUCTION SCHEMA + CORE REFERENCE DATA
-- =========================================================
-- This script creates the ERS schema and seeds core lookup data.
-- It is SAFE for production initialization on an empty database.
-- Do NOT use it to DROP tables on an existing production database.
-- For future changes, use migrations instead of rerunning this file.
-- =========================================================


-- ---------------------------------------------------------
-- TABLES
-- ---------------------------------------------------------

-- 1. Roles
CREATE TABLE IF NOT EXISTS roles (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Departments
CREATE TABLE IF NOT EXISTS departments (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Majors
CREATE TABLE IF NOT EXISTS majors (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    department_id INT NOT NULL,
    FOREIGN KEY (department_id) REFERENCES departments(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Users
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(150) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    phone         VARCHAR(20)  NOT NULL,
    nshe_id       VARCHAR(10),
    employee_id   VARCHAR(15),
    password_hash VARCHAR(255) NOT NULL,
    role_id       INT NOT NULL,
    department_id INT,
    major_id      INT NULL,
    status        ENUM('Active','Inactive') DEFAULT 'Active',
    FOREIGN KEY (role_id)       REFERENCES roles(id),
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (major_id)      REFERENCES majors(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. Professors
CREATE TABLE IF NOT EXISTS professors (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title   VARCHAR(50),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. Locations (Campus + Room)
CREATE TABLE IF NOT EXISTS locations (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,   -- Campus (North Las Vegas, etc.)
    room_number VARCHAR(50)  NOT NULL    -- Testing center room
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. Buildings (per campus)
CREATE TABLE IF NOT EXISTS buildings (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,   -- Building name (A, B, D, etc.)
    location_id INT NOT NULL,            -- Campus
    FOREIGN KEY (location_id) REFERENCES locations(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. Courses
CREATE TABLE IF NOT EXISTS courses (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    course_code   VARCHAR(20)  NOT NULL,
    course_name   VARCHAR(150) NOT NULL,
    department_id INT NOT NULL,
    FOREIGN KEY (department_id) REFERENCES departments(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 9. Timeslots
CREATE TABLE IF NOT EXISTS timeslots (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    start_time TIME NOT NULL,
    end_time   TIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 10. Exams
CREATE TABLE IF NOT EXISTS exams (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    exam_type    VARCHAR(255) NOT NULL,  -- "CS135 Midterm", "CS202 Final", etc.
    course_id    INT NOT NULL,
    exam_date    DATE NOT NULL,
    exam_time    TIME,
    location_id  INT NOT NULL,           -- Campus
    building_id  INT NOT NULL,           -- Building on that campus
    capacity     INT DEFAULT 20,
    professor_id INT,
    timeslot_id  INT,
    FOREIGN KEY (course_id)    REFERENCES courses(id),
    FOREIGN KEY (location_id)  REFERENCES locations(id),
    FOREIGN KEY (building_id)  REFERENCES buildings(id),
    FOREIGN KEY (professor_id) REFERENCES professors(id) ON DELETE SET NULL,
    FOREIGN KEY (timeslot_id)  REFERENCES timeslots(id)  ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 11. Registrations
CREATE TABLE IF NOT EXISTS registrations (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    registration_id   VARCHAR(10) UNIQUE,
    exam_id           INT NOT NULL,
    user_id           INT NOT NULL,
    timeslot_id       INT,
    location_id       INT,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status            ENUM('Active','Canceled') DEFAULT 'Active',
    UNIQUE(exam_id, user_id),
    FOREIGN KEY (exam_id) REFERENCES exams(id)  ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)  ON DELETE CASCADE
    -- (timeslot_id/location_id left without FK on purpose for flexibility)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 12. Exam_Locations (exam sessions per campus)
CREATE TABLE IF NOT EXISTS exam_locations (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    exam_id     INT NOT NULL,
    location_id INT NOT NULL,
    capacity    INT NOT NULL DEFAULT 20,
    UNIQUE KEY (exam_id, location_id),
    FOREIGN KEY (exam_id)     REFERENCES exams(id)     ON DELETE CASCADE,
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 13. Authentication (per professor spec)
CREATE TABLE IF NOT EXISTS authentication (
    auth_id       INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL UNIQUE,
    username      VARCHAR(150) NOT NULL,
    email         VARCHAR(150) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id       INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------
-- INDEXES
-- ---------------------------------------------------------
CREATE INDEX ix_exams_date_time   ON exams (exam_date, exam_time);
CREATE INDEX ix_reg_user_status   ON registrations (user_id, status);
CREATE INDEX ix_reg_exam_status   ON registrations (exam_id, status);
CREATE INDEX ix_reg_regid         ON registrations (registration_id);


-- =========================================================
-- TRIGGERS
-- =========================================================
DELIMITER $$

-- Registration ID generator: CSN001, CSN002, ...
DROP TRIGGER IF EXISTS id_generator$$
CREATE TRIGGER id_generator
BEFORE INSERT ON registrations
FOR EACH ROW
BEGIN
    DECLARE next_id INT;

    SELECT AUTO_INCREMENT INTO next_id
    FROM information_schema.tables
    WHERE table_name = 'registrations'
      AND table_schema = DATABASE();

    IF NEW.registration_id IS NULL OR NEW.registration_id = '' THEN
        SET NEW.registration_id = CONCAT('CSN', LPAD(next_id, 3, '0'));
    END IF;
END$$

-- Email format enforcement based on role
DROP TRIGGER IF EXISTS check_email_format$$
CREATE TRIGGER check_email_format
BEFORE INSERT ON users
FOR EACH ROW
BEGIN
    DECLARE role_name VARCHAR(50);

    -- Normalize email to lowercase
    SET NEW.email = LOWER(NEW.email);

    SELECT name INTO role_name
    FROM roles
    WHERE id = NEW.role_id;

    IF role_name IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid role: role_id not found.';
    END IF;

    SET role_name = LOWER(role_name);

    -- Students must use @student.csn.edu
    IF role_name = 'student'
       AND NEW.email NOT LIKE '%@student.csn.edu' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid email: Students must use @student.csn.edu';
    END IF;

    -- Faculty must use @csn.edu
    IF role_name = 'faculty'
       AND NEW.email NOT LIKE '%@csn.edu' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid email: Faculty must use @csn.edu';
    END IF;
END$$

DELIMITER ;


-- =========================================================
-- CORE REFERENCE SEED DATA (SAFE FOR PROD)
-- =========================================================

-- ROLES
INSERT INTO roles (name)
SELECT * FROM (
    SELECT 'faculty' UNION ALL
    SELECT 'student'
) AS r(name)
WHERE NOT EXISTS (SELECT 1 FROM roles);

-- DEPARTMENTS
INSERT INTO departments (name)
SELECT * FROM (
    SELECT 'Computer and Information Technology' UNION ALL
    SELECT 'Mathematics'                        UNION ALL
    SELECT 'Business Administration'            UNION ALL
    SELECT 'Health Sciences'                    UNION ALL
    SELECT 'Engineering Technology'
) AS d(name)
WHERE NOT EXISTS (SELECT 1 FROM departments);

-- MAJORS
INSERT INTO majors (name, department_id)
SELECT m.name, m.department_id FROM (
    SELECT 'Computer Science'        AS name, 1 AS department_id UNION ALL
    SELECT 'Information Systems'     AS name, 1 AS department_id UNION ALL
    SELECT 'Mathematics'             AS name, 2 AS department_id UNION ALL
    SELECT 'Business Management'     AS name, 3 AS department_id UNION ALL
    SELECT 'Nursing'                 AS name, 4 AS department_id UNION ALL
    SELECT 'Engineering' AS name, 5 AS department_id
) AS m
WHERE NOT EXISTS (SELECT 1 FROM majors);

-- COURSES
INSERT INTO courses (course_code, course_name, department_id)
SELECT c.course_code, c.course_name, c.department_id FROM (
    SELECT 'CS135'   AS course_code, 'Introduction to Programming'             AS course_name, 1 AS department_id UNION ALL
    SELECT 'CS202'   AS course_code, 'Computer Science I'                      AS course_name, 1 AS department_id UNION ALL
    SELECT 'CIT260'  AS course_code, 'Database Concepts and SQL'               AS course_name, 1 AS department_id UNION ALL
    SELECT 'MATH120' AS course_code, 'Fundamentals of College Mathematics'     AS course_name, 2 AS department_id UNION ALL
    SELECT 'BUS101'  AS course_code, 'Principles of Management'                AS course_name, 3 AS department_id UNION ALL
    SELECT 'NURS101' AS course_code, 'Foundations of Nursing Practice'         AS course_name, 4 AS department_id UNION ALL
    SELECT 'ET131'   AS course_code, 'Basic Electronics I'                     AS course_name, 5 AS department_id
) AS c
WHERE NOT EXISTS (SELECT 1 FROM courses);

-- LOCATIONS (Campuses)
INSERT INTO locations (name, room_number)
SELECT l.name, l.room_number FROM (
    SELECT 'North Las Vegas' AS name, 'B-100' AS room_number UNION ALL
    SELECT 'West Charleston' AS name, 'D-200' AS room_number UNION ALL
    SELECT 'Henderson'       AS name, 'A-300' AS room_number
) AS l
WHERE NOT EXISTS (SELECT 1 FROM locations);

-- BUILDINGS (one per campus for now)
INSERT INTO buildings (name, location_id)
SELECT b.name, b.location_id FROM (
    SELECT 'Building B' AS name,
           (SELECT id FROM locations WHERE name='North Las Vegas' LIMIT 1) AS location_id
    UNION ALL
    SELECT 'Building D' AS name,
           (SELECT id FROM locations WHERE name='West Charleston' LIMIT 1) AS location_id
    UNION ALL
    SELECT 'Building A' AS name,
           (SELECT id FROM locations WHERE name='Henderson' LIMIT 1) AS location_id
) AS b
WHERE NOT EXISTS (SELECT 1 FROM buildings);

-- TIMESLOTS (8:00–17:00, once)
INSERT INTO timeslots (start_time, end_time)
SELECT t.start_time, t.end_time
FROM (
  SELECT '08:00:00' AS start_time, '09:00:00' AS end_time UNION ALL
  SELECT '09:00:00', '10:00:00' UNION ALL
  SELECT '10:00:00', '11:00:00' UNION ALL
  SELECT '11:00:00', '12:00:00' UNION ALL
  SELECT '12:00:00', '13:00:00' UNION ALL
  SELECT '13:00:00', '14:00:00' UNION ALL
  SELECT '14:00:00', '15:00:00' UNION ALL
  SELECT '15:00:00', '16:00:00' UNION ALL
  SELECT '16:00:00', '17:00:00'
) AS t
WHERE NOT EXISTS (SELECT 1 FROM timeslots);
