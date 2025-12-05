-- =========================================================
-- Exam Registration System (ERS)
-- Full schema + demo seed data
-- =========================================================

-- NOTE:
-- For production, you may want to REMOVE the DROP TABLE section
-- and run migrations instead of recreating tables.

CREATE DATABASE IF NOT EXISTS er_system;
USE er_system;

-- ---------------------------------------------------------
-- Drop existing tables (DEV/DEMO ONLY)
-- ---------------------------------------------------------
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS
  Registrations,
  Exam_Locations,
  Exams,
  Courses,
  Buildings,
  Locations,
  Professors,
  Authentication,
  Users,
  Majors,
  Departments,
  Roles,
  Timeslots;

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------
-- 1. Roles
-- ---------------------------------------------------------
CREATE TABLE Roles (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
-- 2. Departments
-- ---------------------------------------------------------
CREATE TABLE Departments (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
-- 3. Majors
-- ---------------------------------------------------------
CREATE TABLE Majors (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    department_id INT NOT NULL,
    FOREIGN KEY (department_id) REFERENCES Departments(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
-- 4. Users
-- ---------------------------------------------------------
CREATE TABLE Users (
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
    FOREIGN KEY (role_id)       REFERENCES Roles(id),
    FOREIGN KEY (department_id) REFERENCES Departments(id),
    FOREIGN KEY (major_id)      REFERENCES Majors(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
-- 5. Professors
-- ---------------------------------------------------------
CREATE TABLE Professors (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title   VARCHAR(50),
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
-- 6. Locations (Campus + Room)
-- ---------------------------------------------------------
CREATE TABLE Locations (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,   -- Campus (North Las Vegas, etc.)
    room_number VARCHAR(50)  NOT NULL    -- Testing center room
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
-- 7. Buildings (per campus)
-- ---------------------------------------------------------
CREATE TABLE Buildings (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,   -- Building name (A, B, D, etc.)
    location_id INT NOT NULL,            -- Campus
    FOREIGN KEY (location_id) REFERENCES Locations(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
-- 8. Courses
-- ---------------------------------------------------------
CREATE TABLE Courses (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    course_code   VARCHAR(20)  NOT NULL,
    course_name   VARCHAR(150) NOT NULL,
    department_id INT NOT NULL,
    FOREIGN KEY (department_id) REFERENCES Departments(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
-- 9. Timeslots
-- ---------------------------------------------------------
CREATE TABLE Timeslots (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    start_time TIME NOT NULL,
    end_time   TIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
-- 10. Exams
-- ---------------------------------------------------------
CREATE TABLE Exams (
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
    FOREIGN KEY (course_id)   REFERENCES Courses(id),
    FOREIGN KEY (location_id) REFERENCES Locations(id),
    FOREIGN KEY (building_id) REFERENCES Buildings(id),
    FOREIGN KEY (professor_id) REFERENCES Professors(id) ON DELETE SET NULL,
    FOREIGN KEY (timeslot_id)  REFERENCES Timeslots(id)  ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
-- 11. Registrations
-- ---------------------------------------------------------
CREATE TABLE Registrations (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    registration_id   VARCHAR(10) UNIQUE,
    exam_id           INT NOT NULL,
    user_id           INT NOT NULL,
    timeslot_id       INT,
    location_id       INT,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status            ENUM('Active','Canceled') DEFAULT 'Active',
    UNIQUE(exam_id, user_id),
    FOREIGN KEY (exam_id) REFERENCES Exams(id)  ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES Users(id)  ON DELETE CASCADE
    -- (timeslot_id/location_id left without FK on purpose for flexibility)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
-- 12. Exam_Locations (exam sessions per campus)
-- ---------------------------------------------------------
CREATE TABLE Exam_Locations (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    exam_id     INT NOT NULL,
    location_id INT NOT NULL,
    capacity    INT NOT NULL DEFAULT 20,
    UNIQUE KEY (exam_id, location_id),
    FOREIGN KEY (exam_id)     REFERENCES Exams(id)     ON DELETE CASCADE,
    FOREIGN KEY (location_id) REFERENCES Locations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
-- 13. Authentication (separate auth table, per professor spec)
-- ---------------------------------------------------------
CREATE TABLE Authentication (
    auth_id       INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL UNIQUE,
    username      VARCHAR(150) NOT NULL,
    email         VARCHAR(150) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id       INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES Roles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------
CREATE INDEX ix_exams_date_time   ON Exams (exam_date, exam_time);
CREATE INDEX ix_reg_user_status   ON Registrations (user_id, status);
CREATE INDEX ix_reg_exam_status   ON Registrations (exam_id, status);
CREATE INDEX ix_reg_regid         ON Registrations (registration_id);

-- =========================================================
-- TRIGGERS
-- =========================================================
DELIMITER $$

-- Registration ID generator: CSN001, CSN002, ...
DROP TRIGGER IF EXISTS id_generator$$
CREATE TRIGGER id_generator
BEFORE INSERT ON Registrations
FOR EACH ROW
BEGIN
    DECLARE next_id INT;

    SELECT AUTO_INCREMENT INTO next_id
    FROM information_schema.tables
    WHERE table_name = 'Registrations'
      AND table_schema = DATABASE();

    IF NEW.registration_id IS NULL OR NEW.registration_id = '' THEN
        SET NEW.registration_id = CONCAT('CSN', LPAD(next_id, 3, '0'));
    END IF;
END$$

-- Email format enforcement based on role
DROP TRIGGER IF EXISTS check_email_format$$
CREATE TRIGGER check_email_format
BEFORE INSERT ON Users
FOR EACH ROW
BEGIN
    DECLARE role_name VARCHAR(50);

    -- Normalize email to lowercase
    SET NEW.email = LOWER(NEW.email);

    SELECT name INTO role_name
    FROM Roles
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
-- SEED DATA (ROLES, DEPARTMENTS, MAJORS, COURSES, CAMPUS)
-- =========================================================

-- ROLES
INSERT INTO Roles (name) VALUES
('faculty'),
('student');

-- DEPARTMENTS
INSERT INTO Departments (name) VALUES
('Computer and Information Technology'),
('Mathematics'),
('Business Administration'),
('Health Sciences'),
('Engineering Technology');

-- MAJORS
INSERT INTO Majors (name, department_id) VALUES
('Computer Science',         1),
('Information Systems',      1),
('Mathematics',              2),
('Business Management',      3),
('Nursing',                  4),
('Electronics Engineering',  5);

-- COURSES
INSERT INTO Courses (course_code, course_name, department_id) VALUES
('CS135',   'Introduction to Programming',             1),
('CS202',   'Computer Science I',                      1),
('CIT260',  'Database Concepts and SQL',               1),
('MATH120', 'Fundamentals of College Mathematics',     2),
('BUS101',  'Principles of Management',                3),
('NURS101', 'Foundations of Nursing Practice',         4),
('ET131',   'Basic Electronics I',                     5);

-- LOCATIONS (Campuses)
INSERT INTO Locations (name, room_number) VALUES
('North Las Vegas', 'B-100'),
('West Charleston', 'D-200'),
('Henderson',       'A-300');

-- BUILDINGS (one per campus for now)
INSERT INTO Buildings (name, location_id) VALUES
('Building B', 1),  -- North Las Vegas
('Building D', 2),  -- West Charleston
('Building A', 3);  -- Henderson

-- =========================================================
-- SAMPLE USERS
-- =========================================================
-- Users table fields:
-- (name, email, phone, nshe_id, employee_id, password_hash,
--  role_id, department_id, major_id, status)

INSERT INTO Users
(name, email, phone, nshe_id, employee_id, password_hash,
 role_id, department_id, major_id, status)
VALUES
-- Faculty (role_id = 1, @csn.edu)
('Dr. Bart Simpson',
 'bart.simpson@csn.edu',
 '765-000-0000',
 NULL,
 'E123456',
 'x',              -- dummy hash to satisfy NOT NULL
 1,
 1,                -- CIT department
 1,                -- Computer Science
 'Active'),

-- Students (role_id = 2, @student.csn.edu)
('Velma Dinkley',
 'velma.dinkley@student.csn.edu',
 '123-456-7890',
 '2044992200',
 NULL,
 'x',
 2,
 1,                -- CIT
 2,                -- Information Systems
 'Active'),

('Patrick Star',
 'patrick.star@student.csn.edu',
 '908-765-5454',
 '2009991000',
 NULL,
 'x',
 2,
 3,                -- Business Admin
 4,                -- Business Management
 'Active');

-- PROFESSOR record linked to Bart
INSERT INTO Professors (user_id, title)
SELECT u.id, 'Professor'
FROM Users u
WHERE u.email = 'bart.simpson@csn.edu'
  AND NOT EXISTS (SELECT 1 FROM Professors p WHERE p.user_id = u.id);

-- =========================================================
-- TIMESLOTS (8:00–17:00)
-- =========================================================
INSERT INTO Timeslots (start_time, end_time)
SELECT * FROM (
  SELECT '08:00:00','09:00:00' UNION ALL
  SELECT '09:00:00','10:00:00' UNION ALL
  SELECT '10:00:00','11:00:00' UNION ALL
  SELECT '11:00:00','12:00:00' UNION ALL
  SELECT '12:00:00','13:00:00' UNION ALL
  SELECT '13:00:00','14:00:00' UNION ALL
  SELECT '14:00:00','15:00:00' UNION ALL
  SELECT '15:00:00','16:00:00' UNION ALL
  SELECT '16:00:00','17:00:00'
) AS t(start_time, end_time)
WHERE NOT EXISTS (SELECT 1 FROM Timeslots);

-- Cache professor id for seeding exams
SET @prof := (SELECT id FROM Professors LIMIT 1);

-- =========================================================
-- EXAMS: Midterm + Final for multiple courses across campuses
-- All dates are sample future term dates
-- =========================================================

-- CS135 (09:00)
INSERT INTO Exams (exam_type, course_id, exam_date, exam_time,
                   location_id, building_id, capacity, professor_id)
VALUES
('CS135 Midterm',
 (SELECT id FROM Courses WHERE course_code='CS135'),
 '2026-01-10','09:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('CS135 Midterm',
 (SELECT id FROM Courses WHERE course_code='CS135'),
 '2026-01-10','09:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('CS135 Midterm',
 (SELECT id FROM Courses WHERE course_code='CS135'),
 '2026-01-10','09:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof),

('CS135 Final',
 (SELECT id FROM Courses WHERE course_code='CS135'),
 '2026-01-24','09:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('CS135 Final',
 (SELECT id FROM Courses WHERE course_code='CS135'),
 '2026-01-24','09:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('CS135 Final',
 (SELECT id FROM Courses WHERE course_code='CS135'),
 '2026-01-24','09:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof);

-- CS202 (11:00)
INSERT INTO Exams (exam_type, course_id, exam_date, exam_time,
                   location_id, building_id, capacity, professor_id)
VALUES
('CS202 Midterm',
 (SELECT id FROM Courses WHERE course_code='CS202'),
 '2026-01-11','11:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('CS202 Midterm',
 (SELECT id FROM Courses WHERE course_code='CS202'),
 '2026-01-11','11:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('CS202 Midterm',
 (SELECT id FROM Courses WHERE course_code='CS202'),
 '2026-01-11','11:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof),

('CS202 Final',
 (SELECT id FROM Courses WHERE course_code='CS202'),
 '2026-01-25','11:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('CS202 Final',
 (SELECT id FROM Courses WHERE course_code='CS202'),
 '2026-01-25','11:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('CS202 Final',
 (SELECT id FROM Courses WHERE course_code='CS202'),
 '2026-01-25','11:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof);

-- CIT260 (13:00)
INSERT INTO Exams (exam_type, course_id, exam_date, exam_time,
                   location_id, building_id, capacity, professor_id)
VALUES
('CIT260 Midterm',
 (SELECT id FROM Courses WHERE course_code='CIT260'),
 '2026-01-12','13:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('CIT260 Midterm',
 (SELECT id FROM Courses WHERE course_code='CIT260'),
 '2026-01-12','13:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('CIT260 Midterm',
 (SELECT id FROM Courses WHERE course_code='CIT260'),
 '2026-01-12','13:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof),

('CIT260 Final',
 (SELECT id FROM Courses WHERE course_code='CIT260'),
 '2026-01-26','13:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('CIT260 Final',
 (SELECT id FROM Courses WHERE course_code='CIT260'),
 '2026-01-26','13:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('CIT260 Final',
 (SELECT id FROM Courses WHERE course_code='CIT260'),
 '2026-01-26','13:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof);

-- MATH120 (09:00)
INSERT INTO Exams (exam_type, course_id, exam_date, exam_time,
                   location_id, building_id, capacity, professor_id)
VALUES
('MATH120 Midterm',
 (SELECT id FROM Courses WHERE course_code='MATH120'),
 '2026-01-13','09:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('MATH120 Midterm',
 (SELECT id FROM Courses WHERE course_code='MATH120'),
 '2026-01-13','09:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('MATH120 Midterm',
 (SELECT id FROM Courses WHERE course_code='MATH120'),
 '2026-01-13','09:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof),

('MATH120 Final',
 (SELECT id FROM Courses WHERE course_code='MATH120'),
 '2026-01-27','09:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('MATH120 Final',
 (SELECT id FROM Courses WHERE course_code='MATH120'),
 '2026-01-27','09:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('MATH120 Final',
 (SELECT id FROM Courses WHERE course_code='MATH120'),
 '2026-01-27','09:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof);

-- BUS101 (11:00)
INSERT INTO Exams (exam_type, course_id, exam_date, exam_time,
                   location_id, building_id, capacity, professor_id)
VALUES
('BUS101 Midterm',
 (SELECT id FROM Courses WHERE course_code='BUS101'),
 '2026-01-14','11:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('BUS101 Midterm',
 (SELECT id FROM Courses WHERE course_code='BUS101'),
 '2026-01-14','11:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('BUS101 Midterm',
 (SELECT id FROM Courses WHERE course_code='BUS101'),
 '2026-01-14','11:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof),

('BUS101 Final',
 (SELECT id FROM Courses WHERE course_code='BUS101'),
 '2026-01-28','11:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('BUS101 Final',
 (SELECT id FROM Courses WHERE course_code='BUS101'),
 '2026-01-28','11:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('BUS101 Final',
 (SELECT id FROM Courses WHERE course_code='BUS101'),
 '2026-01-28','11:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof);

-- NURS101 (13:00)
INSERT INTO Exams (exam_type, course_id, exam_date, exam_time,
                   location_id, building_id, capacity, professor_id)
VALUES
('NURS101 Midterm',
 (SELECT id FROM Courses WHERE course_code='NURS101'),
 '2026-01-15','13:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('NURS101 Midterm',
 (SELECT id FROM Courses WHERE course_code='NURS101'),
 '2026-01-15','13:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('NURS101 Midterm',
 (SELECT id FROM Courses WHERE course_code='NURS101'),
 '2026-01-15','13:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof),

('NURS101 Final',
 (SELECT id FROM Courses WHERE course_code='NURS101'),
 '2026-01-29','13:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('NURS101 Final',
 (SELECT id FROM Courses WHERE course_code='NURS101'),
 '2026-01-29','13:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('NURS101 Final',
 (SELECT id FROM Courses WHERE course_code='NURS101'),
 '2026-01-29','13:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof);

-- ET131 (15:00)
INSERT INTO Exams (exam_type, course_id, exam_date, exam_time,
                   location_id, building_id, capacity, professor_id)
VALUES
('ET131 Midterm',
 (SELECT id FROM Courses WHERE course_code='ET131'),
 '2026-01-16','15:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('ET131 Midterm',
 (SELECT id FROM Courses WHERE course_code='ET131'),
 '2026-01-16','15:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('ET131 Midterm',
 (SELECT id FROM Courses WHERE course_code='ET131'),
 '2026-01-16','15:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof),

('ET131 Final',
 (SELECT id FROM Courses WHERE course_code='ET131'),
 '2026-01-30','15:00:00',
 (SELECT id FROM Locations WHERE name='North Las Vegas'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='North Las Vegas') LIMIT 1),
 20, @prof),
('ET131 Final',
 (SELECT id FROM Courses WHERE course_code='ET131'),
 '2026-01-30','15:00:00',
 (SELECT id FROM Locations WHERE name='West Charleston'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='West Charleston') LIMIT 1),
 20, @prof),
('ET131 Final',
 (SELECT id FROM Courses WHERE course_code='ET131'),
 '2026-01-30','15:00:00',
 (SELECT id FROM Locations WHERE name='Henderson'),
 (SELECT id FROM Buildings WHERE location_id =
     (SELECT id FROM Locations WHERE name='Henderson') LIMIT 1),
 20, @prof);

-- =========================================================
-- EXAM_LOCATIONS (one per exam/location pair)
-- =========================================================
INSERT INTO Exam_Locations (exam_id, location_id, capacity)
SELECT e.id, e.location_id, e.capacity
FROM Exams e
LEFT JOIN Exam_Locations el
  ON el.exam_id = e.id AND el.location_id = e.location_id
WHERE el.id IS NULL;

-- =========================================================
-- SAMPLE REGISTRATIONS (OPTIONAL)
-- =========================================================
INSERT INTO Registrations (registration_id, exam_id, user_id, status)
VALUES
('CSN001',
 (SELECT MIN(id) FROM Exams WHERE exam_type='CS135 Midterm'),
 (SELECT id FROM Users WHERE email='velma.dinkley@student.csn.edu'),
 'Active'),
('CSN002',
 (SELECT MIN(id) FROM Exams WHERE exam_type='CS202 Final'),
 (SELECT id FROM Users WHERE email='patrick.star@student.csn.edu'),
 'Active');
