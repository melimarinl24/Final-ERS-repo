from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from sqlalchemy import text
from datetime import date
from . import db

faculty_ui = Blueprint("faculty_ui", __name__)


# ==========================================================
# FACULTY DASHBOARD
# ==========================================================
@faculty_ui.route("/dashboard", methods=["GET"])
@login_required
def faculty_dashboard():
    return render_template("faculty_dashboard.html")


# ==========================================================
# FACULTY PRINT LOG
# ==========================================================
@faculty_ui.route("/print_log", methods=["GET"])
@login_required
def faculty_print_log():

    start  = (request.args.get("start") or "").strip()
    end    = (request.args.get("end") or "").strip()
    exam_q = (request.args.get("exam") or "").strip()
    status = (request.args.get("status") or "").strip()

    where = []
    params = {}

    if start:
        where.append("e.exam_date >= :start")
        params["start"] = start

    if end:
        where.append("e.exam_date <= :end")
        params["end"] = end

    if exam_q:
        where.append("e.exam_type LIKE :exam_q")
        params["exam_q"] = f"%{exam_q}%"

    if status in ("Active", "Canceled"):
        where.append("r.status = :status")
        params["status"] = status

    where_sql = ""
    if where:
        where_sql = "WHERE " + " AND ".join(where)

    rows = db.session.execute(text(f"""
        SELECT 
            e.exam_type       AS exam_name,
            e.exam_date,
            ts.start_time     AS exam_time,
            l.name            AS campus,
            b.name            AS building,
            l.room_number     AS room,
            u.name            AS student_name,
            r.registration_id AS confirmation_code,
            r.status
        FROM registrations r
        JOIN exams e      ON e.id = r.exam_id
        JOIN users u      ON u.id = r.user_id
        JOIN locations l  ON l.id = r.location_id
        JOIN buildings b  ON b.location_id = l.id
        JOIN timeslots ts ON ts.id = r.timeslot_id
        {where_sql}
        ORDER BY e.exam_date, ts.start_time, campus, building, room, student_name
    """), params).mappings().all()

    exams = []
    for row in rows:
        d = dict(row)
        d["full_location"] = f"{d['campus']} – {d['building']}, Room {d['room']}"
        exams.append(d)

    return render_template(
        "faculty_print_log.html",
        exams=exams,
        start=start,
        end=end,
        exam=exam_q,
        status=status,
        today=date.today().strftime("%Y-%m-%d")
    )


# ==========================================================
# FACULTY SEARCH APPOINTMENTS
# ==========================================================
@faculty_ui.route("/search_appointments", methods=["GET", "POST"])
@login_required
def faculty_search_appointments():

    results = []
    search_term = ""

    if request.method == "POST":
        search_term = (request.form.get("search_term") or "").strip()

        rows = db.session.execute(text("""
            SELECT
                r.id                AS reg_id,
                r.registration_id   AS confirmation_code,
                r.status,

                u.name              AS student_name,
                c.course_code       AS course_code,

                e.exam_type,
                e.exam_date,

                ts.start_time       AS exam_time,

                profuser.name       AS professor_name,

                l.name              AS campus,
                b.name              AS building,
                l.room_number       AS room
            FROM registrations r
            JOIN users u        ON u.id = r.user_id
            JOIN exams e        ON e.id = r.exam_id
            JOIN courses c      ON c.id = e.course_id

            JOIN professors p   ON p.id = e.professor_id
            JOIN users profuser ON profuser.id = p.user_id

            JOIN locations l    ON l.id = r.location_id
            JOIN buildings b    ON b.location_id = l.id
            JOIN timeslots ts   ON ts.id = r.timeslot_id

            WHERE u.name LIKE :term
               OR e.exam_type LIKE :term
               OR r.registration_id LIKE :term
               OR c.course_code LIKE :term
               OR profuser.name LIKE :term

            ORDER BY e.exam_date, ts.start_time
        """), {"term": f"%{search_term}%"}).mappings().all()

        for row in rows:
            d = dict(row)
            d["full_location"] = f"{d['campus']} – {d['building']}, Room {d['room']}"
            results.append(d)

    return render_template(
        "faculty_search_appointments.html",
        results=results,
        search_term=search_term
    )


# ==========================================================
# FACULTY CANCEL APPOINTMENT (FIXED)
# ==========================================================
@faculty_ui.route("/cancel/<int:reg_id>", methods=["POST"])
@login_required
def cancel_registration(reg_id):
    """
    Faculty cancellation MUST use the numeric ID.
    """

    reg = db.session.execute(text("""
        SELECT id, status
        FROM registrations
        WHERE id = :rid
    """), {"rid": reg_id}).mappings().first()

    if not reg:
        flash("Appointment not found.", "error")
        return redirect(url_for("faculty_ui.faculty_search_appointments"))

    if reg["status"] != "Active":
        flash("This appointment is already canceled.", "info")
        return redirect(url_for("faculty_ui.faculty_search_appointments"))

    db.session.execute(text("""
        UPDATE registrations
        SET status = 'Canceled'
        WHERE id = :rid
    """), {"rid": reg_id})
    db.session.commit()

    flash("Appointment canceled successfully.", "success")
    return redirect(url_for("faculty_ui.faculty_search_appointments"))
