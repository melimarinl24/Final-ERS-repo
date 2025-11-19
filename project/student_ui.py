import os
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import text
from datetime import date, timedelta
from project import db

student_ui = Blueprint("student_ui", __name__)

print("📁 student_ui.py loaded from:", os.path.abspath(__file__))
print("🚀 student_ui blueprint registered as 'student_ui'")


# ==========================================================
# TIME SLOT HELPER (IDs 1–9 → 08:00–17:00)
# ==========================================================
def get_timeslot_label(timeslot_id):
    """
    Map a timeslot_id (1..9) to a (start, end) time string.
    1 -> 08:00–09:00, 2 -> 09:00–10:00, ..., 9 -> 16:00–17:00
    """
    try:
        tid = int(timeslot_id)
    except (TypeError, ValueError):
        return None, None

    hour = 8 + (tid - 1)
    if hour < 8 or hour > 16:
        return None, None

    start = f"{hour:02d}:00"
    end = f"{hour + 1:02d}:00"
    return start, end


# ==========================================================
# DASHBOARD
# ==========================================================
@student_ui.route("/dashboard")
@login_required
def student_dashboard():
    return render_template("student_dashboard.html")



# ==========================================================
# EXAM SCHEDULING (STEP 1: FORM + REVIEW PAGE)
# ==========================================================
@student_ui.route("/exams", methods=["GET", "POST"])
@login_required
def student_exams():
    print("🔥 student_exams() route hit")

    # 1) Locations
    locations = db.session.execute(text("""
        SELECT id, name
        FROM locations
        ORDER BY name
    """)).mappings().all()

    # 2) Exams PER LOCATION using exam_locations
    raw = db.session.execute(text("""
        SELECT 
            e.id          AS exam_id,
            e.exam_type,
            e.exam_date,
            u.name        AS professor_name,
            el.location_id,
            el.capacity,
            (
                SELECT COUNT(*)
                FROM registrations r
                WHERE r.exam_id = e.id
                  AND r.location_id = el.location_id
                  AND r.status = 'Active'
            ) AS used_seats
        FROM exam_locations el
        JOIN exams e       ON el.exam_id = e.id
        JOIN professors p  ON e.professor_id = p.id
        JOIN users u       ON p.user_id = u.id
        ORDER BY e.exam_date ASC, u.name ASC, el.location_id ASC
    """)).mappings().all()

    # Shape into Python dicts + compute remaining per LOCATION
    exams = []
    for r in raw:
        remaining = r["capacity"] - r["used_seats"]
        if remaining <= 0:
            continue  # hide full sessions

        exams.append({
            "exam_id":        r["exam_id"],
            "exam_type":      r["exam_type"],
            "exam_date":      r["exam_date"].strftime("%Y-%m-%d"),
            "professor_name": r["professor_name"],
            "location_id":    r["location_id"],
            "capacity":       r["capacity"],
            "used_seats":     r["used_seats"],
            "remaining":      remaining,
        })

    # 3) Time slots (in-memory)
    timeslots = [
        {"id": i, "start_time": f"{h:02d}:00", "end_time": f"{h+1:02d}:00"}
        for i, h in enumerate(range(8, 17), start=1)
    ]

    # 4) Distinct exam dates for the calendar
    exam_dates = sorted({e["exam_date"] for e in exams})

    # ------------------------------------------------------
    # POST: Validate + go to review_before_confirm.html
    # (this part stays exactly like you had it before)
    # ------------------------------------------------------
    if request.method == "POST":
        exam_id = request.form.get("exam_id")
        loc_id  = request.form.get("location_id")
        time_id = request.form.get("timeslot_id")

        # Basic validation
        if not (exam_id and loc_id and time_id):
            flash("Please complete all fields.", "error")
            return redirect(url_for("student_ui.student_exams"))

        # Limit: max 3 active registrations
        active_count = db.session.execute(text("""
            SELECT COUNT(*)
            FROM registrations
            WHERE user_id = :u
              AND status = 'Active'
        """), {"u": current_user.id}).scalar()

        if active_count >= 3:
            flash("You cannot have more than 3 active appointments.", "error")
            return redirect(url_for("student_ui.student_exams"))

        # No duplicate exam for this user (same exam_id)
        duplicate = db.session.execute(text("""
            SELECT 1
            FROM registrations r
            WHERE r.user_id = :u
              AND r.status = 'Active'
              AND r.exam_id = :eid
        """), {"u": current_user.id, "eid": exam_id}).scalar()

        if duplicate:
            flash("You already registered for this exam.", "error")
            return redirect(url_for("student_ui.student_exams"))

        # Load exam info for review page
        exam_info = db.session.execute(text("""
            SELECT 
                e.exam_type AS exam_title,
                e.exam_date,
                u.name      AS professor_name,
                l.name      AS location
            FROM exams e
            JOIN professors p ON e.professor_id = p.id
            JOIN users u      ON p.user_id = u.id
            LEFT JOIN locations l ON l.id = :loc
            WHERE e.id = :eid
        """), {"eid": exam_id, "loc": loc_id}).mappings().first()

        if not exam_info:
            flash("Could not load exam details.", "error")
            return redirect(url_for("student_ui.student_exams"))

        # Use your existing helper
        start_time, end_time = get_timeslot_label(time_id)

        info = {
            "exam_title":        exam_info["exam_title"],
            "exam_date":         exam_info["exam_date"],
            "professor_name":    exam_info["professor_name"],
            "location":          exam_info["location"],
            "start_time":        start_time,
            "end_time":          end_time,
            "selected_exam":     exam_id,
            "selected_loc":      loc_id,
            "selected_timeslot": time_id,
        }

        return render_template("review_before_confirm.html", info=info)

    # GET: Show the scheduling form
    return render_template(
        "schedule_exam.html",
        exams=exams,
        locations=locations,
        timeslots=timeslots,
        exam_dates=exam_dates,
        min_date=date.today().strftime("%Y-%m-%d"),
        max_date=(date.today() + timedelta(days=180)).strftime("%Y-%m-%d"),
    )






# ==========================================================
# STEP 2 – FINAL CONFIRM (INSERT + SUCCESS PAGE)
# ==========================================================
@student_ui.route("/confirm-final", methods=["POST"])
@login_required
def confirm_final():
    user_id     = current_user.id
    exam_id     = request.form.get("exam_id")
    timeslot_id = request.form.get("timeslot_id")
    location_id = request.form.get("location_id")

    # ----------------------------------------
    # 1) Validate incoming data
    # ----------------------------------------
    if not exam_id or not timeslot_id or not location_id:
        flash("Missing required appointment information.", "error")
        return redirect(url_for("student_ui.student_exams"))

    # ----------------------------------------
    # 2) Prevent booking same exam twice
    # ----------------------------------------
    dup_check = db.session.execute(text("""
        SELECT id FROM registrations
        WHERE user_id = :u AND exam_id = :e AND status = 'Active'
    """), {"u": user_id, "e": exam_id}).fetchone()

    if dup_check:
        flash("You are already registered for this exam.", "error")
        return redirect(url_for("student_ui.student_exams"))

    # ----------------------------------------
    # 3) Prevent more than 3 active appointments
    # ----------------------------------------
    reg_count = db.session.execute(text("""
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE user_id = :u AND status = 'Active'
    """), {"u": user_id}).mappings().first()["count"]

    if reg_count >= 3:
        flash("You cannot book more than 3 exams.", "error")
        return redirect(url_for("student_ui.student_exams"))

    # ----------------------------------------
    # 4) Generate UNIQUE registration_id (CSN###)
    # ----------------------------------------
    row = db.session.execute(text("""
        SELECT MAX(CAST(SUBSTRING(registration_id, 4) AS UNSIGNED)) AS max_num
        FROM registrations
        WHERE registration_id LIKE 'CSN%%'
    """)).mappings().first()

    max_num = row["max_num"] or 0
    new_reg_id = f"CSN{max_num + 1:03d}"

    # ----------------------------------------
    # 5) Insert new appointment
    # ----------------------------------------
    try:
        db.session.execute(text("""
            INSERT INTO registrations
                (registration_id, user_id, exam_id, timeslot_id, location_id, registration_date, status)
            VALUES
                (:rid, :u, :e, :t, :l, NOW(), 'Active')
        """), {
            "rid": new_reg_id,
            "u": user_id,
            "e": exam_id,
            "t": timeslot_id,
            "l": location_id
        })

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print("ERROR inserting registration:", e)
        flash("An unexpected error occurred while booking your appointment.", "error")
        return redirect(url_for("student_ui.student_exams"))

    # ----------------------------------------
    # 6) Pull back details for the success page
    # ----------------------------------------
    reg = db.session.execute(text("""
        SELECT r.registration_id,
               e.exam_type AS exam_title,
               e.exam_date,
               u.name AS professor_name,
               l.name AS location,
               ts.start_time,
               ts.end_time
        FROM registrations r
        JOIN exams e      ON e.id = r.exam_id
        JOIN professors p ON p.id = e.professor_id
        JOIN users u      ON u.id = p.user_id
        JOIN locations l  ON l.id = r.location_id
        JOIN timeslots ts ON ts.id = r.timeslot_id
        WHERE r.registration_id = :rid
    """), {"rid": new_reg_id}).mappings().first()

    info = {
        "confirmation_code": reg["registration_id"],
        "exam_title":        reg["exam_title"],
        "exam_date":         reg["exam_date"],
        "professor_name":    reg["professor_name"],
        "location":          reg["location"],
        "start_time":        reg["start_time"],
        "end_time":          reg["end_time"],
    }

    return render_template("confirm_success.html", info=info)


# ==========================================================
# STUDENT — VIEW MY APPOINTMENTS
# ==========================================================
@student_ui.route("/appointments")
@login_required
def student_appointments():
    q     = (request.args.get("q") or "").strip()
    start = (request.args.get("start") or "").strip()
    end   = (request.args.get("end") or "").strip()

    # Dynamic parts
    name_filter  = ""
    start_filter = ""
    end_filter   = ""

    params = {"sid": current_user.id}

    if q:
        name_filter = " AND (c.course_code LIKE :like OR e.exam_type LIKE :like)"
        params["like"] = f"%{q}%"

    if start:
        start_filter = " AND e.exam_date >= :start"
        params["start"] = start

    if end:
        end_filter = " AND e.exam_date <= :end"
        params["end"] = end

    # FINAL SQL (only ONE ORDER BY)
    base_sql = f"""
        SELECT
            r.id              AS reg_id,
            r.registration_id AS confirmation_code,
            r.status          AS status,

            e.id              AS exam_id,
            e.exam_type       AS exam_type,
            e.exam_date       AS exam_date,

            ts.start_time     AS exam_time,

            c.course_code     AS course_code,
            l.name            AS location,
            u.name            AS professor_name
        FROM registrations r
        JOIN exams e        ON e.id = r.exam_id
        JOIN timeslots ts   ON ts.id = r.timeslot_id
        JOIN courses c      ON c.id = e.course_id
        JOIN locations l    ON l.id = r.location_id
        JOIN professors p   ON p.id = e.professor_id
        JOIN users u        ON u.id = p.user_id
        WHERE r.user_id = :sid
        {name_filter}
        {start_filter}
        {end_filter}
        ORDER BY e.exam_date DESC, ts.start_time DESC
    """

    rows = db.session.execute(text(base_sql), params).mappings().all()
    bookings = [dict(r) for r in rows]

    return render_template(
        "appointments.html",
        bookings=bookings,
        q=q, start=start, end=end
    )
