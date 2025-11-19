from flask import Blueprint, render_template, request, flash
from flask_login import login_required
from sqlalchemy import text
from . import db

faculty_ui = Blueprint("faculty_ui", __name__)

# ==========================================================
# FACULTY DASHBOARD
# ==========================================================
@faculty_ui.route("/dashboard", methods=["GET"])
@login_required
def faculty_dashboard():
    """Landing page for faculty after login."""
    try:
        return render_template("faculty_dashboard.html")
    except Exception as e:
        flash("Error loading faculty dashboard. Please try again.", "error")
        print("Faculty dashboard error:", e)
        return render_template("faculty_dashboard.html")

# ==========================================================
# PRINT EXAM LOG
# ==========================================================
@faculty_ui.route("/print_log", methods=["GET"])
@login_required
def faculty_print_log():
    """Display a list of all exam appointments for faculty viewing or printing."""
    try:
        query = text("""
            SELECT 
                e.exam_type         AS exam_name,
                e.exam_date,

                ts.start_time       AS exam_time,      -- REAL BOOKED TIME

                l.name              AS exam_location,   -- REAL BOOKED LOCATION

                u.name              AS student_name,
                r.registration_id   AS confirmation_code,
                r.status

            FROM registrations r
            JOIN exams e          ON e.id = r.exam_id
            JOIN users u          ON u.id = r.user_id
            JOIN locations l      ON l.id = r.location_id      -- FIXED
            JOIN timeslots ts     ON ts.id = r.timeslot_id     -- FIXED

            ORDER BY e.exam_date, ts.start_time
        """)


        
        results = db.session.execute(query).mappings().all()
    except Exception as e:
        results = []
        flash("Error loading exam log. Please try again.", "error")
        print("Faculty print log error:", e)

    return render_template("faculty_print_log.html", results=results)

# ==========================================================
# SEARCH APPOINTMENTS
# ==========================================================
@faculty_ui.route("/search_appointments", methods=["GET", "POST"])
@login_required
def faculty_search_appointments():
    """Allows faculty to search for student appointments by name, exam, or confirmation code."""
    results = []
    search_term = ""

    if request.method == "POST":
        search_term = (request.form.get("search_term") or "").strip()

        query = text("""
            SELECT 
                r.registration_id     AS confirmation_code,
                r.status              AS status,

                u.name                AS student_name,

                c.course_code         AS course_code,
                e.exam_type           AS exam_type,
                e.exam_date           AS exam_date,

                ts.start_time         AS exam_time,        -- FIXED

                p.id                  AS professor_id,
                profuser.name         AS professor_name,

                l.name                AS location          -- FIXED

            FROM registrations r
            JOIN users u            ON u.id = r.user_id
            JOIN exams e            ON e.id = r.exam_id
            JOIN courses c          ON c.id = e.course_id
            JOIN professors p       ON p.id = e.professor_id
            JOIN users profuser     ON profuser.id = p.user_id

            -- REAL LOCATION + TIME NOW
            JOIN locations l        ON l.id = r.location_id
            JOIN timeslots ts       ON ts.id = r.timeslot_id

            WHERE u.name LIKE :term
            OR e.exam_type LIKE :term
            OR r.registration_id LIKE :term
            OR c.course_code LIKE :term
            OR profuser.name LIKE :term

            ORDER BY e.exam_date, ts.start_time
        """)

        try:
            results = db.session.execute(query, {"term": f"%{search_term}%"}).mappings().all()
        except Exception as e:
            flash("Error searching appointments. Please try again.", "error")
            print("Faculty search error:", e)

    return render_template("faculty_search_appointments.html",
                           results=results,
                           search_term=search_term)
