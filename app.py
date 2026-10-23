
from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.utils import secure_filename
from functools import wraps
import os

from database import get_db_connection, create_tables

# =========================
# FLASK APP
# =========================

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "rentnest_dev_key_change_me")

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "static",
    "uploads"
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================
# AUTHENTICATION DECORATORS
# =========================

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))

            if session.get("role") != role:
                return redirect(url_for("home"))

            return view(*args, **kwargs)
        return wrapped
    return decorator


# =========================
# CREATE DATABASE TABLES
# =========================

create_tables()


# =========================
# HOME
# =========================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


# =========================
# PROPERTIES
# =========================

@app.route("/properties")
def properties():
    search = request.args.get("search", "").strip()
    property_type = request.args.get("type", "").strip()
    max_rent = request.args.get("max_rent", "").strip()

    connection = get_db_connection()

    try:
        query = "SELECT * FROM properties WHERE 1=1"
        params = []

        if search:
            query += """
                AND (
                    title LIKE ?
                    OR location LIKE ?
                    OR facilities LIKE ?
                )
            """
            term = f"%{search}%"
            params.extend([term, term, term])

        if property_type:
            query += " AND property_type = ?"
            params.append(property_type)

        if max_rent:
            try:
                query += " AND rent <= ?"
                params.append(int(max_rent))
            except ValueError:
                max_rent = ""

        query += " ORDER BY id DESC"

        properties_list = connection.execute(
            query, params
        ).fetchall()

        types = connection.execute("""
            SELECT DISTINCT property_type
            FROM properties
            ORDER BY property_type
        """).fetchall()

    finally:
        connection.close()

    return render_template(
        "properties.html",
        properties=properties_list,
        property_types=types,
        search=search,
        selected_type=property_type,
        max_rent=max_rent
    )


# =========================
# PROPERTY DETAILS
# =========================

@app.route("/property/<int:property_id>")
def property_details(property_id):
    connection = get_db_connection()

    try:
        property_data = connection.execute("""
            SELECT *
            FROM properties
            WHERE id = ?
        """, (property_id,)).fetchone()
    finally:
        connection.close()

    if not property_data:
        return "Property Not Found", 404

    return render_template(
        "property_details.html",
        property=property_data
    )


# =========================
# REGISTER
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip()

        if not name or not email or not password:
            return "Please fill in all required fields.", 400

        if role not in ("Owner", "Tenant"):
            return "Invalid account role.", 400

        connection = get_db_connection()

        try:
            existing_user = connection.execute("""
                SELECT id
                FROM users
                WHERE LOWER(email) = ?
            """, (email,)).fetchone()

            if existing_user:
                return """
                    <h2>Email Already Registered</h2>
                    <a href="/register">Try Again</a>
                """

            connection.execute("""
                INSERT INTO users (name, email, password, role)
                VALUES (?, ?, ?, ?)
            """, (name, email, password, role))

            connection.commit()

        except Exception:
            connection.rollback()
            app.logger.exception("Registration failed")
            return "Registration failed. Please try again.", 500

        finally:
            connection.close()

        return """
            <div style="font-family:Arial;text-align:center;margin-top:100px">
                <h1>Registration Successful!</h1>
                <p>Your RentNest account has been created.</p>
                <a href="/login">Login Now</a>
            </div>
        """

    return render_template("register.html")


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = get_db_connection()

        try:
            user = connection.execute("""
                SELECT *
                FROM users
                WHERE LOWER(email) = ?
                  AND password = ?
            """, (email, password)).fetchone()
        finally:
            connection.close()

        if user:
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            session["email"] = user["email"]

            if user["role"] == "Owner":
                return redirect(url_for("owner_dashboard"))

            return redirect(url_for("tenant_dashboard"))

        return """
            <div style="font-family:Arial;text-align:center;margin-top:100px">
                <h1 style="color:#dc2626">Login Failed</h1>
                <p>Invalid email or password.</p>
                <a href="/login">Try Again</a>
            </div>
        """

    return render_template("login.html")


# =========================
# TENANT DASHBOARD
# =========================

@app.route("/tenant-dashboard")
@login_required
@role_required("Tenant")
def tenant_dashboard():
    connection = get_db_connection()

    try:
        bookings = connection.execute("""
            SELECT *
            FROM bookings
            WHERE user_id = ?
            ORDER BY id DESC
        """, (session["user_id"],)).fetchall()
    finally:
        connection.close()

    return render_template(
        "tenant_dashboard.html",
        name=session["name"],
        bookings=bookings
    )


# =========================
# OWNER DASHBOARD
# =========================

@app.route("/owner-dashboard")
@login_required
@role_required("Owner")
def owner_dashboard():
    return render_template(
        "owner_dashboard.html",
        name=session["name"]
    )


# =========================
# ADD PROPERTY
# =========================

@app.route("/add-property", methods=["GET", "POST"])
@login_required
@role_required("Owner")
def add_property():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        property_type = request.form.get("property_type", "").strip()
        location = request.form.get("location", "").strip()
        rent = request.form.get("rent", type=int)
        deposit = request.form.get("deposit", type=int)
        facilities = request.form.get("facilities", "").strip()

        if not title or not property_type or not location or rent is None:
            return "Please enter valid property details.", 400

        image = request.files.get("image")
        image_filename = ""

        if image and image.filename:
            image_filename = secure_filename(image.filename)

            if image_filename:
                image.save(os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    image_filename
                ))

        connection = get_db_connection()

        try:
            connection.execute("""
                INSERT INTO properties (
                    owner_id, title, property_type, location,
                    rent, deposit, facilities, image, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session["user_id"],
                title,
                property_type,
                location,
                rent,
                deposit,
                facilities,
                image_filename,
                "Available"
            ))

            connection.commit()

        except Exception:
            connection.rollback()
            app.logger.exception("Adding property failed")
            return "Unable to add property.", 500

        finally:
            connection.close()

        return redirect(url_for("owner_properties"))

    return render_template("add_property.html")


# =========================
# OWNER PROPERTIES
# =========================

@app.route("/owner-properties")
@login_required
@role_required("Owner")
def owner_properties():
    connection = get_db_connection()

    try:
        properties_list = connection.execute("""
            SELECT *
            FROM properties
            WHERE owner_id = ?
            ORDER BY id DESC
        """, (session["user_id"],)).fetchall()
    finally:
        connection.close()

    return render_template(
        "owner_properties.html",
        properties=properties_list
    )


# =========================
# EDIT PROPERTY
# =========================

@app.route("/edit-property/<int:property_id>", methods=["GET", "POST"])
@login_required
@role_required("Owner")
def edit_property(property_id):
    connection = get_db_connection()

    try:
        property_data = connection.execute("""
            SELECT *
            FROM properties
            WHERE id = ? AND owner_id = ?
        """, (property_id, session["user_id"])).fetchone()

        if not property_data:
            return "Property Not Found", 404

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            property_type = request.form.get("property_type", "").strip()
            location = request.form.get("location", "").strip()
            rent = request.form.get("rent", type=int)
            deposit = request.form.get("deposit", type=int)
            facilities = request.form.get("facilities", "").strip()

            if not title or not property_type or not location or rent is None:
                return "Please enter valid property details.", 400

            connection.execute("""
                UPDATE properties
                SET title = ?,
                    property_type = ?,
                    location = ?,
                    rent = ?,
                    deposit = ?,
                    facilities = ?
                WHERE id = ? AND owner_id = ?
            """, (
                title, property_type, location, rent,
                deposit, facilities, property_id, session["user_id"]
            ))

            connection.commit()
            return redirect(url_for("owner_properties"))

    finally:
        connection.close()

    return render_template(
        "edit_property.html",
        property=property_data
    )


# =========================
# DELETE PROPERTY
# =========================

@app.route("/delete-property/<int:property_id>")
@login_required
@role_required("Owner")
def delete_property(property_id):
    connection = get_db_connection()

    try:
        connection.execute("""
            DELETE FROM properties
            WHERE id = ? AND owner_id = ?
        """, (property_id, session["user_id"]))

        connection.commit()
    finally:
        connection.close()

    return redirect(url_for("owner_properties"))


# =========================
# SEND RENTAL REQUEST
# =========================

@app.route("/request-rental/<int:property_id>")
@role_required("Tenant")
def request_rental(property_id):
    connection = get_db_connection()

    try:
        property_data = connection.execute("""
            SELECT *
            FROM properties
            WHERE id = ?
        """, (property_id,)).fetchone()

        if not property_data:
            return "Property Not Found", 404

        if property_data["status"] != "Available":
            return "This property is not available for rent.", 400

        existing = connection.execute("""
            SELECT *
            FROM bookings
            WHERE user_id = ?
              AND property_id = ?
              AND status IN ('Pending', 'Accepted')
        """, (session["user_id"], property_id)).fetchone()

        if existing:
            return redirect(url_for("my_booking"))

        connection.execute("""
            INSERT INTO bookings (user_id, property_id, status)
            VALUES (?, ?, 'Pending')
        """, (session["user_id"], property_id))

        connection.commit()

    finally:
        connection.close()

    return redirect(url_for("my_booking"))


# =========================
# MY BOOKING
# =========================

@app.route("/my-booking")
@login_required
def my_booking():
    connection = get_db_connection()

    try:
        bookings = connection.execute("""
            SELECT
                bookings.*,
                properties.title,
                properties.location,
                properties.rent,
                properties.image
            FROM bookings
            JOIN properties
              ON bookings.property_id = properties.id
            WHERE bookings.user_id = ?
            ORDER BY bookings.id DESC
        """, (session["user_id"],)).fetchall()
    finally:
        connection.close()

    return render_template("my_booking.html", bookings=bookings)


# =========================
# TENANT MAINTENANCE
# =========================

@app.route("/maintenance/<int:property_id>", methods=["GET", "POST"])
@login_required
@role_required("Tenant")
def maintenance(property_id):
    connection = get_db_connection()

    try:
        property_data = connection.execute("""
            SELECT *
            FROM properties
            WHERE id = ?
        """, (property_id,)).fetchone()

        if not property_data:
            return "Property Not Found", 404

        if request.method == "POST":
            problem = request.form.get("problem", "").strip()

            if not problem:
                return "Please describe the problem.", 400

            connection.execute("""
                INSERT INTO maintenance_requests
                    (tenant_id, property_id, problem, status)
                VALUES (?, ?, ?, ?)
            """, (
                session["user_id"], property_id, problem, "Pending"
            ))

            connection.commit()
            return redirect(url_for("my_maintenance"))

    finally:
        connection.close()

    return render_template("maintenance.html", property=property_data)


# =========================
# OWNER MAINTENANCE
# =========================

@app.route("/owner-maintenance")
@login_required
@role_required("Owner")
def owner_maintenance():
    connection = get_db_connection()

    try:
        maintenance_requests = connection.execute("""
            SELECT
                maintenance_requests.id,
                maintenance_requests.problem,
                maintenance_requests.status,
                maintenance_requests.request_date,
                users.name AS tenant_name,
                users.email AS tenant_email,
                properties.title AS property_title,
                properties.location AS property_location
            FROM maintenance_requests
            JOIN users
              ON maintenance_requests.tenant_id = users.id
            JOIN properties
              ON maintenance_requests.property_id = properties.id
            WHERE properties.owner_id = ?
            ORDER BY maintenance_requests.id DESC
        """, (session["user_id"],)).fetchall()
    finally:
        connection.close()

    return render_template(
        "owner_maintenance.html",
        maintenance_requests=maintenance_requests
    )


# =========================
# UPDATE MAINTENANCE STATUS
# =========================

@app.route("/update-maintenance/<int:request_id>/<status>")
@login_required
@role_required("Owner")
def update_maintenance(request_id, status):
    allowed_status = ["Pending", "In Progress", "Completed"]

    if status not in allowed_status:
        return "Invalid Status", 400

    connection = get_db_connection()

    try:
        request_data = connection.execute("""
            SELECT maintenance_requests.id
            FROM maintenance_requests
            JOIN properties
              ON maintenance_requests.property_id = properties.id
            WHERE maintenance_requests.id = ?
              AND properties.owner_id = ?
        """, (request_id, session["user_id"])).fetchone()

        if not request_data:
            return "Maintenance Request Not Found", 404

        connection.execute("""
            UPDATE maintenance_requests
            SET status = ?
            WHERE id = ?
        """, (status, request_id))

        connection.commit()
    finally:
        connection.close()

    return redirect(url_for("owner_maintenance"))


# =========================
# OWNER RENTAL REQUESTS
# =========================

@app.route("/owner-requests")
@login_required
@role_required("Owner")
def owner_requests():
    connection = get_db_connection()

    try:
        requests_list = connection.execute("""
            SELECT
                bookings.id,
                bookings.status,
                bookings.request_date,
                users.name AS tenant_name,
                users.email AS tenant_email,
                properties.title AS property_title,
                properties.location AS property_location,
                properties.rent AS property_rent
            FROM bookings
            JOIN users ON bookings.user_id = users.id
            JOIN properties ON bookings.property_id = properties.id
            WHERE properties.owner_id = ?
            ORDER BY bookings.id DESC
        """, (session["user_id"],)).fetchall()
    finally:
        connection.close()

    return render_template("owner_requests.html", requests=requests_list)


# =========================
# ACCEPT RENTAL REQUEST
# =========================

@app.route("/accept-request/<int:request_id>")
@role_required("Owner")
def accept_request(request_id):
    connection = get_db_connection()

    try:
        row = connection.execute("""
            SELECT bookings.id, bookings.property_id
            FROM bookings
            JOIN properties ON bookings.property_id = properties.id
            WHERE bookings.id = ? AND properties.owner_id = ?
        """, (request_id, session["user_id"])).fetchone()

        if not row:
            return "Request Not Found", 404

        connection.execute("""
            UPDATE bookings
            SET status = 'Rejected'
            WHERE property_id = ?
              AND id <> ?
              AND status = 'Pending'
        """, (row["property_id"], request_id))

        connection.execute("""
            UPDATE bookings
            SET status = 'Accepted'
            WHERE id = ?
        """, (request_id,))

        connection.execute("""
            UPDATE properties
            SET status = 'Rented'
            WHERE id = ?
        """, (row["property_id"],))

        connection.commit()
    finally:
        connection.close()

    return redirect(url_for("owner_requests"))


# =========================
# REJECT RENTAL REQUEST
# =========================

@app.route("/reject-request/<int:request_id>")
@role_required("Owner")
def reject_request(request_id):
    connection = get_db_connection()

    try:
        row = connection.execute("""
            SELECT bookings.id
            FROM bookings
            JOIN properties ON bookings.property_id = properties.id
            WHERE bookings.id = ? AND properties.owner_id = ?
        """, (request_id, session["user_id"])).fetchone()

        if not row:
            return "Request Not Found", 404

        connection.execute("""
            UPDATE bookings
            SET status = 'Rejected'
            WHERE id = ?
        """, (request_id,))

        connection.commit()
    finally:
        connection.close()

    return redirect(url_for("owner_requests"))


# =========================
# MY MAINTENANCE
# =========================

@app.route("/my-maintenance")
@login_required
@role_required("Tenant")
def my_maintenance():
    connection = get_db_connection()

    try:
        maintenance_requests = connection.execute("""
            SELECT
                maintenance_requests.*,
                properties.title,
                properties.location
            FROM maintenance_requests
            LEFT JOIN properties
              ON maintenance_requests.property_id = properties.id
            WHERE maintenance_requests.tenant_id = ?
            ORDER BY maintenance_requests.id DESC
        """, (session["user_id"],)).fetchall()
    finally:
        connection.close()

    return render_template(
        "my_maintenance.html",
        maintenance_requests=maintenance_requests
    )


# =========================
# ADD MAINTENANCE REQUEST
# =========================

@app.route("/add-maintenance", methods=["GET", "POST"])
@login_required
@role_required("Tenant")
def add_maintenance():
    connection = get_db_connection()

    try:
        if request.method == "POST":
            property_id = request.form.get("property_id", type=int)
            problem = request.form.get("problem", "").strip()

            if not property_id or not problem:
                return "Please select a property and describe the problem.", 400

            connection.execute("""
                INSERT INTO maintenance_requests
                    (tenant_id, property_id, problem, status)
                VALUES (?, ?, ?, ?)
            """, (
                session["user_id"], property_id, problem, "Pending"
            ))

            connection.commit()
            return redirect(url_for("my_maintenance"))

        properties_list = connection.execute("""
            SELECT DISTINCT properties.*
            FROM properties
            JOIN bookings ON bookings.property_id = properties.id
            WHERE bookings.user_id = ?
              AND bookings.status = 'Accepted'
            ORDER BY properties.id DESC
        """, (session["user_id"],)).fetchall()

    finally:
        connection.close()

    return render_template(
        "add_maintenance.html",
        properties=properties_list
    )


# =========================
# ADD RENT RECORD
# =========================

@app.route("/add-rent", methods=["GET", "POST"])
@role_required("Owner")
def add_rent():
    connection = get_db_connection()

    try:
        if request.method == "POST":
            tenant_id = request.form.get("tenant_id", type=int)
            property_id = request.form.get("property_id", type=int)
            amount = request.form.get("amount", type=int)
            due_date = request.form.get("due_date", "").strip() or None

            valid = connection.execute("""
                SELECT users.id
                FROM users
                JOIN bookings ON users.id = bookings.user_id
                JOIN properties ON bookings.property_id = properties.id
                WHERE users.id = ?
                  AND properties.id = ?
                  AND properties.owner_id = ?
                  AND bookings.status = 'Accepted'
            """, (tenant_id, property_id, session["user_id"])).fetchone()

            if not valid or not amount:
                return "Invalid tenant, property or amount.", 400

            connection.execute("""
                INSERT INTO rent_records
                    (tenant_id, property_id, amount, due_date, status)
                VALUES (?, ?, ?, ?, 'Pending')
            """, (tenant_id, property_id, amount, due_date))

            connection.commit()
            return redirect(url_for("owner_rent"))

        properties_list = connection.execute("""
            SELECT *
            FROM properties
            WHERE owner_id = ?
            ORDER BY id DESC
        """, (session["user_id"],)).fetchall()

        tenants = connection.execute("""
            SELECT DISTINCT users.id, users.name, users.email
            FROM users
            JOIN bookings ON users.id = bookings.user_id
            JOIN properties ON bookings.property_id = properties.id
            WHERE properties.owner_id = ?
              AND bookings.status = 'Accepted'
            ORDER BY users.name
        """, (session["user_id"],)).fetchall()

    finally:
        connection.close()

    return render_template(
        "add_rent.html",
        properties=properties_list,
        tenants=tenants
    )


# =========================
# OWNER RENT
# =========================

@app.route("/owner-rent")
@role_required("Owner")
def owner_rent():
    connection = get_db_connection()

    try:
        rent_records = connection.execute("""
            SELECT
                rent_records.*,
                users.name AS tenant_name,
                users.email AS tenant_email,
                properties.title AS property_title,
                properties.location AS property_location
            FROM rent_records
            JOIN users ON rent_records.tenant_id = users.id
            JOIN properties ON rent_records.property_id = properties.id
            WHERE properties.owner_id = ?
            ORDER BY rent_records.id DESC
        """, (session["user_id"],)).fetchall()
    finally:
        connection.close()

    return render_template("owner_rent.html", rent_records=rent_records)


# =========================
# EDIT RENT
# =========================

@app.route("/edit-rent/<int:rent_id>", methods=["GET", "POST"])
@role_required("Owner")
def edit_rent(rent_id):
    connection = get_db_connection()

    try:
        rent = connection.execute("""
            SELECT rent_records.*, properties.title AS property_title
            FROM rent_records
            JOIN properties ON rent_records.property_id = properties.id
            WHERE rent_records.id = ?
              AND properties.owner_id = ?
        """, (rent_id, session["user_id"])).fetchone()

        if not rent:
            return "Rent Record Not Found", 404

        if request.method == "POST":
            amount = request.form.get("amount", type=int)
            due_date = request.form.get("due_date", "").strip() or None

            if not amount:
                return "Amount is required.", 400

            connection.execute("""
                UPDATE rent_records
                SET amount = ?, due_date = ?
                WHERE id = ?
            """, (amount, due_date, rent_id))

            connection.commit()
            return redirect(url_for("owner_rent"))

    finally:
        connection.close()

    return render_template("edit_rent.html", rent=rent)


# =========================
# DELETE RENT
# =========================

@app.route("/delete-rent/<int:rent_id>")
@role_required("Owner")
def delete_rent(rent_id):
    connection = get_db_connection()

    try:
        connection.execute("""
            DELETE FROM rent_records
            WHERE id = ?
              AND property_id IN (
                  SELECT id FROM properties WHERE owner_id = ?
              )
        """, (rent_id, session["user_id"]))

        connection.commit()
    finally:
        connection.close()

    return redirect(url_for("owner_rent"))


# =========================
# MARK RENT PAID
# =========================

@app.route("/mark-rent-paid/<int:rent_id>")
@role_required("Owner")
def mark_rent_paid(rent_id):
    connection = get_db_connection()

    try:
        connection.execute("""
            UPDATE rent_records
            SET status = 'Paid', payment_date = CURRENT_TIMESTAMP
            WHERE id = ?
              AND property_id IN (
                  SELECT id FROM properties WHERE owner_id = ?
              )
        """, (rent_id, session["user_id"]))

        connection.commit()
    finally:
        connection.close()

    return redirect(url_for("owner_rent"))


# =========================
# TENANT RENT
# =========================

@app.route("/tenant-rent")
@role_required("Tenant")
def tenant_rent():
    connection = get_db_connection()

    try:
        rent_records = connection.execute("""
            SELECT
                rent_records.*,
                properties.title AS property_title,
                properties.location AS property_location
            FROM rent_records
            JOIN properties ON rent_records.property_id = properties.id
            WHERE rent_records.tenant_id = ?
            ORDER BY rent_records.id DESC
        """, (session["user_id"],)).fetchall()
    finally:
        connection.close()

    return render_template("tenant_rent.html", rent_records=rent_records)


# =========================
# PROFILE
# =========================

@app.route("/profile")
@login_required
def profile():
    return render_template(
        "profile.html",
        name=session["name"],
        email=session.get("email", ""),
        role=session["role"]
    )


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# =========================
# RUN APPLICATION
# =========================

if __name__ == "__main__":
    app.run(debug=True)
