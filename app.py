import os
import sqlite3
import base64
import io
from datetime import datetime, date
from functools import wraps

import cv2
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from openpyxl import Workbook

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "attendance.db"))
YUNET_MODEL = os.path.join(BASE_DIR, "models", "face_detection_yunet_2023mar.onnx")
SFACE_MODEL = os.path.join(BASE_DIR, "models", "face_recognition_sface_2021dec.onnx")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-before-deployment")

def db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            parent_name TEXT DEFAULT '',
            parent_mobile TEXT DEFAULT '',
            face_image BLOB
        );
        CREATE TABLE IF NOT EXISTS class_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            session_date TEXT NOT NULL,
            session_time TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attendance_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Present',
            marked_at TEXT NOT NULL,
            UNIQUE(session_id, student_id),
            FOREIGN KEY(session_id) REFERENCES class_sessions(session_id),
            FOREIGN KEY(student_id) REFERENCES students(student_id)
        );
        """)

def load_models():
    if not (os.path.exists(YUNET_MODEL) and os.path.exists(SFACE_MODEL)):
        return None, None
    try:
        detector = cv2.FaceDetectorYN.create(
            YUNET_MODEL, "", (320, 320), 0.8, 0.3, 5000
        )
        recognizer = cv2.FaceRecognizerSF.create(SFACE_MODEL, "")
        return detector, recognizer
    except Exception as exc:
        app.logger.exception("Could not load face models: %s", exc)
        return None, None

detector, recognizer = load_models()

def decode_data_url(data_url):
    if not data_url or "," not in data_url:
        raise ValueError("No camera image was received.")
    raw = base64.b64decode(data_url.split(",", 1)[1])
    arr = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not read the camera image.")
    return frame

def face_feature(frame):
    global detector, recognizer
    if detector is None or recognizer is None:
        detector, recognizer = load_models()
    if detector is None or recognizer is None:
        raise RuntimeError("Face models are missing. Run: python download_models.py")
    h, w = frame.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(frame)
    if faces is None or len(faces) == 0:
        raise ValueError("No face detected. Face the camera and try again.")
    # Use the largest detected face in the frame.
    face = max(faces, key=lambda f: float(f[2] * f[3]))
    aligned = recognizer.alignCrop(frame, face)
    feature = recognizer.feature(aligned)
    return feature

def compare_features(feature_a, feature_b):
    return float(recognizer.match(feature_a, feature_b, cv2.FaceRecognizerSF_FR_COSINE))

@app.route("/")
def home():
    with db() as conn:
        student_count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        session_count = conn.execute("SELECT COUNT(*) FROM class_sessions").fetchone()[0]
        today_count = conn.execute(
            "SELECT COUNT(*) FROM attendance_records ar JOIN class_sessions cs "
            "ON ar.session_id=cs.session_id WHERE cs.session_date=? AND ar.status='Present'",
            (date.today().isoformat(),)
        ).fetchone()[0]
    return render_template("home.html", student_count=student_count,
                           session_count=session_count, today_count=today_count,
                           models_ready=detector is not None and recognizer is not None)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        sid = request.form.get("student_id", "").strip()
        name = request.form.get("name", "").strip()
        department = request.form.get("department", "").strip()
        parent_name = request.form.get("parent_name", "").strip()
        parent_mobile = request.form.get("parent_mobile", "").strip()
        image_data = request.form.get("face_image", "")
        if not all([sid, name, department, image_data]):
            flash("Please complete the student details and capture a face image.", "error")
            return redirect(url_for("register"))
        try:
            frame = decode_data_url(image_data)
            # Validate that a face can be detected before saving.
            face_feature(frame)
            ok, encoded = cv2.imencode(".jpg", frame)
            if not ok:
                raise ValueError("Could not save the captured image.")
            with db() as conn:
                conn.execute(
                    """INSERT INTO students
                    (student_id,name,department,parent_name,parent_mobile,face_image)
                    VALUES (?,?,?,?,?,?)
                    ON CONFLICT(student_id) DO UPDATE SET
                    name=excluded.name, department=excluded.department,
                    parent_name=excluded.parent_name, parent_mobile=excluded.parent_mobile,
                    face_image=excluded.face_image""",
                    (sid, name, department, parent_name, parent_mobile, encoded.tobytes())
                )
            flash("Student registered successfully.", "success")
            return redirect(url_for("teacher"))
        except Exception as exc:
            flash(str(exc), "error")
            return redirect(url_for("register"))
    return render_template("register.html")

@app.route("/teacher", methods=["GET", "POST"])
def teacher():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        if subject:
            now = datetime.now()
            with db() as conn:
                conn.execute(
                    "INSERT INTO class_sessions(subject,session_date,session_time) VALUES (?,?,?)",
                    (subject, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"))
                )
            flash("Class session created.", "success")
        return redirect(url_for("teacher"))
    with db() as conn:
        sessions = conn.execute(
            "SELECT * FROM class_sessions ORDER BY session_id DESC"
        ).fetchall()
        students = conn.execute("SELECT student_id,name,department FROM students ORDER BY name").fetchall()
    return render_template("teacher.html", sessions=sessions, students=students)

@app.route("/start/<int:session_id>")
def start_session(session_id):
    with db() as conn:
        session = conn.execute("SELECT * FROM class_sessions WHERE session_id=?", (session_id,)).fetchone()
    if session is None:
        flash("Class session not found.", "error")
        return redirect(url_for("teacher"))
    return render_template("recognize.html", session=session)

@app.route("/api/recognize/<int:session_id>", methods=["POST"])
def api_recognize(session_id):
    payload = request.get_json(silent=True) or {}
    try:
        frame = decode_data_url(payload.get("image", ""))
        feature = face_feature(frame)
        with db() as conn:
            session = conn.execute("SELECT session_id FROM class_sessions WHERE session_id=?", (session_id,)).fetchone()
            if not session:
                return jsonify(ok=False, message="Class session not found."), 404
            students = conn.execute(
                "SELECT student_id,name,face_image FROM students WHERE face_image IS NOT NULL"
            ).fetchall()
            best = None
            best_score = -1.0
            for student in students:
                image_arr = np.frombuffer(student["face_image"], dtype=np.uint8)
                saved = cv2.imdecode(image_arr, cv2.IMREAD_COLOR)
                if saved is None:
                    continue
                saved_feature = face_feature(saved)
                score = compare_features(feature, saved_feature)
                if score > best_score:
                    best_score = score
                    best = student
            if best is None or best_score < 0.363:
                return jsonify(ok=False, message="Face not recognized. Please register the student first.")
            conn.execute(
                """INSERT OR IGNORE INTO attendance_records
                (session_id,student_id,status,marked_at) VALUES (?,?,?,?)""",
                (session_id, best["student_id"], "Present", datetime.now().isoformat(timespec="seconds"))
            )
            already = conn.execute(
                "SELECT changes()"
            ).fetchone()[0] == 0
        return jsonify(ok=True, student=best["name"], student_id=best["student_id"],
                       score=round(best_score, 3),
                       message=("Attendance already recorded." if already else "Attendance recorded successfully."))
    except Exception as exc:
        return jsonify(ok=False, message=str(exc)), 400

@app.route("/student")
def student():
    sid = request.args.get("student_id", "").strip()
    with db() as conn:
        students = conn.execute("SELECT student_id,name FROM students ORDER BY name").fetchall()
        selected = None
        summary = None
        subjects = []
        if sid:
            selected = conn.execute("SELECT * FROM students WHERE student_id=?", (sid,)).fetchone()
            if selected:
                total = conn.execute(
                    "SELECT COUNT(*) FROM class_sessions"
                ).fetchone()[0]
                present = conn.execute(
                    "SELECT COUNT(*) FROM attendance_records WHERE student_id=? AND status='Present'", (sid,)
                ).fetchone()[0]
                percent = (present / total * 100) if total else 0
                summary = {"total": total, "present": present, "percentage": round(percent, 1),
                           "risk": percent < 75}
                subjects = conn.execute("""
                    SELECT cs.subject, COUNT(*) AS total,
                    SUM(CASE WHEN ar.status='Present' THEN 1 ELSE 0 END) AS present
                    FROM class_sessions cs
                    LEFT JOIN attendance_records ar ON ar.session_id=cs.session_id AND ar.student_id=?
                    GROUP BY cs.subject ORDER BY cs.subject
                """, (sid,)).fetchall()
    return render_template("student.html", students=students, selected=selected,
                           summary=summary, subjects=subjects)

@app.route("/parent")
def parent():
    # Parent portal uses student ID selection in this starter version.
    return redirect(url_for("student"))

@app.route("/export/<int:session_id>")
def export_session(session_id):
    with db() as conn:
        session = conn.execute("SELECT * FROM class_sessions WHERE session_id=?", (session_id,)).fetchone()
        if not session:
            flash("Session not found.", "error")
            return redirect(url_for("teacher"))
        rows = conn.execute("""
            SELECT s.student_id,s.name,s.department,
            COALESCE(ar.status,'Absent') AS status, ar.marked_at
            FROM students s LEFT JOIN attendance_records ar
            ON s.student_id=ar.student_id AND ar.session_id=?
            ORDER BY s.student_id
        """, (session_id,)).fetchall()
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"
    ws.append(["Student ID", "Name", "Department", "Status", "Marked At"])
    for row in rows:
        ws.append([row["student_id"], row["name"], row["department"], row["status"], row["marked_at"] or ""])
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    safe_subject = "".join(c if c.isalnum() else "_" for c in session["subject"])
    return send_file(output, as_attachment=True,
                     download_name=f"{safe_subject}_attendance_{session['session_date']}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/health")
def health():
    return jsonify(status="ok")

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
