from flask import render_template, request, flash, redirect, url_for, session

def register_college_routes(app, db):

    # ===========================
    # HOME
    # ===========================

    @app.route("/")
    def home():
        db.reconnect(attempts=3, delay=1)
        return redirect(url_for("college_login"))

    # ===========================
    # COLLEGE REGISTER
    # ===========================

    @app.route("/college_register", methods=["GET", "POST"])
    def college_register():

        if request.method == "POST":

            cursor = db.cursor()

            cursor.execute("""
                INSERT INTO colleges
                (
                    college_name,
                    college_code,
                    address,
                    email,
                    username,
                    password,
                    phone,
                    calling_number
                )
                VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (

                request.form["college_name"],
                request.form["college_code"],
                request.form["address"],
                request.form["email"],
                request.form["username"],
                request.form["password"],
                request.form["phone"],
                request.form["calling_number"]

            ))

            db.commit()
            cursor.close()

            flash("✅ College Registered Successfully!")
            return redirect(url_for("college_login"))

        return render_template("college_register.html")

    # ===========================
    # COLLEGE LOGIN
    # ===========================

    @app.route("/college_login", methods=["GET", "POST"])
    def college_login():

        if request.method == "POST":

            cursor = db.cursor(dictionary=True)

            cursor.execute("""
                SELECT *
                FROM colleges
                WHERE username=%s
            """, (
                request.form["username"],
            ))

            college = cursor.fetchone()
            cursor.close()

            if college:

                if college["password"] == request.form["password"]:

                    session["college_id"] = college["college_id"]
                    session["college_name"] = college["college_name"]

                    flash("✅ Login Successful")

                    return redirect(url_for("college_dashboard"))

                else:

                    flash("❌ Wrong Password")

            else:

                flash("❌ Username Not Found")

        return render_template("college_login.html")

    # ===========================
    # DASHBOARD
    # ===========================

    @app.route("/college_dashboard")
    def college_dashboard():

        if "college_id" not in session:
            return redirect(url_for("college_login"))

        return render_template(
            "college_dashboard.html",
            college_name=session["college_name"]
        )

    # ===========================
    # LOGOUT
    # ===========================

    @app.route("/logout")
    def logout():

        session.clear()

        flash("✅ Logout Successful")

        return redirect(url_for("college_login"))