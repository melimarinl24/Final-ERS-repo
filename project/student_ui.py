import os
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_required, current_user
from sqlalchemy import text
from datetime import date, timedelta
from project import db
from project.email_utils import send_exam_confirmation

student_ui = Blueprint("student_ui", __name__)

print("📁 student_ui.py loaded from:", os.path.abspath(__file__))
print("🚀 student_ui blueprint registered as 'student_ui'")


# =====================================================================
# TIME SLOT HELPER
# =====================================================================
def get_timeslot_label(timeslot_id):
    try:
        tid = int(timeslot_id)
    except:
        return None, None

    hour = 8 + (tid - 1)
    if hour < 8 or hour > 16:
        return None, None

    return f"{hour:02d}:00", f"{hour+1:02d}:00"




# =====================================================================
# START RESCHEDULE (Step 0) — DOES NOT cancel anything yet
# =====================================================================
@student_ui.route("/appointments/<int:reg_id>/start-reschedule", methods=["POST"])
@login_required
def start_reschedule(reg_id):

    # Find appointment
    reg = db.session.execute(text("""
        SELECT id, user_id, status
        FROM registrations
        WHERE id = :rid
    """), {"rid": reg_id}).mappings().first()

    # Validate
    if not reg or reg["user_id"] != current_user.id:
        flash("Appointment not found.", "error")
        return redirect(url_for("student_ui.student_appointments"))

    # Save the old appointment ID in session
    session["reschedule_old_id"] = reg_id

    flash("Choose your new date and time to complete your reschedule.", "info")

    # Go to scheduling page
    return redirect(url_for("student_ui.student_exams"))


# =====================================================================
# DASHBOARD
# =====================================================================
@student_ui.route("/dashboard")
@login_required
def student_dashboard():
    return render_template("student_dashboard.html")

# =====================================================================
# EXAM SCHEDULING — STEP 1 (main page)
# =====================================================================
@student_ui.route("/exams", methods=["GET", "POST"])
@login_required
def student_exams():

    reschedule_old_id = session.get("reschedule_old_id")

    # -------------------------------------------------------------
    # HELPER: active registration counts for this student
    # -------------------------------------------------------------
    max_allowed = 3
    row = db.session.execute(text("""
        SELECT COUNT(*) AS cnt
        FROM registrations
        WHERE user_id = :uid
          AND status = 'Active'
    """), {"uid": current_user.id}).mappings().first()

    active_count = row["cnt"] if row and row["cnt"] is not None else 0
    remaining_slots = max_allowed - active_count
    if remaining_slots < 0:
        remaining_slots = 0

    # Load locations
    locations = db.session.execute(text("""
        SELECT id, name
        FROM locations
        ORDER BY name
    """)).mappings().all()

    # Load exams (using exam_locations table)
    raw = db.session.execute(text("""
        SELECT 
            e.id AS exam_id,
            e.exam_type,
            e.exam_date,
            u.name AS professor_name,
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
        JOIN exams e ON el.exam_id = e.id
        JOIN professors p ON e.professor_id = p.id
        JOIN users u ON p.user_id = u.id
        ORDER BY e.exam_date ASC
    """)).mappings().all()

    exams = []
    for r in raw:
        remaining = r["capacity"] - r["used_seats"]
        if remaining > 0:
            exams.append({
                "exam_id": r["exam_id"],
                "exam_type": r["exam_type"],
                "exam_date": r["exam_date"].strftime("%Y-%m-%d"),
                "professor_name": r["professor_name"],
                "location_id": r["location_id"],
                "remaining": remaining
            })

    # Build timeslots 8am–5pm
    timeslots = [
        {"id": i, "start_time": f"{h:02d}:00", "end_time": f"{h+1:02d}:00"}
        for i, h in enumerate(range(8, 17), start=1)
    ]

    # Build exam_dates — REQUIRED for schedule_exam.js
    exam_dates = sorted({e["exam_date"] for e in exams})

    # POST → go to review_before_confirm.html
    if request.method == "POST":
        exam_id = request.form.get("exam_id")
        loc_id = request.form.get("location_id")
        timeslot_id = request.form.get("timeslot_id")

        if not (exam_id and loc_id and timeslot_id):
            flash("Please complete all fields.", "error")
            return redirect(url_for("student_ui.student_exams"))

        # Load exam + location info
        exam_info = db.session.execute(text("""
            SELECT 
                e.exam_type AS exam_title,
                e.exam_date,
                u.name AS professor_name,

                l.name AS campus,
                b.name AS building,
                l.room_number AS room
            FROM exams e
            JOIN professors p ON e.professor_id = p.id
            JOIN users u ON p.user_id = u.id
            JOIN locations l ON l.id = :loc
            JOIN buildings b ON b.location_id = l.id
            WHERE e.id = :eid
        """), {"eid": exam_id, "loc": loc_id}).mappings().first()

        if not exam_info:
            flash("Could not load exam details.", "error")
            return redirect(url_for("student_ui.student_exams"))

        start_time, end_time = get_timeslot_label(timeslot_id)

        info = {
            "exam_title": exam_info["exam_title"],
            "exam_date": exam_info["exam_date"],
            "professor_name": exam_info["professor_name"],
            "full_location": f"{exam_info['campus']} – {exam_info['building']}, Room {exam_info['room']}",
            "start_time": start_time,
            "end_time": end_time,
            "selected_exam": exam_id,
            "selected_loc": loc_id,
            "selected_timeslot": timeslot_id,
            "reschedule_old_id": reschedule_old_id,
        }

        return render_template("review_before_confirm.html", info=info)

    # GET → show scheduling page
    return render_template(
        "schedule_exam.html",
        exams=exams,
        locations=locations,
        timeslots=timeslots,
        exam_dates=exam_dates,         # REQUIRED
        reschedule_old_id=reschedule_old_id,
        # helper data
        active_count=active_count,
        max_allowed=max_allowed,
        remaining_slots=remaining_slots,
    )

# =====================================================================
# FINAL CONFIRM — Creates New Appointment (Normal or Reschedule)
# =====================================================================
@student_ui.route("/confirm-final", methods=["POST"])
@login_required
def confirm_final():

    user_id = current_user.id
    exam_id = request.form.get("exam_id")
    timeslot_id = request.form.get("timeslot_id")
    location_id = request.form.get("location_id")

    old_reg_id = session.get("reschedule_old_id")
    is_reschedule = old_reg_id is not None

    if not exam_id or not timeslot_id or not location_id:
        flash("Missing appointment information.", "error")
        return redirect(url_for("student_ui.student_exams"))

    # ==============================================================
    # BUSINESS RULE CHECKS
    # ==============================================================

    # 1) Max 3 active registrations per student (normal booking only)
    active_row = db.session.execute(text("""
        SELECT COUNT(*) AS cnt
        FROM registrations
        WHERE user_id = :uid
          AND status = 'Active'
    """), {"uid": user_id}).mappings().first()

    active_count = active_row["cnt"] if active_row and active_row["cnt"] is not None else 0

    if not is_reschedule and active_count >= 3:
        flash("You already have 3 active exam registrations. You cannot book more.", "error")
        return redirect(url_for("student_ui.student_exams"))

    # 2) No duplicate bookings per exam (one active reservation per exam)
    #    For reschedule, ignore the existing row being replaced.
    dup_params = {"uid": user_id, "eid": exam_id}

    if is_reschedule and old_reg_id:
        dup_sql = """
            SELECT COUNT(*) AS cnt
            FROM registrations
            WHERE user_id = :uid
              AND exam_id = :eid
              AND status = 'Active'
              AND id <> :old_id
        """
        dup_params["old_id"] = old_reg_id
    else:
        dup_sql = """
            SELECT COUNT(*) AS cnt
            FROM registrations
            WHERE user_id = :uid
              AND exam_id = :eid
              AND status = 'Active'
        """

    dup_row = db.session.execute(text(dup_sql), dup_params).mappings().first()
    dup_count = dup_row["cnt"] if dup_row and dup_row["cnt"] is not None else 0

    if dup_count > 0:
        flash("You already have an active reservation for this exam.", "error")
        return redirect(url_for("student_ui.student_exams"))

    # ==============================================================
    # GENERATE REGISTRATION ID
    # ==============================================================

    row = db.session.execute(text("""
        SELECT MAX(CAST(SUBSTRING(registration_id, 4) AS UNSIGNED)) AS max_num
        FROM registrations
        WHERE registration_id LIKE 'CSN%%'
    """)).mappings().first()

    new_reg_id = f"CSN{(row['max_num'] or 0) + 1:03d}"

    # ==============================================================
    # WRITE TO DB (handle reschedule + insert) + COMMIT
    # ==============================================================

    try:
        # If reschedule → cancel old *first*
        if is_reschedule and old_reg_id:
            db.session.execute(text("""
                UPDATE registrations
                SET status = 'Canceled'
                WHERE id = :old
            """), {"old": old_reg_id})
            session.pop("reschedule_old_id", None)

        # Insert new appointment
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
        flash("Unexpected error creating appointment.", "error")
        return redirect(url_for("student_ui.student_exams"))

    # ==========================
    # EMAIL CONFIRMATION
    # ==========================
    exam_info = db.session.execute(text("""
        SELECT 
            e.exam_type AS exam_title,
            e.exam_date,
            u.name        AS professor_name,
            l.name        AS campus,
            b.name        AS building,
            l.room_number AS room
        FROM exams e
        JOIN professors p ON e.professor_id = p.id
        JOIN users u      ON p.user_id = u.id
        JOIN locations l  ON l.id = :loc_id
        JOIN buildings b  ON b.location_id = l.id
        WHERE e.id = :exam_id
    """), {"exam_id": exam_id, "loc_id": location_id}).mappings().first()

    if exam_info:
        exam_date_str = exam_info["exam_date"].strftime("%Y-%m-%d")
        start_time, end_time = get_timeslot_label(timeslot_id)
        full_location = f"{exam_info['campus']} – {exam_info['building']}, Room {exam_info['room']}"

        html_body = f"""
            <p>Hi {current_user.name},</p>
            <p>Your exam reservation is confirmed.</p>
            <ul>
              <li><strong>Exam:</strong> {exam_info['exam_title']}</li>
              <li><strong>Date:</strong> {exam_date_str}</li>
              <li><strong>Time:</strong> {start_time}–{end_time}</li>
              <li><strong>Location:</strong> {full_location}</li>
            </ul>
            <p>If you need to cancel or reschedule, please log into the Exam Registration System.</p>
        """

        print("🔥 DEBUG: sending confirmation email to", current_user.email)


        send_exam_confirmation(
            to_email=current_user.email,
            subject="CSN Exam Reservation Confirmation",
            html_body=html_body,
        )

    flash("Your exam appointment has been scheduled!", "success")
    return redirect(url_for("student_ui.student_appointments"))


# =====================================================================
# CANCEL APPOINTMENT
# =====================================================================
@student_ui.route("/appointments/<int:reg_id>/cancel", methods=["POST"])
@login_required
def cancel_appointment(reg_id):

    reg = db.session.execute(text("""
        SELECT id, user_id, status
        FROM registrations
        WHERE id = :rid
    """), {"rid": reg_id}).mappings().first()

    if not reg or reg["user_id"] != current_user.id:
        flash("Appointment not found.", "error")
        return redirect(url_for("student_ui.student_appointments"))

    if reg["status"] != "Active":
        flash("This appointment is already canceled.", "info")
        return redirect(url_for("student_ui.student_appointments"))

    db.session.execute(text("""
        UPDATE registrations
        SET status='Canceled'
        WHERE id = :rid
    """), {"rid": reg_id})
    db.session.commit()

    flash("Your appointment has been canceled.", "success")
    return redirect(url_for("student_ui.student_appointments"))

# =====================================================================
# VIEW MY APPOINTMENTS
# =====================================================================
@student_ui.route("/appointments")
@login_required
def student_appointments():

    # -------------------------------------------------------------
    # HELPER: active registration counts for this student
    # -------------------------------------------------------------
    max_allowed = 3
    row = db.session.execute(text("""
        SELECT COUNT(*) AS cnt
        FROM registrations
        WHERE user_id = :sid
          AND status = 'Active'
    """), {"sid": current_user.id}).mappings().first()

    active_count = row["cnt"] if row and row["cnt"] is not None else 0
    remaining_slots = max_allowed - active_count
    if remaining_slots < 0:
        remaining_slots = 0

    q = (request.args.get("q") or "").strip()
    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()

    filters = ""
    params = {"sid": current_user.id}

    if q:
        filters += " AND (c.course_code LIKE :like OR e.exam_type LIKE :like)"
        params["like"] = f"%{q}%"

    if start:
        filters += " AND e.exam_date >= :start"
        params["start"] = start

    if end:
        filters += " AND e.exam_date <= :end"
        params["end"] = end

    rows = db.session.execute(text(f"""
        SELECT 
            r.id AS reg_id,
            r.registration_id AS confirmation_code,
            r.status,
            e.exam_type,
            e.exam_date,
            ts.start_time AS exam_time,
            c.course_code,
            u.name AS professor_name,
            l.name AS campus,
            b.name AS building,
            l.room_number AS room
        FROM registrations r
        JOIN exams e ON e.id = r.exam_id
        JOIN timeslots ts ON ts.id = r.timeslot_id
        JOIN courses c ON c.id = e.course_id
        JOIN locations l ON l.id = r.location_id
        JOIN buildings b ON b.location_id = l.id
        JOIN professors p ON p.id = e.professor_id
        JOIN users u ON u.id = p.user_id
        WHERE r.user_id = :sid
        {filters}
        ORDER BY e.exam_date DESC
    """), params).mappings().all()

    bookings = []
    for r in rows:
        d = dict(r)
        d["full_location"] = f"{d['campus']} – {d['building']}, Room {d['room']}"
        bookings.append(d)

    return render_template(
        "appointments.html",
        bookings=bookings,
        q=q,
        start=start,
        end=end,
        # helper data
        active_count=active_count,
        max_allowed=max_allowed,
        remaining_slots=remaining_slots,
    )

