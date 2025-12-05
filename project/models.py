from flask_login import UserMixin
from project import db


# ----------------------------
# Role
# ----------------------------
class Role(db.Model):
    __tablename__ = 'Roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    users = db.relationship("User", backref="role", lazy=True)


# ----------------------------
# Department
# ----------------------------
class Department(db.Model):
    __tablename__ = 'Departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


# ----------------------------
# Major
# ----------------------------
class Major(db.Model):
    __tablename__ = 'Majors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    department_id = db.Column(db.Integer, db.ForeignKey('Departments.id'), nullable=False)
    department = db.relationship("Department", backref="majors", lazy=True)


# ----------------------------
# User (Authentication + Domain User)
# ----------------------------
class User(db.Model, UserMixin):
    __tablename__ = 'Users'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)

    nshe_id = db.Column(db.String(10), unique=True)
    employee_id = db.Column(db.String(15), unique=True)

    password_hash = db.Column(db.String(255), nullable=False)

    role_id = db.Column(db.Integer, db.ForeignKey('Roles.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('Departments.id'))
    major_id = db.Column(db.Integer, db.ForeignKey('Majors.id'))

    status = db.Column(db.Enum('Active', 'Inactive'), default='Active')

    department = db.relationship("Department", lazy=True)
    major = db.relationship("Major", lazy=True)

    def __repr__(self):
        return f"<User {self.email} ({self.role.name})>"


# ----------------------------
# Authentication table (required for assignment)
# One-to-One with Users
# ----------------------------
class Authentication(db.Model):
    __tablename__ = 'Authentication'

    auth_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('Users.id'), unique=True, nullable=False)

    username = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('Roles.id'), nullable=False)

    user = db.relationship("User", backref=db.backref("auth_record", uselist=False))
    role = db.relationship("Role", lazy=True)


# ----------------------------
# Professors
# ----------------------------
class Professor(db.Model):
    __tablename__ = 'Professors'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('Users.id'), nullable=False)

    title = db.Column(db.String(50))

    user = db.relationship("User", backref="professor_profile", lazy=True)


# ----------------------------
# Locations (Campus)
# ----------------------------
class Location(db.Model):
    __tablename__ = 'Locations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Campus Name
    room_number = db.Column(db.String(50), nullable=False)  # Required

    buildings = db.relationship("Building", backref="campus", lazy=True)

    def full_room_label(self):
        return f"{self.name} — Room {self.room_number}"


# ----------------------------
# Buildings
# ----------------------------
class Building(db.Model):
    __tablename__ = 'Buildings'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Building name

    location_id = db.Column(db.Integer, db.ForeignKey('Locations.id'), nullable=False)

    def full_label(self):
        return f"{self.campus.name} — {self.name}"


# ----------------------------
# Courses
# ----------------------------
class Course(db.Model):
    __tablename__ = 'Courses'

    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(20), nullable=False)
    course_name = db.Column(db.String(150), nullable=False)

    department_id = db.Column(db.Integer, db.ForeignKey('Departments.id'), nullable=False)

    department = db.relationship("Department", backref="courses", lazy=True)


# ----------------------------
# Timeslots
# ----------------------------
class Timeslot(db.Model):
    __tablename__ = 'Timeslots'

    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)


# ----------------------------
# Exams
# ----------------------------
class Exam(db.Model):
    __tablename__ = 'Exams'

    id = db.Column(db.Integer, primary_key=True)

    exam_type = db.Column(db.String(255), nullable=False)

    course_id = db.Column(db.Integer, db.ForeignKey('Courses.id'), nullable=False)
    course = db.relationship("Course", backref="exams", lazy=True)

    exam_date = db.Column(db.Date, nullable=False)
    exam_time = db.Column(db.Time)

    location_id = db.Column(db.Integer, db.ForeignKey('Locations.id'), nullable=False)
    building_id = db.Column(db.Integer, db.ForeignKey('Buildings.id'), nullable=False)

    capacity = db.Column(db.Integer, default=20)

    professor_id = db.Column(db.Integer, db.ForeignKey('Professors.id'))
    professor = db.relationship("Professor", backref="exams", lazy=True)

    timeslot_id = db.Column(db.Integer, db.ForeignKey('Timeslots.id'))
    timeslot = db.relationship("Timeslot", lazy=True)

    location = db.relationship("Location", lazy=True)
    building = db.relationship("Building", lazy=True)

    def full_location(self):
        return f"{self.location.name} — {self.building.name} — Room {self.location.room_number}"


# ----------------------------
# Registrations
# ----------------------------
class Registration(db.Model):
    __tablename__ = 'Registrations'

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.String(10), unique=True)

    exam_id = db.Column(db.Integer, db.ForeignKey('Exams.id'), nullable=False)
    exam = db.relationship("Exam", backref="registrations", lazy=True)

    user_id = db.Column(db.Integer, db.ForeignKey('Users.id'), nullable=False)
    user = db.relationship("User", backref="registrations", lazy=True)

    timeslot_id = db.Column(db.Integer)
    location_id = db.Column(db.Integer)

    registration_date = db.Column(db.DateTime, server_default=db.func.now())
    status = db.Column(db.Enum('Active','Canceled'), default='Active')

    def __repr__(self):
        return f"<Reg {self.registration_id} for exam {self.exam_id}>"
