from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask import Flask, render_template, request, flash, redirect, url_for, session, jsonify
import mysql.connector
from datetime import date
import os

import os
from werkzeug.utils import secure_filename
print("HELLO FROM APP.PY")

from flask import Flask, render_template, request, flash, redirect, url_for, session, jsonify
import mysql.connector
import re
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

app = Flask(__name__)
UPLOAD_FOLDER = "uploads/voices"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.secret_key = os.environ.get("SECRET_KEY", "student_ai_secret")

# ===========================
# DATABASE CONNECTION
# ===========================

db = mysql.connector.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    user=os.environ.get("DB_USER", "root"),
    password=os.environ.get("DB_PASSWORD", ""),
    database=os.environ.get("DB_NAME", "student_ai_system"),
    consume_results=True
)
UPLOAD_FOLDER = "static/voices"

# =========================================================
# FINAL PROJECT TABLE SAFETY
# =========================================================
# Older copies of this project may not have the optional calling
# tables. Creating them here keeps the application usable without
# deleting any existing records.
def ensure_project_tables():
    cursor = db.cursor()
    try:
        cursor.execute("""
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
            )
        """)
        cursor.execute("""
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
            )
        """)
        db.commit()
    except Exception as e:
        db.rollback()
        print("PROJECT TABLE CHECK:", e)
    finally:
        cursor.close()

ensure_project_tables()

# =========================================================
# COLLEGE LOGIN ID MIGRATION
# =========================================================
def ensure_college_login_id():
    cursor = db.cursor()
    try:
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'colleges'
              AND COLUMN_NAME = 'college_login_id'
        """)
        exists = cursor.fetchone()[0]

        if not exists:
            cursor.execute("""
                ALTER TABLE colleges
                ADD COLUMN college_login_id VARCHAR(20) NULL UNIQUE
                AFTER college_id
            """)

        cursor.execute("""
            UPDATE colleges
            SET college_login_id = CAST(college_id AS CHAR)
            WHERE college_login_id IS NULL
               OR TRIM(college_login_id) = ''
               OR college_login_id LIKE 'COL%'
        """)

        db.commit()
        print("COLLEGE LOGIN ID CHECK: OK")
    except Exception as e:
        db.rollback()
        print("COLLEGE LOGIN ID CHECK:", e)
    finally:
        cursor.close()

ensure_college_login_id()



if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ===========================
# HOME PAGE
# ===========================
@app.route("/")
def home():

    db.reconnect(attempts=3, delay=1)

    return redirect(url_for("college_login"))


# ===========================
# COLLEGE REGISTRATION
# ===========================

@app.route("/college_register", methods=["GET", "POST"])
def college_register():

    if request.method == "POST":

        college_name = request.form.get("college_name", "").strip()
        college_code = request.form.get("college_code", "").strip()
        address = request.form.get("address", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        phone = request.form.get("phone", "").strip()
        calling_number = request.form.get("calling_number", "").strip()

        if not college_name or not college_code or not email or not username or not password or not phone:
            flash("❌ Please fill all required fields.")
            return render_template("college_register.html")

        cursor = db.cursor(dictionary=True, buffered=True)

        try:
            cursor.execute("SELECT college_id FROM colleges WHERE username=%s LIMIT 1", (username,))
            if cursor.fetchone():
                flash("❌ Username already exists.")
                return render_template("college_register.html")

            cursor.execute("SELECT college_id FROM colleges WHERE email=%s LIMIT 1", (email,))
            if cursor.fetchone():
                flash("❌ Email already exists.")
                return render_template("college_register.html")

            cursor.execute("SELECT college_id FROM colleges WHERE college_code=%s LIMIT 1", (college_code,))
            if cursor.fetchone():
                flash("❌ College Code already exists.")
                return render_template("college_register.html")

            cursor.execute("""
                INSERT INTO colleges
                (college_name, college_code, address, email, username, password, phone, calling_number)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                college_name, college_code, address, email, username,
                password, phone, calling_number
            ))

            new_college_id = cursor.lastrowid
            college_login_id = str(new_college_id)

            cursor.execute("""
                UPDATE colleges
                SET college_login_id=%s
                WHERE college_id=%s
            """, (college_login_id, new_college_id))

            db.commit()
            cursor.close()

            print("========================================")
            print("COLLEGE REGISTERED")
            print("College DB ID:", new_college_id)
            print("College ID:", college_login_id)
            print("College Name:", college_name)
            print("========================================")

            return render_template(
                "college_register.html",
                registration_success=True,
                college_login_id=college_login_id,
                college_name=college_name
            )

        except Exception as e:
            db.rollback()
            cursor.close()
            print("COLLEGE REGISTRATION ERROR:", repr(e))
            flash("❌ College registration failed. Check terminal.")
            return render_template("college_register.html")

    return render_template("college_register.html")


# ===========================
# COLLEGE LOGIN
# ===========================

@app.route("/college_login", methods=["GET", "POST"])
def college_login():

    if request.method == "POST":

        college_login_id = request.form.get("college_login_id", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not college_login_id or not username or not password:
            flash("❌ College ID, Username and Password are required.")
            return render_template("college_login.html")

        try:
            college_id_for_login = int(college_login_id)
        except ValueError:
            flash("❌ College ID must be a number.")
            return render_template("college_login.html")

        cursor = db.cursor(dictionary=True, buffered=True)

        cursor.execute("""
            SELECT *
            FROM colleges
            WHERE college_id=%s
              AND username=%s
            LIMIT 1
        """, (college_id_for_login, username))

        college = cursor.fetchone()
        cursor.close()

        if not college:
            flash("❌ Invalid College ID or Username.")
            return render_template("college_login.html")

        if college["password"] != password:
            flash("❌ Wrong Password.")
            return render_template("college_login.html")

        session["college_id"] = college["college_id"]
        session["college_login_id"] = str(college["college_id"])
        session["college_name"] = college["college_name"]

        flash("✅ College Login Successful!")
        return redirect(url_for("college_dashboard"))

    return render_template("college_login.html")


# ===========================
# COLLEGE LOGOUT
# ===========================

@app.route("/college_logout")
def college_logout():

    session.clear()

    return redirect(
        url_for("college_login")
    )
# =========================================================
# CREATE TEACHER
# =========================================================

@app.route("/create_teacher", methods=["GET", "POST"])
def create_teacher():

    if "college_id" not in session:
        return redirect(url_for("college_login"))

    if request.method == "POST":

        teacher_name = request.form.get("teacher_name", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        mobile = request.form.get("mobile", "").strip()
        password = request.form.get("password", "").strip()

        print("\n========================================")
        print("🔥 CREATE TEACHER POST")
        print("FORM:", dict(request.form))
        print("========================================")

        if not teacher_name or not email or not mobile or not password:
            flash("❌ Please fill all required fields.")
            return render_template("create_teacher.html")

        cursor = db.cursor(dictionary=True, buffered=True)

        try:

            # Find any class belonging to this college
            cursor.execute("""
                SELECT c.class_id
                FROM classes c
                INNER JOIN departments d
                    ON c.department_id = d.department_id
                WHERE d.college_id = %s
                LIMIT 1
            """, (session["college_id"],))

            class_row = cursor.fetchone()

            if not class_row:
                flash("❌ No class is configured for this college.")
                return render_template("create_teacher.html")

            class_id = class_row["class_id"]

            # Email duplicate
            cursor.execute("""
                SELECT teacher_id
                FROM teachers
                WHERE email = %s
                LIMIT 1
            """, (email,))

            if cursor.fetchone():
                flash("❌ Email already exists.")
                return render_template("create_teacher.html")

            # Username duplicate
            if username:

                cursor.execute("""
                    SELECT teacher_id
                    FROM teachers
                    WHERE username = %s
                    LIMIT 1
                """, (username,))

                if cursor.fetchone():
                    flash("❌ Username already exists.")
                    return render_template("create_teacher.html")

            print("🔥 INSERTING TEACHER")
            print("College:", session["college_id"])
            print("Class:", class_id)
            print("Name:", teacher_name)

            cursor.execute("""
                INSERT INTO teachers
                (
                    college_id,
                    class_id,
                    teacher_name,
                    email,
                    username,
                    mobile,
                    password
                )
                VALUES
                (%s, %s, %s, %s, %s, %s, %s)
            """, (
                session["college_id"],
                class_id,
                teacher_name,
                email,
                username if username else None,
                mobile,
                password
            ))

            new_id = cursor.lastrowid

            db.commit()

            print("🔥🔥 TEACHER SAVED 🔥🔥")
            print("NEW TEACHER ID:", new_id)
            print("========================================\n")

            flash("✅ Teacher created successfully!")

            return redirect(url_for("teacher_list"))

        except Exception as e:

            db.rollback()

            print("\n========================================")
            print("❌ CREATE TEACHER ERROR")
            print("TYPE:", type(e).__name__)
            print("ERROR:", repr(e))
            print("========================================\n")

            flash("❌ Teacher could not be created. Check terminal.")

            return render_template("create_teacher.html")

        finally:

            cursor.close()

    return render_template("create_teacher.html")
# ===========================
# COLLEGE DASHBOARD
# ===========================

@app.route("/college_dashboard")
def college_dashboard():

    if "college_id" not in session:
        return redirect(url_for("college_login"))
    return render_template(
        "college_dashboard.html",
        college_name=session["college_name"],
        college_login_id=session.get("college_login_id")
    )

    # ===========================
# EDIT COLLEGE PROFILE
# ===========================

@app.route("/edit_college", methods=["GET", "POST"])
def edit_college():

    if "college_id" not in session:
        return redirect(url_for("college_login"))

    cursor = db.cursor(dictionary=True)
    

    if request.method == "POST":
        print("🔥🔥🔥 CREATE TEACHER POST REACHED 🔥🔥🔥")
        print("FORM =", dict(request.form))

        college_name = request.form["college_name"]
        college_code = request.form["college_code"]
        address = request.form["address"]
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        phone = request.form["phone"]
        calling_number = request.form["calling_number"]

        cursor.execute("""
            UPDATE colleges
            SET
                college_name=%s,
                college_code=%s,
                address=%s,
                email=%s,
                username=%s,
                password=%s,
                phone=%s,
                calling_number=%s
            WHERE college_id=%s
        """,(
            college_name,
            college_code,
            address,
            email,
            username,
            password,
            phone,
            calling_number,
            session["college_id"]
        ))

        db.commit()

        session["college_name"] = college_name

        cursor.close()

        flash("✅ College Profile Updated Successfully!")

        return redirect(url_for("college_dashboard"))

    cursor.execute("""
        SELECT *
        FROM colleges
        WHERE college_id=%s
    """,(session["college_id"],))

    college = cursor.fetchone()

    cursor.close()

    return render_template(
        "edit_college.html",
        college=college
    )
# =========================================================
# AI VOICE SETTINGS
# =========================================================

@app.route("/voice_settings")
def voice_settings():

    if "college_id" not in session:
        return redirect(url_for("college_login"))

    college_id = session["college_id"]

    cursor = db.cursor(dictionary=True, buffered=True)

    # =====================================================
    # GET VOICE + PARENT CALLING SCRIPT
    # =====================================================

    cursor.execute("""
        SELECT
            voice_id,
            college_id,
            voice_file,
            call_script,
            created_at
        FROM voice_settings
        WHERE college_id = %s
        LIMIT 1
    """, (college_id,))

    settings = cursor.fetchone()

    # =====================================================
    # GET PARENT QUESTIONS + AI ANSWERS
    # =====================================================

    cursor.execute("""
        SELECT
            question_id,
            college_id,
            parent_question,
            ai_answer
        FROM ai_questions
        WHERE college_id = %s
        ORDER BY question_id DESC
    """, (college_id,))

    questions = cursor.fetchall()

    cursor.close()

    return render_template(
        "voice_settings.html",
        settings=settings,
        questions=questions
    )

# =========================================================
# SAVE VOICE SETTINGS
# =========================================================

@app.route("/save_voice_settings", methods=["POST"])
def save_voice_settings():

    if "college_id" not in session:
        return redirect(url_for("college_login"))

    college_id = session["college_id"]

    # =====================================================
    # GET CALLING SCRIPT
    # =====================================================

    call_script = request.form.get(
        "call_script",
        ""
    ).strip()

    print("==========================================")
    print("VOICE SETTINGS DEBUG")
    print("College ID:", college_id)
    print("Call Script:", repr(call_script))
    print("==========================================")

    # =====================================================
    # GET VOICE FILE
    # =====================================================

    voice_file_name = None

    if "voice_file" in request.files:

        file = request.files["voice_file"]

        if file and file.filename:

            filename = secure_filename(
                file.filename
            )

            file.save(
                os.path.join(
                    UPLOAD_FOLDER,
                    filename
                )
            )

            voice_file_name = filename

    # =====================================================
    # DATABASE
    # =====================================================

    cursor = db.cursor(
        dictionary=True,
        buffered=True
    )

    # =====================================================
    # CHECK EXISTING SETTINGS
    # =====================================================

    cursor.execute("""
        SELECT
            voice_id,
            college_id,
            voice_file,
            call_script
        FROM voice_settings
        WHERE college_id = %s
        LIMIT 1
    """, (college_id,))

    settings = cursor.fetchone()

    # =====================================================
    # UPDATE EXISTING RECORD
    # =====================================================

    if settings:

        if voice_file_name:

            cursor.execute("""
                UPDATE voice_settings
                SET
                    voice_file = %s,
                    call_script = %s
                WHERE college_id = %s
            """, (
                voice_file_name,
                call_script,
                college_id
            ))

        else:

            cursor.execute("""
                UPDATE voice_settings
                SET
                    call_script = %s
                WHERE college_id = %s
            """, (
                call_script,
                college_id
            ))

    # =====================================================
    # INSERT NEW RECORD
    # =====================================================

    else:

        cursor.execute("""
            INSERT INTO voice_settings
            (
                college_id,
                voice_file,
                call_script
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
        """, (
            college_id,
            voice_file_name,
            call_script
        ))

    db.commit()

    cursor.close()

    print("✅ Voice settings saved successfully.")

    flash(
        "✅ Voice & Parent Calling Script Saved Successfully."
    )

    return redirect(
        url_for("voice_settings")
    )
# =========================================================
# EDIT PARENT CALLING SCRIPT PAGE
# =========================================================

@app.route("/edit_calling_script")
def edit_calling_script():

    if "college_id" not in session:
        return redirect(url_for("college_login"))

    college_id = session["college_id"]

    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT *
        FROM voice_settings
        WHERE college_id = %s
        LIMIT 1
    """, (college_id,))

    settings = cursor.fetchone()

    cursor.close()

    if not settings:

        flash("❌ Parent Calling Script was not found.")

        return redirect(url_for("voice_settings"))

    return render_template(
        "edit_calling_script.html",
        settings=settings
    )
# =========================================================
# UPDATE PARENT CALLING SCRIPT
# =========================================================

@app.route("/update_calling_script", methods=["POST"])
def update_calling_script():

    if "college_id" not in session:
        return redirect(url_for("college_login"))

    college_id = session["college_id"]

    call_script = request.form.get(
        "call_script",
        ""
    ).strip()

    cursor = db.cursor()

    cursor.execute("""
        UPDATE voice_settings
        SET call_script = %s
        WHERE college_id = %s
    """, (
        call_script,
        college_id
    ))

    db.commit()

    cursor.close()

    flash("✅ Parent Calling Script Updated Successfully.")

    return redirect(url_for("voice_settings"))   
# ===========================
# ADD AI QUESTION
# ===========================

@app.route("/add_ai_question", methods=["POST"])
def add_ai_question():

    if "college_id" not in session:
        return redirect(url_for("college_login"))

    question = request.form["parent_question"]
    answer = request.form["ai_answer"]

    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO ai_questions
        (
            college_id,
            parent_question,
            ai_answer
        )
        VALUES
        (%s,%s,%s)
    """, (
        session["college_id"],
        question,
        answer
    ))

    db.commit()
    cursor.close()

    flash("✅ AI Question Added Successfully.")

    return redirect(url_for("voice_settings"))

# =====================================================
# EDIT AI QUESTION
# =====================================================

@app.route("/edit_ai_question/<int:question_id>", methods=["GET", "POST"])
def edit_ai_question(question_id):

    if "college_id" not in session:
        return redirect(url_for("college_login"))

    cursor = db.cursor(dictionary=True, buffered=True)

    # ==========================
    # GET QUESTION
    # ==========================

    cursor.execute("""
        SELECT *
        FROM ai_questions
        WHERE question_id=%s
        AND college_id=%s
    """, (
        question_id,
        session["college_id"]
    ))

    question = cursor.fetchone()

    if not question:

        cursor.close()

        flash("❌ Question not found.")

        return redirect(url_for("voice_settings"))


    # ==========================
    # UPDATE QUESTION
    # ==========================

    if request.method == "POST":

        parent_question = request.form["parent_question"].strip()

        ai_answer = request.form["ai_answer"].strip()


        cursor.execute("""
            UPDATE ai_questions

            SET
                parent_question=%s,
                ai_answer=%s

            WHERE question_id=%s
            AND college_id=%s
        """, (
            parent_question,
            ai_answer,
            question_id,
            session["college_id"]
        ))


        db.commit()

        cursor.close()

        flash("✅ Parent Question & AI Answer updated successfully!")

        return redirect(url_for("voice_settings"))


    cursor.close()


    return render_template(
        "edit_ai_question.html",
        question=question
    )

# =====================================================
# DELETE AI QUESTION
# =====================================================

@app.route("/delete_ai_question/<int:question_id>")
def delete_ai_question(question_id):

    if "college_id" not in session:
        return redirect(url_for("college_login"))

    cursor = db.cursor(dictionary=True, buffered=True)


    cursor.execute("""
        DELETE FROM ai_questions
        WHERE question_id=%s
        AND college_id=%s
    """, (
        question_id,
        session["college_id"]
    ))


    db.commit()

    cursor.close()


    flash("🗑️ Parent Question deleted successfully!")

    return redirect(url_for("voice_settings"))
# =========================================================
# CREATE TEACHER
# =========================================================

@app.route("/teacher_register", methods=["GET", "POST"])
def teacher_register():

    if "college_id" not in session:
        return redirect(url_for("college_login"))

    if request.method == "POST":

        teacher_name = request.form["teacher_name"]
        username = request.form["username"]
        password = request.form["password"]

        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO teachers
            (teacher_name, username, password, college_id)
            VALUES (%s, %s, %s, %s)
        """, (
            teacher_name,
            username,
            password,
            session["college_id"]
        ))

        db.commit()
        cursor.close()

        flash("✅ Teacher Created Successfully!")

        return redirect(url_for("college_dashboard"))

    return render_template("teacher_register.html")

# ===========================
# TEACHER LIST
# ===========================

@app.route("/teacher_list")
def teacher_list():

    if "college_id" not in session:
        return redirect(url_for("college_login"))

    cursor = db.cursor(dictionary=True, buffered=True)

    try:

        college_id = session["college_id"]

        cursor.execute("""
            SELECT
                teacher_id,
                college_id,
                class_id,
                teacher_name,
                email,
                username,
                mobile,
                created_at
            FROM teachers
            WHERE college_id = %s
            ORDER BY teacher_id DESC
        """, (
            college_id,
        ))

        teachers = cursor.fetchall()

        print("========================================")
        print("TEACHER LIST")
        print("College ID:", college_id)
        print("Teachers:", teachers)
        print("Total Teachers:", len(teachers))
        print("========================================")

        return render_template(
            "teacher_list.html",
            teachers=teachers
        )

    except Exception as e:

        print("========================================")
        print("TEACHER LIST ERROR")
        print(str(e))
        print("========================================")

        flash("❌ Unable to load teacher list.")

        return redirect(url_for("college_dashboard"))

    finally:

        cursor.close()
# ===========================
# DELETE TEACHER
# ===========================


@app.route("/delete_teacher/<int:teacher_id>")
def delete_teacher(teacher_id):

    # Login Check
    if "college_id" not in session:
        return redirect(url_for("college_login"))

    cursor = db.cursor()

    cursor.execute(
        """
        DELETE FROM teachers
        WHERE teacher_id=%s
        AND college_id=%s
        """,
        (
            teacher_id,
            session["college_id"]
        )
    )

    db.commit()
    cursor.close()

    flash("🗑 Teacher Deleted Successfully!")

    return redirect(url_for("teacher_list"))

# ===========================
# EDIT TEACHER
# ===========================

@app.route("/edit_teacher/<int:teacher_id>", methods=["GET","POST"])
def edit_teacher(teacher_id):

    # Login Check
    if "college_id" not in session:
        return redirect(url_for("college_login"))

    cursor = db.cursor(dictionary=True)

    # Only the teacher of the logged-in college
    cursor.execute(
        """
        SELECT *
        FROM teachers
        WHERE teacher_id=%s
        AND college_id=%s
        """,
        (
            teacher_id,
            session["college_id"]
        )
    )

    teacher = cursor.fetchone()

    if teacher is None:

        cursor.close()

        flash("❌ Teacher Not Found!")

        return redirect(url_for("teacher_list"))

    if request.method == "POST":

        teacher_name = request.form["teacher_name"]
        email = request.form["email"]
        username = request.form["username"]
        mobile = request.form["mobile"]
        password = request.form["password"]

        cursor.execute(
            """
            UPDATE teachers
            SET
                teacher_name=%s,
                email=%s,
                username=%s,
                mobile=%s,
                password=%s
            WHERE
                teacher_id=%s
                AND college_id=%s
            """,
            (
                teacher_name,
                email,
                username,
                mobile,
                password,
                teacher_id,
                session["college_id"]
            )
        )

        db.commit()

        cursor.close()

        flash("✅ Teacher Updated Successfully!")

        return redirect(url_for("teacher_list"))

    cursor.close()

    return render_template(
        "edit_teacher.html",
        teacher=teacher
    )

    # ===========================
# LOGOUT
# ===========================

@app.route("/logout")
def logout():

    session.clear()

    flash("✅ Logout Successfully!")

    return redirect(url_for("college_login"))

    # ===========================
# TEACHER LOGIN
# ===========================

@app.route("/teacher_login", methods=["GET", "POST"])
def teacher_login():

    if request.method == "POST":

        college_login_id = request.form.get("college_login_id", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not college_login_id or not username or not password:
            flash("❌ College ID, Username and Password are required.")
            return render_template("teacher_login.html")

        try:
            college_id_for_login = int(college_login_id)
        except ValueError:
            flash("❌ College ID must be a number.")
            return render_template("teacher_login.html")

        cursor = db.cursor(dictionary=True, buffered=True)

        cursor.execute("""
            SELECT t.*
            FROM teachers t
            INNER JOIN colleges c ON c.college_id=t.college_id
            WHERE c.college_id=%s
              AND t.username=%s
            LIMIT 1
        """, (college_id_for_login, username))

        teacher=cursor.fetchone()
        cursor.close()

        if teacher:
            if teacher["password"] == password:
                session["teacher_id"] = teacher["teacher_id"]
                session["teacher_name"] = teacher["teacher_name"]
                session["teacher_username"] = teacher.get("username")
                session["college_id"] = teacher["college_id"]

                flash("✅ Teacher Login Successful!")
                return redirect(url_for("teacher_dashboard"))
            else:
                flash("❌ Wrong Password.")
        else:
            flash("❌ Invalid College ID or Username.")

    return render_template("teacher_login.html")


# ===========================
# TEACHER DASHBOARD
# ===========================

@app.route("/teacher_dashboard")
def teacher_dashboard():

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    return render_template(
        "teacher_dashboard.html",
        teacher_name=session["teacher_name"]
    )

  # =========================================================
# TEACHER LOGOUT
# =========================================================

@app.route("/teacher_logout")
def teacher_logout():

    session.pop("teacher_id", None)
    session.pop("teacher_name", None)
    session.pop("teacher_username", None)

    flash("✅ Teacher Logout Successful!")

    return redirect(url_for("college_dashboard"))

    # ===========================
# STUDENT MANAGEMENT
# ===========================

@app.route("/students", methods=["GET", "POST"])
def students():

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    cursor = db.cursor(dictionary=True)

    # -----------------------
    # SAVE STUDENT
    # -----------------------

    if request.method == "POST":

        roll_no = request.form["roll_no"]
        student_name = request.form["student_name"]
        academic_year = request.form["academic_year"]
        course = request.form["course"]
        year = request.form["year"]
        gender = request.form["gender"]
        mobile = request.form["mobile"]
        parent_name = request.form["parent_name"]
        parent_mobile = request.form["parent_mobile"]
        address = request.form["address"]

        cursor.execute(
            """
            INSERT INTO students
            (
                college_id,
                teacher_id,
                roll_no,
                student_name,
                academic_year,
                course,
                year,
                gender,
                mobile,
                parent_name,
                parent_mobile,
                address
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                session["college_id"],
                session["teacher_id"],
                roll_no,
                student_name,
                academic_year,
                course,
                year,
                gender,
                mobile,
                parent_name,
                parent_mobile,
                address
            )
        )

        db.commit()

        flash("✅ Student Added Successfully!")

        return redirect(url_for("students"))

    # -----------------------
    # LOAD STUDENTS
    # -----------------------

    cursor.execute(
        """
        SELECT *
        FROM students
        WHERE teacher_id=%s
        ORDER BY student_id DESC
        """,
        (session["teacher_id"],)
    )

    students = cursor.fetchall()

    cursor.close()

    return render_template(
        "students.html",
        students=students
    )

# ===========================
# DELETE STUDENT
# ===========================

@app.route("/delete_student/<int:student_id>")
def delete_student(student_id):

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    cursor = db.cursor()

    cursor.execute(
        """
        DELETE FROM students
        WHERE student_id=%s
        AND teacher_id=%s
        """,
        (
            student_id,
            session["teacher_id"]
        )
    )

    db.commit()

    cursor.close()

    flash("🗑 Student Deleted Successfully!")

    return redirect(url_for("students"))

    # ===========================
# EDIT STUDENT
# ===========================

@app.route("/edit_student/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    cursor = db.cursor(dictionary=True)

    # -----------------------
    # UPDATE STUDENT
    # -----------------------

    if request.method == "POST":

        roll_no = request.form["roll_no"]
        student_name = request.form["student_name"]
        academic_year = request.form["academic_year"]
        course = request.form["course"]
        year = request.form["year"]
        gender = request.form["gender"]
        mobile = request.form["mobile"]
        parent_name = request.form["parent_name"]
        parent_mobile = request.form["parent_mobile"]
        address = request.form["address"]

        cursor.execute(
            """
            UPDATE students
            SET
                roll_no=%s,
                student_name=%s,
                academic_year=%s,
                course=%s,
                year=%s,
                gender=%s,
                mobile=%s,
                parent_name=%s,
                parent_mobile=%s,
                address=%s
            WHERE
                student_id=%s
                AND teacher_id=%s
            """,
            (
                roll_no,
                student_name,
                academic_year,
                course,
                year,
                gender,
                mobile,
                parent_name,
                parent_mobile,
                address,
                student_id,
                session["teacher_id"]
            )
        )

        db.commit()

        cursor.close()

        flash("✅ Student Updated Successfully!")

        return redirect(url_for("students"))

    # -----------------------
    # LOAD STUDENT
    # -----------------------

    cursor.execute(
        """
        SELECT *
        FROM students
        WHERE
            student_id=%s
            AND teacher_id=%s
        """,
        (
            student_id,
            session["teacher_id"]
        )
    )

    student = cursor.fetchone()

    cursor.close()

    if not student:

        flash("❌ Student Not Found")

        return redirect(url_for("students"))

    return render_template(
        "edit_student.html",
        student=student
    )
from datetime import date

# =========================================================
# TAKE ATTENDANCE
# =========================================================

@app.route("/attendance", methods=["GET", "POST"])
def attendance():

    # =====================================================
    # TEACHER LOGIN CHECK
    # =====================================================

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    cursor = db.cursor(dictionary=True, buffered=True)

    try:

        # =================================================
        # POST
        # =================================================

        if request.method == "POST":

            attendance_date = request.form.get(
                "attendance_date"
            )

            # =================================================
            # ACTION
            # =================================================

            action = request.form.get("action", "save")

            # =================================================
            # GET ALL STUDENTS
            # =================================================

            cursor.execute("""
                SELECT
                    student_id,
                    roll_no,
                    parent_name,
                    parent_mobile
                FROM students
                WHERE teacher_id=%s
                ORDER BY roll_no
            """, (
                session["teacher_id"],
            ))

            students = cursor.fetchall()

            if not students:

                flash("❌ Students Not Found.")

                return redirect(
                    url_for("attendance")
                )

            # =================================================
            # DUPLICATE ATTENDANCE CHECK
            # =================================================

            cursor.execute("""
                SELECT attendance_id
                FROM student_attendance
                WHERE teacher_id=%s
                AND attendance_date=%s
                LIMIT 1
            """, (
                session["teacher_id"],
                attendance_date
            ))

            existing_attendance = cursor.fetchone()

            if existing_attendance:

                flash(
                    "❌ Attendance For This date has already been taken."
                )

                return redirect(
                    url_for("attendance")
                )

            # =================================================
            # NO ABSENT STUDENT
            # =================================================
            #
            # Teacher clicked the "No Absent Student" button
            #
            # Result:
            # All students = Present
            # Calling Queue = Empty
            # Parent Calling = No Absent Student
            #
            # =================================================

            if action == "no_absent":

                for student in students:

                    # -----------------------------------------
                    # SAVE PRESENT ATTENDANCE
                    # -----------------------------------------

                    cursor.execute("""
                        INSERT INTO student_attendance
                        (
                            college_id,
                            teacher_id,
                            student_id,
                            attendance_date,
                            status
                        )
                        VALUES
                        (%s,%s,%s,%s,%s)
                    """, (
                        session["college_id"],
                        session["teacher_id"],
                        student["student_id"],
                        attendance_date,
                        "Present"
                    ))

                db.commit()

                flash(
                    "✅ No Absent Student! "
                    "All Students Are Present, Attendance Has Been Saved."
                )

                return redirect(
                    url_for("attendance")
                )

            # =================================================
            # NORMAL ATTENDANCE SAVE
            # =================================================

            absent_rolls = request.form.get(
                "absent_rolls",
                ""
            ).strip()

            # =================================================
            # CONVERT ABSENT ROLL NUMBERS
            # =================================================

            absent_list = []

            if absent_rolls:

                for value in absent_rolls.split(","):

                    value = value.strip()

                    if value.isdigit():

                        absent_list.append(
                            int(value)
                        )

            # =================================================
            # SAVE EACH STUDENT
            # =================================================

            for student in students:

                # -----------------------------------------
                # CHECK ABSENT
                # -----------------------------------------

                if student["roll_no"] in absent_list:

                    status = "Absent"

                else:

                    status = "Present"

                # -----------------------------------------
                # SAVE ATTENDANCE
                # -----------------------------------------

                cursor.execute("""
                    INSERT INTO student_attendance
                    (
                        college_id,
                        teacher_id,
                        student_id,
                        attendance_date,
                        status
                    )
                    VALUES
                    (%s,%s,%s,%s,%s)
                """, (
                    session["college_id"],
                    session["teacher_id"],
                    student["student_id"],
                    attendance_date,
                    status
                ))

                # =================================================
                # ABSENT STUDENT
                # =================================================

                if status == "Absent":

                    # -----------------------------------------
                    # CALLING QUEUE
                    # -----------------------------------------

                    cursor.execute("""
                        INSERT INTO calling_queue
                        (
                            college_id,
                            teacher_id,
                            student_id,
                            parent_name,
                            parent_mobile,
                            attendance_date
                        )
                        VALUES
                        (%s,%s,%s,%s,%s,%s)
                    """, (
                        session["college_id"],
                        session["teacher_id"],
                        student["student_id"],
                        student["parent_name"],
                        student["parent_mobile"],
                        attendance_date
                    ))

                    # -----------------------------------------
                    # CALL HISTORY
                    # -----------------------------------------

                    cursor.execute("""
                        INSERT INTO call_history
                        (
                            college_id,
                            teacher_id,
                            student_id,
                            parent_name,
                            parent_mobile,
                            attendance_date,
                            call_status,
                            call_duration
                        )
                        VALUES
                        (%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        session["college_id"],
                        session["teacher_id"],
                        student["student_id"],
                        student["parent_name"],
                        student["parent_mobile"],
                        attendance_date,
                        "Pending",
                        "0"
                    ))

            # =================================================
            # SAVE DATABASE
            # =================================================

            db.commit()

            # =================================================
            # SUCCESS MESSAGE
            # =================================================

            if absent_list:

                flash(
                    "✅ Attendance Saved Successfully! "
                    f"{len(absent_list)} Absent Student(s)."
                )

            else:

                flash(
                    "✅ Attendance Saved Successfully! "
                    "All Students Are Present."
                )

            return redirect(
                url_for("attendance")
            )

        # =====================================================
        # GET — LOAD CLASS INFORMATION
        # =====================================================

        cursor.execute("""
            SELECT
                course,
                academic_year,
                year
            FROM students
            WHERE teacher_id=%s
            LIMIT 1
        """, (
            session["teacher_id"],
        ))

        info = cursor.fetchone()

        # =====================================================
        # SHOW ATTENDANCE PAGE
        # =====================================================

        return render_template(
            "attendance.html",
            today=date.today().strftime("%Y-%m-%d"),
            course=info["course"] if info else "",
            academic_year=info["academic_year"] if info else "",
            year=info["year"] if info else ""
        )

    # =====================================================
    # ERROR
    # =====================================================

    except Exception as e:

        db.rollback()

        print("======================================")
        print("ATTENDANCE ERROR")
        print("======================================")
        print(e)
        print("======================================")

        flash(
            "❌ An Eror Occured While SAving The Attendance."
        )

        return redirect(
            url_for("attendance")
        )

    # =====================================================
    # CLOSE CURSOR
    # =====================================================

    finally:

        cursor.close()
   # =========================================================
# EDIT ATTENDANCE
# =========================================================

@app.route("/edit_attendance/<attendance_date>", methods=["GET", "POST"])
def edit_attendance(attendance_date):

    # =====================================================
    # TEACHER LOGIN CHECK
    # =====================================================

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    cursor = db.cursor(dictionary=True, buffered=True)

    try:

        # =================================================
        # NO ABSENT STUDENT
        # =================================================

        if request.method == "POST" and request.form.get("action") == "no_absent":

            # ---------------------------------------------
            # 1. ALL STUDENTS PRESENT
            # ---------------------------------------------

            cursor.execute("""
                UPDATE student_attendance
                SET status='Present'
                WHERE teacher_id=%s
                AND attendance_date=%s
            """, (
                session["teacher_id"],
                attendance_date
            ))

            # ---------------------------------------------
            # 2. REMOVE ALL CALLING QUEUE
            # ---------------------------------------------

            cursor.execute("""
                DELETE FROM calling_queue
                WHERE teacher_id=%s
                AND attendance_date=%s
            """, (
                session["teacher_id"],
                attendance_date
            ))

            db.commit()

            flash(
                "✅ No Absent Student!All Students Have Been Marked Present."
            )

            return redirect(
                url_for(
                    "edit_attendance",
                    attendance_date=attendance_date
                )
            )

        # =================================================
        # SAVE MANUAL ATTENDANCE CHANGES
        # =================================================

        if request.method == "POST" and request.form.get("action") == "save":

            # ---------------------------------------------
            # GET ATTENDANCE RECORDS
            # ---------------------------------------------

            cursor.execute("""
                SELECT
                    attendance_id,
                    student_id
                FROM student_attendance
                WHERE teacher_id=%s
                AND attendance_date=%s
            """, (
                session["teacher_id"],
                attendance_date
            ))

            attendance_rows = cursor.fetchall()

            # ---------------------------------------------
            # UPDATE EACH STUDENT
            # ---------------------------------------------

            for row in attendance_rows:

                attendance_id = row["attendance_id"]
                student_id = row["student_id"]

                new_status = request.form.get(
                    f"status_{attendance_id}"
                )

                # Safety
                if new_status not in ["Present", "Absent"]:
                    continue

                # -----------------------------------------
                # UPDATE ATTENDANCE
                # -----------------------------------------

                cursor.execute("""
                    UPDATE student_attendance
                    SET status=%s
                    WHERE attendance_id=%s
                """, (
                    new_status,
                    attendance_id
                ))

                # =========================================
                # ABSENT
                # =========================================

                if new_status == "Absent":

                    # -------------------------------------
                    # GET PARENT DETAILS
                    # -------------------------------------

                    cursor.execute("""
                        SELECT
                            parent_name,
                            parent_mobile
                        FROM students
                        WHERE student_id=%s
                        LIMIT 1
                    """, (
                        student_id,
                    ))

                    parent = cursor.fetchone()

                    # -------------------------------------
                    # CHECK CALLING QUEUE
                    # -------------------------------------

                    cursor.execute("""
                        SELECT queue_id
                        FROM calling_queue
                        WHERE student_id=%s
                        AND attendance_date=%s
                        LIMIT 1
                    """, (
                        student_id,
                        attendance_date
                    ))

                    already = cursor.fetchone()

                    # -------------------------------------
                    # ADD TO CALLING QUEUE
                    # -------------------------------------

                    if not already and parent:

                        cursor.execute("""
                            INSERT INTO calling_queue
                            (
                                college_id,
                                teacher_id,
                                student_id,
                                parent_name,
                                parent_mobile,
                                attendance_date
                            )
                            VALUES
                            (%s,%s,%s,%s,%s,%s)
                        """, (
                            session["college_id"],
                            session["teacher_id"],
                            student_id,
                            parent["parent_name"],
                            parent["parent_mobile"],
                            attendance_date
                        ))

                # =========================================
                # PRESENT
                # =========================================

                else:

                    # -------------------------------------
                    # REMOVE FROM CALLING QUEUE
                    # -------------------------------------

                    cursor.execute("""
                        DELETE FROM calling_queue
                        WHERE student_id=%s
                        AND attendance_date=%s
                    """, (
                        student_id,
                        attendance_date
                    ))

            # ---------------------------------------------
            # COMMIT
            # ---------------------------------------------

            db.commit()

            flash(
                "✅ Attendance Updated Successfully!"
            )

            return redirect(
                url_for(
                    "edit_attendance",
                    attendance_date=attendance_date
                )
            )

        # =================================================
        # LOAD ATTENDANCE
        # =================================================

        cursor.execute("""
            SELECT
                a.attendance_id,
                a.student_id,
                s.roll_no,
                s.student_name,
                a.status

            FROM student_attendance a

            JOIN students s
            ON a.student_id=s.student_id

            WHERE
                a.teacher_id=%s
                AND a.attendance_date=%s

            ORDER BY s.roll_no
        """, (
            session["teacher_id"],
            attendance_date
        ))

        students = cursor.fetchall()

        # =================================================
        # CHECK IF ALL PRESENT
        # =================================================

        total_students = len(students)

        absent_count = sum(
            1
            for student in students
            if student["status"] == "Absent"
        )

        all_present = (
            total_students > 0
            and absent_count == 0
        )

        # =================================================
        # PAGE
        # =================================================

        return render_template(
            "edit_attendance.html",
            students=students,
            attendance_date=attendance_date,
            all_present=all_present,
            total_students=total_students,
            absent_count=absent_count
        )

    except Exception as e:

        db.rollback()

        print("======================================")
        print("EDIT ATTENDANCE ERROR")
        print("======================================")
        print(e)
        print("======================================")

        return f"""
        <div style="
            text-align:center;
            margin-top:60px;
            font-family:Arial;
        ">

            <h3>❌ Attendance Error</h3>

            <p>{e}</p>

        </div>
        """

    finally:

        cursor.close()
# =========================================================
# TODAY'S ABSENT STUDENTS
# =========================================================

@app.route("/today_absent")
def today_absent():

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    cursor = db.cursor(dictionary=True, buffered=True)

    try:

        today = date.today()

        print("====================================")
        print("TODAY ABSENT DEBUG")
        print("Teacher ID:", session["teacher_id"])
        print("Today:", today)
        print("====================================")

        cursor.execute("""
            SELECT
                s.student_id,
                s.roll_no,
                s.student_name,
                s.parent_name,
                s.parent_mobile,
                a.attendance_date,
                a.status
            FROM students s
            INNER JOIN student_attendance a
                ON s.student_id = a.student_id
            WHERE s.teacher_id = %s
              AND DATE(a.attendance_date) = %s
              AND LOWER(TRIM(a.status)) = 'absent'
            ORDER BY s.roll_no
        """, (
            session["teacher_id"],
            today
        ))

        students = cursor.fetchall()

        print("Today's absent students:", students)

        return render_template(
            "today_absent.html",
            students=students,
            today=today
        )

    finally:
        cursor.close()
# =========================================================
# AUTOMATIC MARATHI GENDER SLASH RESOLVER
# =========================================================

import re


def resolve_gender_script(script, gender):

    if not script:
        return script

    script = str(script)

    # -----------------------------------------
    # CLEAN GENDER
    # -----------------------------------------

    gender_clean = str(gender or "").strip().lower()

    female_values = [
        "female",
        "f",
        "girl",
        "mulgi",
        "मुलगी",
        "स्त्री",
        "महिला"
    ]

    is_female = gender_clean in female_values

    print("====================================")
    print("GENDER RESOLVER")
    print("Gender from database:", gender)
    print("Clean gender:", gender_clean)
    print("Is Female:", is_female)
    print("Before:", script)

    # -----------------------------------------
    # FEMALE
    # -----------------------------------------

    if is_female:

        replacements = [

            (r"तुमचा\s*/\s*तुमची\s+मुलगा\s*/\s*मुलगी",
             "तुमची मुलगी"),

            (r"तुमचा\s*/\s*तुमची",
             "तुमची"),

            (r"मुलगा\s*/\s*मुलगी",
             "मुलगी"),

            (r"तो\s*/\s*ती",
             "ती"),

            (r"आला\s*/\s*आली",
             "आली"),

            (r"गेला\s*/\s*गेली",
             "गेली"),

            (r"त्याने\s*/\s*तिने",
             "तिने"),

            (r"त्याचा\s*/\s*तिचा",
             "तिचा"),

            (r"त्याची\s*/\s*तिची",
             "तिची"),

            (r"त्याला\s*/\s*तिला",
             "तिला"),

            (r"मुलाला\s*/\s*मुलीला",
             "मुलीला"),

            (r"मुलाचा\s*/\s*मुलीचा",
             "मुलीचा"),

            (r"मुलाचे\s*/\s*मुलीचे",
             "मुलीचे"),

            (r"मुलाने\s*/\s*मुलीने",
             "मुलीने")
        ]

    # -----------------------------------------
    # MALE
    # -----------------------------------------

    else:

        replacements = [

            (r"तुमचा\s*/\s*तुमची\s+मुलगा\s*/\s*मुलगी",
             "तुमचा मुलगा"),

            (r"तुमचा\s*/\s*तुमची",
             "तुमचा"),

            (r"मुलगा\s*/\s*मुलगी",
             "मुलगा"),

            (r"तो\s*/\s*ती",
             "तो"),

            (r"आला\s*/\s*आली",
             "आला"),

            (r"गेला\s*/\s*गेली",
             "गेला"),

            (r"त्याने\s*/\s*तिने",
             "त्याने"),

            (r"त्याचा\s*/\s*तिचा",
             "त्याचा"),

            (r"त्याची\s*/\s*तिची",
             "त्याची"),

            (r"त्याला\s*/\s*तिला",
             "त्याला"),

            (r"मुलाला\s*/\s*मुलीला",
             "मुलाला"),

            (r"मुलाचा\s*/\s*मुलीचा",
             "मुलाचा"),

            (r"मुलाचे\s*/\s*मुलीचे",
             "मुलाचे"),

            (r"मुलाने\s*/\s*मुलीने",
             "मुलाने")
        ]

    # -----------------------------------------
    # APPLY REGEX REPLACEMENTS
    # -----------------------------------------

    for pattern, replacement in replacements:

        script = re.sub(
            pattern,
            replacement,
            script
        )

    print("After:", script)
    print("====================================")

    return script
# =========================================================
# PREPARE PARENT CALL
# =========================================================

@app.route("/prepare_parent_call/<int:student_id>")
def prepare_parent_call(student_id):

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    cursor = db.cursor(dictionary=True, buffered=True)

    try:

        # =====================================================
        # 1. GET STUDENT DETAILS
        # =====================================================

        cursor.execute("""
            SELECT
                student_id,
                student_name,
                parent_name,
                parent_mobile,
                gender
            FROM students
            WHERE student_id = %s
              AND teacher_id = %s
            LIMIT 1
        """, (
            student_id,
            session["teacher_id"]
        ))

        student = cursor.fetchone()

        if not student:
            return "❌ Student not found."

        # =====================================================
        # 2. GET TEACHER COLLEGE ID
        # =====================================================

        cursor.execute("""
            SELECT college_id
            FROM teachers
            WHERE teacher_id = %s
            LIMIT 1
        """, (
            session["teacher_id"],
        ))

        teacher = cursor.fetchone()

        if not teacher:
            return "❌ Teacher information not found."

        college_id = teacher["college_id"]

        # =====================================================
        # 3. GET COLLEGE NAME
        # =====================================================

        cursor.execute("""
            SELECT college_name
            FROM colleges
            WHERE college_id = %s
            LIMIT 1
        """, (
            college_id,
        ))

        college = cursor.fetchone()

        college_name = ""

        if college:
            college_name = college.get("college_name") or ""

        # =====================================================
        # 4. GET VOICE SETTINGS
        # =====================================================

        cursor.execute("""
            SELECT
                voice_id,
                voice_file,
                call_script,
                created_at
            FROM voice_settings
            WHERE college_id = %s
            LIMIT 1
        """, (
            college_id,
        ))

        settings = cursor.fetchone()

        # =====================================================
        # 5. GET CALL SCRIPT
        # =====================================================

        if settings:
            final_script = settings.get("call_script") or ""
        else:
            final_script = ""

        final_script = str(final_script)

        # =====================================================
        # 6. BASIC VARIABLES
        # =====================================================

        student_name = str(
            student.get("student_name") or ""
        )

        parent_name = str(
            student.get("parent_name") or ""
        )

        # =====================================================
        # 7. GENDER DETECTION
        # =====================================================

        gender = str(
            student.get("gender") or ""
        ).strip().lower()

        female_values = [
            "female",
            "f",
            "girl",
            "mulgi",
            "मुलगी",
            "स्त्री",
            "महिला"
        ]

        male_values = [
            "male",
            "m",
            "boy",
            "mulga",
            "मुलगा",
            "पुरुष"
        ]

        if gender in female_values:

            child_word = "मुलगी"

            pronoun = "ती"

            possessive_pronoun = "तिने"

            parent_child_word = "तुमची"

            arrived_word = "आली"

            gone_word = "गेली"

            his_her_word = "तिची"

            him_her_word = "तिला"

            child_object_word = "मुलीला"

            child_genitive_word = "मुलीचा"

            child_genitive_neuter_word = "मुलीचे"

            child_agent_word = "मुलीने"

        elif gender in male_values:

            child_word = "मुलगा"

            pronoun = "तो"

            possessive_pronoun = "त्याने"

            parent_child_word = "तुमचा"

            arrived_word = "आला"

            gone_word = "गेला"

            his_her_word = "त्याची"

            him_her_word = "त्याला"

            child_object_word = "मुलाला"

            child_genitive_word = "मुलाचा"

            child_genitive_neuter_word = "मुलाचे"

            child_agent_word = "मुलाने"

        else:

            # Default if gender is missing
            child_word = "मुलगा"

            pronoun = "तो"

            possessive_pronoun = "त्याने"

            parent_child_word = "तुमचा"

            arrived_word = "आला"

            gone_word = "गेला"

            his_her_word = "त्याची"

            him_her_word = "त्याला"

            child_object_word = "मुलाला"

            child_genitive_word = "मुलाचा"

            child_genitive_neuter_word = "मुलाचे"

            child_agent_word = "मुलाने"

        # =====================================================
        # 8. REPLACE {{VARIABLES}}
        # =====================================================

        final_script = final_script.replace(
            "{{student_name}}",
            student_name
        )

        final_script = final_script.replace(
            "{{parent_name}}",
            parent_name
        )

        final_script = final_script.replace(
            "{{college_name}}",
            college_name
        )

        final_script = final_script.replace(
            "{{child_word}}",
            child_word
        )

        final_script = final_script.replace(
            "{{pronoun}}",
            pronoun
        )

        final_script = final_script.replace(
            "{{possessive_pronoun}}",
            possessive_pronoun
        )

        final_script = final_script.replace(
            "{{parent_child_word}}",
            parent_child_word
        )

        final_script = final_script.replace(
            "{{arrived_word}}",
            arrived_word
        )

        final_script = final_script.replace(
            "{{gone_word}}",
            gone_word
        )

        final_script = final_script.replace(
            "{{his_her_word}}",
            his_her_word
        )

        final_script = final_script.replace(
            "{{him_her_word}}",
            him_her_word
        )

        final_script = final_script.replace(
            "{{child_object_word}}",
            child_object_word
        )

        final_script = final_script.replace(
            "{{child_genitive_word}}",
            child_genitive_word
        )

        final_script = final_script.replace(
            "{{child_genitive_neuter_word}}",
            child_genitive_neuter_word
        )

        final_script = final_script.replace(
            "{{child_agent_word}}",
            child_agent_word
        )

        # =====================================================
        # 9. GENDER SLASH RESOLVER
        # =====================================================

        import re

        if gender in female_values:

            replacements = {

                # Parent
                r"तुमचा\s*/\s*तुमची": "तुमची",

                # Child
                r"मुलगा\s*/\s*मुलगी": "मुलगी",

                # Pronoun
                r"तो\s*/\s*ती": "ती",

                # Arrival
                r"आला\s*/\s*आली": "आली",
                r"आली\s*/\s*आला": "आली",

                # Going
                r"गेला\s*/\s*गेली": "गेली",
                r"गेली\s*/\s*गेला": "गेली",

                # Agent
                r"त्याने\s*/\s*तिने": "तिने",
                r"तिने\s*/\s*त्याने": "तिने",

                # Possessive
                r"त्याचा\s*/\s*तिचा": "तिचा",
                r"तिचा\s*/\s*त्याचा": "तिचा",

                r"त्याची\s*/\s*तिची": "तिची",
                r"तिची\s*/\s*त्याची": "तिची",

                # Object
                r"त्याला\s*/\s*तिला": "तिला",
                r"तिला\s*/\s*त्याला": "तिला",

                # Child forms
                r"मुलाला\s*/\s*मुलीला": "मुलीला",
                r"मुलीला\s*/\s*मुलाला": "मुलीला",

                r"मुलाचा\s*/\s*मुलीचा": "मुलीचा",
                r"मुलीचा\s*/\s*मुलाचा": "मुलीचा",

                r"मुलाचे\s*/\s*मुलीचे": "मुलीचे",
                r"मुलीचे\s*/\s*मुलाचे": "मुलीचे",

                r"मुलाने\s*/\s*मुलीने": "मुलीने",
                r"मुलीने\s*/\s*मुलाने": "मुलीने"
            }

        else:

            replacements = {

                # Parent
                r"तुमचा\s*/\s*तुमची": "तुमचा",

                # Child
                r"मुलगा\s*/\s*मुलगी": "मुलगा",

                # Pronoun
                r"तो\s*/\s*ती": "तो",

                # Arrival
                r"आला\s*/\s*आली": "आला",
                r"आली\s*/\s*आला": "आला",

                # Going
                r"गेला\s*/\s*गेली": "गेला",
                r"गेली\s*/\s*गेला": "गेला",

                # Agent
                r"त्याने\s*/\s*तिने": "त्याने",
                r"तिने\s*/\s*त्याने": "त्याने",

                # Possessive
                r"त्याचा\s*/\s*तिचा": "त्याचा",
                r"तिचा\s*/\s*त्याचा": "त्याचा",

                r"त्याची\s*/\s*तिची": "त्याची",
                r"तिची\s*/\s*त्याची": "त्याची",

                # Object
                r"त्याला\s*/\s*तिला": "त्याला",
                r"तिला\s*/\s*त्याला": "त्याला",

                # Child forms
                r"मुलाला\s*/\s*मुलीला": "मुलाला",
                r"मुलीला\s*/\s*मुलाला": "मुलाला",

                r"मुलाचा\s*/\s*मुलीचा": "मुलाचा",
                r"मुलीचा\s*/\s*मुलाचा": "मुलाचा",

                r"मुलाचे\s*/\s*मुलीचे": "मुलाचे",
                r"मुलीचे\s*/\s*मुलाचे": "मुलाचे",

                r"मुलाने\s*/\s*मुलीने": "मुलाने",
                r"मुलीने\s*/\s*मुलाने": "मुलाने"
            }

        # =====================================================
        # 10. APPLY ALL SLASH REPLACEMENTS
        # =====================================================

        for pattern, replacement in replacements.items():

            final_script = re.sub(
                pattern,
                replacement,
                final_script
            )

        # =====================================================
        # 11. EXTRA CLEANUP
        # =====================================================

        # Remove remaining spaces around the slash
        final_script = re.sub(
            r"\s*/\s*",
            " / ",
            final_script
        )

        # Resolve known gender phrases again
        if gender in female_values:

            final_script = final_script.replace(
                "आली / आला",
                "आली"
            )

            final_script = final_script.replace(
                "आला / आली",
                "आली"
            )

            final_script = final_script.replace(
                "गेली / गेला",
                "गेली"
            )

            final_script = final_script.replace(
                "गेला / गेली",
                "गेली"
            )

        else:

            final_script = final_script.replace(
                "आली / आला",
                "आला"
            )

            final_script = final_script.replace(
                "आला / आली",
                "आला"
            )

            final_script = final_script.replace(
                "गेली / गेला",
                "गेला"
            )

            final_script = final_script.replace(
                "गेला / गेली",
                "गेला"
            )

        # =====================================================
        # 12. DEBUG PRINT
        # =====================================================

        print("")
        print("========================================")
        print("PREPARE PARENT CALL")
        print("Student :", student.get("student_name"))
        print("Gender  :", gender)
        print("College :", college_name)
        print("Script  :", final_script)
        print("========================================")
        print("")

        # =====================================================
        # 13. SEND DATA TO TEMPLATE
        # =====================================================

        return render_template(
            "prepare_parent_call.html",
            student=student,
            college_name=college_name,
            settings=settings,
            final_script=final_script
        )

    finally:

        cursor.close()
# =========================================================
# PARENT CALLING
# =========================================================

@app.route("/call_all_parents")
def call_all_parents():

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    cursor = db.cursor(dictionary=True, buffered=True)

    try:

        today = date.today()

        cursor.execute("""
            SELECT
                s.student_id,
                s.roll_no,
                s.student_name,
                s.parent_name,
                s.parent_mobile,
                a.attendance_date,
                a.status
            FROM students s
            INNER JOIN student_attendance a
                ON s.student_id = a.student_id
            WHERE s.teacher_id = %s
              AND DATE(a.attendance_date) = %s
              AND LOWER(TRIM(a.status)) = 'absent'
            ORDER BY s.roll_no
        """, (
            session["teacher_id"],
            today
        ))

        students = cursor.fetchall()

        print("====================================")
        print("PARENT CALLING")
        print("Teacher ID:", session["teacher_id"])
        print("Today's absent:", students)
        print("====================================")

        return render_template(
            "parent_calling.html",
            students=students,
            today=today
        )

    finally:
        cursor.close()

        
    # ===# =========================================================
# GET PENDING CALLS FOR COLLEGE
# =========================================================

@app.route("/pending-calls", methods=["GET"])
def pending_calls():

    # Web request: logged-in college session.
    # Android/legacy bridge: access token or bridge token + college_id.
    if "college_id" in session:
        college_id = session["college_id"]
    else:
        auth = get_mobile_auth()
        if auth:
            college_id = int(auth["college_id"])
        else:
            if not valid_mobile_token():
                return {
                    "success": False,
                    "message": "College login is required.",
                    "calls": [],
                    "total_calls": 0
                }, 401

            college_id = request.args.get("college_id", type=int)

    if not college_id:
        return {
            "success": False,
            "message": "College login is required.",
            "calls": [],
            "total_calls": 0
        }, 401

    cursor = db.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("""
            SELECT
                queue_id,
                student_id,
                parent_name,
                parent_mobile,
                attendance_date
            FROM calling_queue
            WHERE college_id = %s
              AND call_status = 'Pending'
            ORDER BY queue_id ASC
        """, (college_id,))

        calls = cursor.fetchall()

        return {
            "success": True,
            "calls": calls,
            "total_calls": len(calls)
        }
    finally:
        cursor.close()


# =========================================================
# UPDATE CALL STATUS
# =========================================================

@app.route("/update-call-status", methods=["POST"])
def update_call_status():

    data = request.get_json()

    if not data:
        return {
            "success": False,
            "message": "Request body is required"
        }, 400

    queue_id = data.get("queue_id")
    call_status = data.get("call_status")

    if not queue_id or not call_status:
        return {
            "success": False,
            "message": "queue_id and call_status are required"
        }, 400

    cursor = db.cursor()

    cursor.execute("""
        UPDATE calling_queue
        SET call_status = %s
        WHERE queue_id = %s
    """, (call_status, queue_id))

    db.commit()

    cursor.close()

    return {
        "success": True,
        "message": "Call status updated successfully",
        "queue_id": queue_id,
        "call_status": call_status
    }

#========================
# TEACHER SETTINGS
# ===========================

@app.route("/teacher_settings")
def teacher_settings():

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            teacher_name,
            email,
            mobile
        FROM teachers
        WHERE teacher_id=%s
    """, (session["teacher_id"],))

    teacher = cursor.fetchone()

    cursor.close()

    return render_template(
        "teacher_settings.html",
        teacher=teacher
    )
    # ===========================
# UPDATE TEACHER SETTINGS
# ===========================

@app.route("/update_teacher", methods=["POST"])
def update_teacher():

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    teacher_name = request.form.get("teacher_name", "").strip()
    email = request.form.get("email", "").strip()
    mobile = request.form.get("mobile", "").strip()
    password = request.form.get("password", "").strip()

    if not teacher_name or not email:
        flash("❌ Teacher Name and Email are required.")
        return redirect(url_for("teacher_settings"))

    cursor = db.cursor(dictionary=True)

    # Check whether email is already used by another teacher
    cursor.execute("""
        SELECT teacher_id
        FROM teachers
        WHERE email=%s
        AND teacher_id!=%s
    """, (
        email,
        session["teacher_id"]
    ))

    existing_teacher = cursor.fetchone()

    if existing_teacher:
        cursor.close()

        flash("❌ This email is already used by another teacher.")

        return redirect(url_for("teacher_settings"))

    # Update profile + password only if new password is entered
    if password:

        cursor.execute("""
            UPDATE teachers
            SET
                teacher_name=%s,
                email=%s,
                mobile=%s,
                password=%s
            WHERE teacher_id=%s
        """, (
            teacher_name,
            email,
            mobile,
            password,
            session["teacher_id"]
        ))

    else:

        cursor.execute("""
            UPDATE teachers
            SET
                teacher_name=%s,
                email=%s,
                mobile=%s
            WHERE teacher_id=%s
        """, (
            teacher_name,
            email,
            mobile,
            session["teacher_id"]
        ))

    db.commit()

    cursor.close()

    flash("✅ Teacher Profile Updated Successfully!")

    return redirect(url_for("teacher_settings"))

# =========================================================
# TEST PENDING PARENT CALL
# =========================================================

@app.route("/test-pending-call/<int:queue_id>")
def test_pending_call(queue_id):

    if "college_id" not in session:
        return redirect(url_for("college_login"))

    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT
            cq.queue_id,
            cq.college_id,
            cq.teacher_id,
            cq.student_id,
            cq.parent_name,
            cq.parent_mobile,
            cq.attendance_date,
            s.student_name
        FROM calling_queue cq
        JOIN students s
            ON cq.student_id = s.student_id
        WHERE cq.queue_id = %s
        AND cq.college_id = %s
        LIMIT 1
    """, (
        queue_id,
        session["college_id"]
    ))

    call = cursor.fetchone()

    cursor.close()

    if not call:
        return "❌ Pending call not found."

    return {
        "queue_id": call["queue_id"],
        "student_name": call["student_name"],
        "parent_name": call["parent_name"],
        "parent_mobile": call["parent_mobile"],
        "attendance_date": str(call["attendance_date"]),
        "status": "Pending Call Found"
    }
# ===========================
# ATTENDANCE REPORT
# ===========================

@app.route("/attendance_report")
def attendance_report():

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT
            s.student_id,
            s.roll_no,
            s.student_name,

            SUM(
                CASE
                    WHEN a.status = 'Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present_days,

            SUM(
                CASE
                    WHEN a.status = 'Absent'
                    THEN 1
                    ELSE 0
                END
            ) AS absent_days,

            COUNT(a.attendance_id) AS total_days,

            GROUP_CONCAT(
                CASE
                    WHEN a.status = 'Absent'
                    THEN DATE_FORMAT(a.attendance_date, '%d-%m-%Y')
                END
                ORDER BY a.attendance_date
                SEPARATOR ', '
            ) AS absent_dates

        FROM students s

        LEFT JOIN student_attendance a
            ON s.student_id = a.student_id

        WHERE s.teacher_id = %s

        GROUP BY
            s.student_id,
            s.roll_no,
            s.student_name

        ORDER BY s.roll_no
    """, (session["teacher_id"],))

    report = cursor.fetchall()

    cursor.close()

    # Calculate Attendance Percentage
    for row in report:

        present = row["present_days"] or 0
        absent = row["absent_days"] or 0
        total = row["total_days"] or 0

        if total == 0:
            row["percentage"] = 0
        else:
            row["percentage"] = round(
                (present / total) * 100,
                2
            )

        if not row["absent_dates"]:
            row["absent_dates"] = "No Absent"

    return render_template(
        "attendance_report.html",
        report=report
    )
# ===========================
# ATTENDANCE HISTORY
# ===========================

@app.route("/attendance_history")
def attendance_history():

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT

            attendance_date,

            COUNT(*) AS total_students,

            SUM(
                CASE
                    WHEN status='Present'
                    THEN 1
                    ELSE 0
                END
            ) AS present_students,

            SUM(
                CASE
                    WHEN status='Absent'
                    THEN 1
                    ELSE 0
                END
            ) AS absent_students

        FROM student_attendance

        WHERE teacher_id=%s

        GROUP BY attendance_date

        ORDER BY attendance_date DESC

    """, (session["teacher_id"],))

    history = cursor.fetchall()

    cursor.close()

    return render_template(
        "attendance_history.html",
        history=history
    )
# =========================================================
# FREE OFFLINE PARENT CALL DEMO HELPERS
# =========================================================

def build_gender_aware_call_script(student, college_name, template):
    """Build a personalized Marathi parent-call script without any paid API."""
    student_name = str(student.get("student_name") or "").strip()
    parent_name = str(student.get("parent_name") or "").strip()
    gender = str(student.get("gender") or "").strip().lower()

    female_values = {
        "female", "f", "girl", "mulgi", "मुलगी", "स्त्री", "महिला"
    }

    is_female = gender in female_values

    if is_female:
        values = {
            "child_word": "मुलगी",
            "pronoun": "ती",
            "possessive_pronoun": "तिने",
            "parent_child_word": "तुमची",
            "came_word": "आली",
            "did_not_come": "आली नाही",
            "went_word": "गेली",
            "did_not_go": "गेली नाही",
            "child_oblique": "मुलीला",
        }
    else:
        values = {
            "child_word": "मुलगा",
            "pronoun": "तो",
            "possessive_pronoun": "त्याने",
            "parent_child_word": "तुमचा",
            "came_word": "आला",
            "did_not_come": "आला नाही",
            "went_word": "गेला",
            "did_not_go": "गेला नाही",
            "child_oblique": "मुलाला",
        }

    script = str(template or "").strip()

    if not script:
        script = (
            "नमस्कार. मी {college_name} कॉलेजमधून बोलत आहे. "
            "{parent_child_word} {child_word} {student_name} आज कॉलेजमध्ये अनुपस्थित आहे. "
            "{pronoun} आज कॉलेजमध्ये का {came_word} नाही?"
        )

    replacements = {
        "{{student_name}}": student_name,
        "{{parent_name}}": parent_name,
        "{{college_name}}": str(college_name or ""),
        "{{child_word}}": values["child_word"],
        "{{pronoun}}": values["pronoun"],
        "{{possessive_pronoun}}": values["possessive_pronoun"],
        "{{parent_child_word}}": values["parent_child_word"],
        "{{came_word}}": values["came_word"],
        "{{did_not_come}}": values["did_not_come"],
        "{{went_word}}": values["went_word"],
        "{{did_not_go}}": values["did_not_go"],
        "{{child_oblique}}": values["child_oblique"],
    }

    for key, value in replacements.items():
        script = script.replace(key, value)

    # Resolve common slash-style Marathi alternatives left in old scripts.
    slash_replacements = [
        (r"तुमचा\s*/\s*तुमची", values["parent_child_word"]),
        (r"मुलगा\s*/\s*मुलगी", values["child_word"]),
        (r"तो\s*/\s*ती", values["pronoun"]),
        (r"आला\s*/\s*आली", values["came_word"]),
        (r"आला\s*/\s*आली\s+नाही", values["did_not_come"]),
        (r"गेला\s*/\s*गेली", values["went_word"]),
        (r"गेला\s*/\s*गेली\s+नाही", values["did_not_go"]),
        (r"त्याने\s*/\s*तिने", values["possessive_pronoun"]),
        (r"त्याला\s*/\s*तिला", values["child_oblique"]),
        (r"मुलाला\s*/\s*मुलीला", values["child_oblique"]),
        (r"मुलाचा\s*/\s*मुलीचा", "मुलीचा" if is_female else "मुलाचा"),
        (r"मुलाचे\s*/\s*मुलीचे", "मुलीचे" if is_female else "मुलाचे"),
        (r"मुलाने\s*/\s*मुलीने", "मुलीने" if is_female else "मुलाने"),
    ]

    for pattern, replacement in slash_replacements:
        script = re.sub(pattern, replacement, script)

    return script


def get_college_name_for_teacher(teacher_id, cursor):
    cursor.execute("""
        SELECT c.college_name
        FROM teachers t
        LEFT JOIN colleges c ON c.college_id = t.college_id
        WHERE t.teacher_id = %s
        LIMIT 1
    """, (teacher_id,))
    row = cursor.fetchone()
    return (row or {}).get("college_name") or ""


# =========================================================
# PARENT CALLING COMPATIBILITY ROUTES
# =========================================================

# =========================================================

@app.route("/parent_calling")
def parent_calling_page():
    # Old/alternate URL. Open the same Parent Calling page.
    return redirect(url_for("call_all_parents"))


@app.route("/prepare_parent_call")
def prepare_parent_call_without_student():
    # If an old button/bookmark opens this URL without student_id,
    # send the teacher to the Parent Calling list instead of 404.
    return redirect(url_for("call_all_parents"))


# =========================================================
# CALL HISTORY
# =========================================================

@app.route("/call_history")
def call_history():
    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    cursor = db.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("""
            SELECT
                ch.attendance_date,
                s.student_name,
                ch.parent_name,
                ch.parent_mobile,
                ch.call_status,
                ch.call_duration,
                ch.parent_response,
                ch.retry_count,
                ch.call_time,
                ch.remarks
            FROM call_history ch
            LEFT JOIN students s
                ON ch.student_id = s.student_id
            WHERE ch.teacher_id = %s
            ORDER BY ch.call_time DESC, ch.attendance_date DESC
        """, (session["teacher_id"],))

        records = cursor.fetchall()

    except Exception as e:
        # Keep dashboard usable even if call_history has not been created yet.
        print("CALL HISTORY ERROR:", e)
        records = []

    finally:
        cursor.close()

    return render_template(
        "call_history.html",
        records=records
    )
# =========================================================
# START BULK PARENT CALLS
# =========================================================

@app.route("/start_bulk_parent_calls", methods=["POST"])
def start_bulk_parent_calls():
    """Create a one-by-one SIM calling queue for the Android companion app."""
    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    cursor = db.cursor(dictionary=True, buffered=True)
    try:
        today = date.today()
        teacher_id = session["teacher_id"]
        college_id = session["college_id"]

        cursor.execute("""
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
            )
        """)

        cursor.execute("""
            SELECT s.student_id, s.roll_no, s.student_name,
                   s.parent_name, s.parent_mobile, s.gender,
                   a.attendance_date, a.status
            FROM students s
            INNER JOIN student_attendance a ON s.student_id=a.student_id
            WHERE s.teacher_id=%s
              AND DATE(a.attendance_date)=%s
              AND LOWER(TRIM(a.status))='absent'
            ORDER BY s.roll_no
        """, (teacher_id, today))
        students = cursor.fetchall()

        if not students:
            return render_template("bulk_call_result.html",
                                   students=[], today=today,
                                   message="There are no absent students today.")

        college_name = get_college_name_for_teacher(teacher_id, cursor)
        cursor.execute("""
            SELECT call_script FROM voice_settings
            WHERE college_id=%s LIMIT 1
        """, (college_id,))
        settings = cursor.fetchone()
        template = (settings or {}).get("call_script") or ""

        for s in students:
            if not s.get("parent_mobile"):
                continue

            cursor.execute("""
                SELECT queue_id FROM calling_queue
                WHERE teacher_id=%s AND student_id=%s
                  AND DATE(attendance_date)=%s
                  AND call_status IN ('Pending','Calling')
                LIMIT 1
            """, (teacher_id, s["student_id"], today))
            if cursor.fetchone():
                continue

            cursor.execute("""
                INSERT INTO calling_queue
                (college_id, teacher_id, student_id, parent_name,
                 parent_mobile, attendance_date, call_status)
                VALUES (%s,%s,%s,%s,%s,%s,'Pending')
            """, (college_id, teacher_id, s["student_id"],
                  s["parent_name"], s["parent_mobile"], today))

            cursor.execute("""
                INSERT INTO call_history
                (college_id, teacher_id, student_id, parent_name,
                 parent_mobile, attendance_date, call_status,
                 call_duration, remarks)
                VALUES (%s,%s,%s,%s,%s,%s,'Pending','0','Queued for SIM calling')
            """, (college_id, teacher_id, s["student_id"],
                  s["parent_name"], s["parent_mobile"], today))

        db.commit()

        queue = []
        for s in students:
            queue.append({
                "student_id": s["student_id"],
                "roll_no": s["roll_no"],
                "student_name": s["student_name"],
                "parent_name": s["parent_name"],
                "parent_mobile": s["parent_mobile"],
                "status": "Ready" if s.get("parent_mobile") else "Mobile Number Not Available",
                "script": build_gender_aware_call_script(s, college_name, template)
            })

        return render_template(
            "bulk_call_result.html",
            students=queue,
            today=today,
            message="Calling queue created. Keep the Android SIM Caller app running; it will call parents one by one."
        )
    except Exception as e:
        db.rollback()
        app.logger.exception("Bulk parent calling error")
        return render_template("bulk_call_result.html",
                               students=[], today=date.today(),
                               message=f"Unable to prepare the calling queue: {e}"), 500
    finally:
        cursor.close()



# =========================================================
# ANDROID APP LOGIN / AUTHENTICATION
# =========================================================
MOBILE_AUTH_MAX_AGE = 86400  # 24 hours
MOBILE_AUTH_SALT = "android-college-login-v1"

def mobile_serializer():
    return URLSafeTimedSerializer(app.secret_key, salt=MOBILE_AUTH_SALT)

def create_mobile_access_token(college_id, username):
    return mobile_serializer().dumps({
        "college_id": int(college_id),
        "username": username
    })

def get_mobile_auth():
    token = request.args.get("access_token", "").strip()
    if not token:
        return None
    try:
        return mobile_serializer().loads(token, max_age=MOBILE_AUTH_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None

@app.route("/mobile/login", methods=["POST"])
def mobile_login():

    # The initial Android login uses the local bridge token as an extra safeguard.
    if not valid_mobile_token():
        return jsonify({"success": False, "message": "Invalid mobile authentication."}), 401

    data = request.get_json(silent=True) or {}
    college_login_id = str(data.get("college_login_id") or "").strip()
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")

    if not college_login_id or not username or not password:
        return jsonify({
            "success": False,
            "message": "College ID, username and password are required."
        }), 400
    try:
        college_id_for_login = int(college_login_id)
    except ValueError:
        return jsonify({
            "success": False,
            "message": "College ID must be a number."
        }), 400

    cursor = db.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("""
            SELECT college_id, college_name, username, password
            FROM colleges
            WHERE college_id=%s AND username=%s
            LIMIT 1
        """, (college_id_for_login, username))
        college = cursor.fetchone()

        if not college or college["password"] != password:
            return jsonify({
                "success": False,
                "message": "Invalid College ID, username or password."
            }), 401

        access_token = create_mobile_access_token(
            college["college_id"], college["username"]
        )

        return jsonify({
            "success": True,
            "access_token": access_token,
            "college_id": college["college_id"],
            "college_login_id": str(college["college_id"]),
            "college_name": college["college_name"],
            "username": college["username"]
        })
    finally:
        cursor.close()

# =========================================================
# FREE SIM CALLING BRIDGE
# =========================================================

MOBILE_BRIDGE_TOKEN = os.environ.get(
    "MOBILE_BRIDGE_TOKEN",
    "AI_STUDENT_SYSTEM_FREE_BRIDGE_2026"
)

def valid_mobile_token():
    return request.args.get("token") == MOBILE_BRIDGE_TOKEN


@app.route("/mobile/pending-calls", methods=["GET"])
def mobile_pending_calls():

    auth = get_mobile_auth()
    if auth:
        college_id = int(auth["college_id"])
    else:
        if not valid_mobile_token():
            return jsonify({"success": False, "message": "Invalid mobile authentication."}), 401
        college_id = request.args.get("college_id", type=int)

    if not college_id:
        return jsonify({"success": False, "message": "College authentication is required."}), 401

    cursor=db.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("""
            SELECT q.queue_id, q.student_id, q.parent_name, q.parent_mobile,
                   q.attendance_date, s.student_name
            FROM calling_queue q
            LEFT JOIN students s ON s.student_id=q.student_id
            WHERE q.college_id=%s AND q.call_status='Pending'
            ORDER BY q.queue_id ASC
        """,(college_id,))
        calls=cursor.fetchall()
        return jsonify({
            "success": True,
            "calls": calls,
            "total_calls": len(calls)
        })
    finally:
        cursor.close()


@app.route("/mobile/next-call", methods=["GET"])
def mobile_next_call():
    auth = get_mobile_auth()
    if auth:
        college_id = int(auth["college_id"])
    else:
        if not valid_mobile_token():
            return jsonify({"success": False, "message": "Invalid mobile authentication."}), 401
        college_id = request.args.get("college_id", type=int)
        if not college_id:
            return jsonify({"success": False, "message": "college_id is required."}), 400

    cursor = db.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("""
            SELECT queue_id, teacher_id, student_id, parent_name,
                   parent_mobile, attendance_date
            FROM calling_queue
            WHERE college_id=%s AND call_status='Pending'
            ORDER BY queue_id ASC
            LIMIT 1
        """, (college_id,))
        call = cursor.fetchone()

        if not call:
            return jsonify({"success": True, "call": None})

        cursor.execute("""
            UPDATE calling_queue
            SET call_status='Calling'
            WHERE queue_id=%s AND call_status='Pending'
        """, (call["queue_id"],))
        db.commit()
        return jsonify({"success": True, "call": call})
    finally:
        cursor.close()


@app.route("/mobile/call-result", methods=["POST"])
def mobile_call_result():
    if not get_mobile_auth() and not valid_mobile_token():
        return jsonify({"success": False, "message": "Invalid mobile authentication."}), 401

    data = request.get_json(silent=True) or {}
    queue_id = data.get("queue_id")
    status = str(data.get("call_status") or "Failed")
    duration = str(data.get("call_duration") or "0")
    remarks = str(data.get("remarks") or "SIM call completed.")
    parent_response = data.get("parent_response")

    if not queue_id:
        return jsonify({"success": False, "message": "queue_id is required."}), 400

    if status not in {"Success","Failed","No Answer","Busy","Rejected","Cancelled"}:
        status = "Failed"

    cursor = db.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("""
            SELECT teacher_id, student_id, attendance_date
            FROM calling_queue WHERE queue_id=%s LIMIT 1
        """, (queue_id,))
        q = cursor.fetchone()
        if not q:
            return jsonify({"success": False, "message": "Queue item not found."}), 404

        cursor.execute("""
            UPDATE calling_queue SET call_status=%s WHERE queue_id=%s
        """, (status, queue_id))

        cursor.execute("""
            UPDATE call_history
            SET call_status=%s, call_duration=%s,
                parent_response=%s, call_time=CURRENT_TIMESTAMP,
                remarks=%s
            WHERE teacher_id=%s AND student_id=%s
              AND attendance_date=%s AND call_status='Pending'
            ORDER BY call_id ASC LIMIT 1
        """, (status, duration, parent_response, remarks,
              q["teacher_id"], q["student_id"], q["attendance_date"]))
        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.rollback()
        app.logger.exception("Mobile call result error")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()


@app.route("/demo_call_complete", methods=["POST"])
def demo_call_complete():
    """Store the result of the free browser voice demonstration."""
    if "teacher_id" not in session:
        return jsonify({"success": False, "message": "Login required."}), 401

    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    status = data.get("status", "Demo Completed")
    remarks = data.get("remarks", "Free browser voice demo completed.")

    if not student_id:
        return jsonify({"success": False, "message": "student_id is required."}), 400

    cursor = db.cursor(dictionary=True, buffered=True)

    try:
        # Create the optional history table if the current database does not
        # already contain it. Existing projects are left unchanged.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_history (
                call_id INT AUTO_INCREMENT PRIMARY KEY,
                college_id INT NULL,
                teacher_id INT NOT NULL,
                student_id INT NOT NULL,
                attendance_date DATE NULL,
                parent_name VARCHAR(255) NULL,
                parent_mobile VARCHAR(50) NULL,
                call_status VARCHAR(50) NOT NULL DEFAULT 'Demo Completed',
                call_duration VARCHAR(50) NULL,
                parent_response TEXT NULL,
                retry_count INT NOT NULL DEFAULT 0,
                call_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                remarks TEXT NULL
            )
        """)

        cursor.execute("""
            SELECT
                s.parent_name,
                s.parent_mobile,
                a.attendance_date,
                t.college_id
            FROM students s
            JOIN teachers t ON t.teacher_id = s.teacher_id
            LEFT JOIN student_attendance a
                ON a.student_id = s.student_id
                AND DATE(a.attendance_date) = %s
            WHERE s.student_id = %s
              AND s.teacher_id = %s
            ORDER BY a.attendance_date DESC
            LIMIT 1
        """, (date.today(), student_id, session["teacher_id"]))

        student = cursor.fetchone()

        if not student:
            return jsonify({"success": False, "message": "Student not found."}), 404

        cursor.execute("""
            INSERT INTO call_history
            (
                college_id,
                teacher_id,
                student_id,
                attendance_date,
                parent_name,
                parent_mobile,
                call_status,
                call_duration,
                parent_response,
                retry_count,
                remarks
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            student["college_id"],
            session["teacher_id"],
            student_id,
            student["attendance_date"],
            student["parent_name"],
            student["parent_mobile"],
            status,
            "Demo",
            None,
            0,
            remarks
        ))

        db.commit()

        return jsonify({"success": True, "message": "Demo result saved."})

    except Exception as e:
        db.rollback()
        app.logger.exception("Demo history error")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        cursor.close()


# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
