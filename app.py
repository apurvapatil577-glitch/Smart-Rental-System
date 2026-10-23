from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.utils import secure_filename
import os
from functools import wraps

from database import get_db_connection, create_tables


# =========================
# FLASK APP
# =========================

app = Flask(__name__)

app.secret_key = "rentnest_secret_key"

UPLOAD_FOLDER = "static/uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


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
# CREATE BOOKINGS TABLE
# =========================

connection = get_db_connection()

connection.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        property_id INTEGER,
        status TEXT DEFAULT 'Pending',
        request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
# =========================
# CREATE MAINTENANCE TABLE
# =========================

connection.execute("""
    CREATE TABLE IF NOT EXISTS maintenance_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER,
        property_id INTEGER,
        problem TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

connection.commit()
connection.close()



# =========================
# HOME PAGE
# =========================

@app.route("/")
def home():

    return render_template("index.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

# =========================
# PROPERTIES PAGE
# =========================

@app.route("/properties")
def properties():
    search = request.args.get("search", "").strip()
    property_type = request.args.get("type", "").strip()
    max_rent = request.args.get("max_rent", "").strip()

    connection = get_db_connection()
    query = "SELECT * FROM properties WHERE 1=1"
    params = []

    if search:
        query += " AND (title LIKE ? OR location LIKE ? OR facilities LIKE ?)"
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
    properties_list = connection.execute(query, params).fetchall()
    types = connection.execute("SELECT DISTINCT property_type FROM properties ORDER BY property_type").fetchall()
    connection.close()

    return render_template("properties.html", properties=properties_list, property_types=types, search=search, selected_type=property_type, max_rent=max_rent)

# =========================
# PROPERTY DETAILS
# =========================

@app.route("/property/<int:property_id>")
def property_details(property_id):

    connection = get_db_connection()

    property_data = connection.execute("""
        SELECT *
        FROM properties
        WHERE id = ?
    """, (property_id,)).fetchone()

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

        name = request.form["name"]

        email = request.form["email"].strip().lower()

        password = request.form["password"]

        role = request.form["role"]

        connection = get_db_connection()

        try:

            existing_user = connection.execute(
                """
                SELECT id
                FROM users
                WHERE LOWER(email) = ?
                """,
                (email,)
            ).fetchone()

            if existing_user:

                connection.close()

                return """
                <div style="
                    font-family:Arial;
                    text-align:center;
                    margin-top:100px;
                ">

                    <h1 style="color:#dc2626;">
                        ❌ Email Already Registered
                    </h1>

                    <p>
                        This email is already registered.
                    </p>

                    <br>

                    <a href="/register">
                        Try Again
                    </a>

                </div>
                """

            connection.execute(
                """
                INSERT INTO users
                (name, email, password, role)
                VALUES (?, ?, ?, ?)
                """,
                (name, email, password, role)
            )

            connection.commit()

        except Exception as error:

            connection.close()

            return f"""
            <div style="
                font-family:Arial;
                text-align:center;
                margin-top:100px;
            ">

                <h1 style="color:#dc2626;">
                    ❌ Registration Failed
                </h1>

                <p>
                    {error}
                </p>

                <br>

                <a href="/register">
                    Try Again
                </a>

            </div>
            """

        connection.close()

        return """
        <div style="
            font-family:Arial;
            text-align:center;
            margin-top:100px;
        ">

            <h1 style="color:#0f766e;">
                🎉 Registration Successful!
            </h1>

            <p>
                Your RentNest account has been created.
            </p>

            <br>

            <a href="/login"
               style="
               padding:12px 25px;
               background:#0f766e;
               color:white;
               text-decoration:none;
               border-radius:8px;
               ">

                Login Now

            </a>

        </div>
        """

    return render_template("register.html")


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        connection = get_db_connection()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE LOWER(email) = ?
            AND password = ?
            """,
            (email, password)
        ).fetchone()

        connection.close()

        # =========================
        # USER FOUND
        # =========================

        if user:

            session["user_id"] = user["id"]

            session["name"] = user["name"]

            session["role"] = user["role"]

            session["email"] = user["email"]

            # OWNER

            if user["role"] == "Owner":

                return redirect(
                    url_for("owner_dashboard")
                )

            # TENANT

            else:

                return redirect(
                    url_for("tenant_dashboard")
                )

        # =========================
        # LOGIN FAILED
        # =========================

        return """
        <div style="
            font-family:Arial;
            text-align:center;
            margin-top:100px;
        ">

            <h1 style="color:#dc2626;">
                ❌ Login Failed
            </h1>

            <p>
                Invalid email or password.
            </p>

            <br>

            <a href="/login">
                Try Again
            </a>

        </div>
        """

    return render_template("login.html")


# =========================
# TENANT DASHBOARD
# =========================

@app.route("/tenant-dashboard")
def tenant_dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    bookings = connection.execute(
        """
        SELECT *
        FROM bookings
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

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
def owner_dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "Owner":

        return redirect(
            url_for("login")
        )

    return render_template(
        "owner_dashboard.html",
        name=session["name"]
    )


# =========================
# ADD PROPERTY
# =========================

@app.route("/add-property", methods=["GET", "POST"])
def add_property():

    # Login check

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    # Owner check

    if session.get("role") != "Owner":

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        title = request.form["title"]

        property_type = request.form["property_type"]

        location = request.form["location"]

        rent = request.form["rent"]

        deposit = request.form["deposit"]

        facilities = request.form["facilities"]

        # =========================
        # PROPERTY IMAGE
        # =========================

        image = request.files.get("image")

        image_filename = ""

        if image and image.filename:

            image_filename = secure_filename(
                image.filename
            )

            image.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    image_filename
                )
            )

        # =========================
        # SAVE PROPERTY
        # =========================

        connection = get_db_connection()

        connection.execute(
            """
            INSERT INTO properties
            (
                owner_id,
                title,
                property_type,
                location,
                rent,
                deposit,
                facilities,
                image,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                title,
                property_type,
                location,
                rent,
                deposit,
                facilities,
                image_filename,
                "Available"
            )
        )

        connection.commit()

        connection.close()

        return redirect(
            url_for("owner_properties")
        )

    return render_template(
        "add_property.html"
    )


# =========================
# OWNER PROPERTIES
# =========================

@app.route("/owner-properties")
def owner_properties():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "Owner":
        return redirect(url_for("login"))

    connection = get_db_connection()

    properties_list = connection.execute("""
        SELECT *
        FROM properties
        WHERE owner_id = ?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()

    connection.close()

    return render_template(
        "owner_properties.html",
        properties=properties_list
    )
# =========================
# EDIT PROPERTY
# =========================

@app.route("/edit-property/<int:property_id>", methods=["GET", "POST"])
def edit_property(property_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "Owner":
        return redirect(url_for("login"))

    connection = get_db_connection()

    property_data = connection.execute("""
        SELECT *
        FROM properties
        WHERE id = ?
        AND owner_id = ?
    """, (property_id, session["user_id"])).fetchone()

    if not property_data:
        connection.close()
        return "Property Not Found", 404

    if request.method == "POST":

        title = request.form["title"]
        property_type = request.form["property_type"]
        location = request.form["location"]
        rent = request.form["rent"]
        deposit = request.form["deposit"]
        facilities = request.form["facilities"]

        connection.execute("""
            UPDATE properties
            SET title = ?,
                property_type = ?,
                location = ?,
                rent = ?,
                deposit = ?,
                facilities = ?
            WHERE id = ?
            AND owner_id = ?
        """, (
            title,
            property_type,
            location,
            rent,
            deposit,
            facilities,
            property_id,
            session["user_id"]
        ))

        connection.commit()
        connection.close()

        return redirect(url_for("owner_properties"))

    connection.close()

    return render_template(
        "edit_property.html",
        property=property_data
    )


# =========================
# DELETE PROPERTY
# =========================

@app.route("/delete-property/<int:property_id>")
def delete_property(property_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "Owner":
        return redirect(url_for("login"))

    connection = get_db_connection()

    connection.execute("""
        DELETE FROM properties
        WHERE id = ?
        AND owner_id = ?
    """, (
        property_id,
        session["user_id"]
    ))

    connection.commit()
    connection.close()

    return redirect(url_for("owner_properties"))


# =========================
# SEND RENTAL REQUEST
# =========================

@app.route("/request-rental/<int:property_id>")
@role_required("Tenant")
def request_rental(property_id):
    connection = get_db_connection()
    property_data = connection.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    if not property_data:
        connection.close()
        return "Property Not Found", 404
    if property_data["status"] != "Available":
        connection.close()
        return "This property is not available for rent.", 400

    existing = connection.execute("SELECT * FROM bookings WHERE user_id = ? AND property_id = ? AND status IN ('Pending','Accepted')", (session["user_id"], property_id)).fetchone()
    if existing:
        connection.close()
        return redirect(url_for("my_booking"))

    connection.execute("INSERT INTO bookings (user_id, property_id, status) VALUES (?, ?, 'Pending')", (session["user_id"], property_id))
    connection.commit()
    connection.close()
    return redirect(url_for("my_booking"))

# =========================
# MY BOOKING
# =========================

@app.route("/my-booking")
def my_booking():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    bookings = connection.execute(
        """
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
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "my_booking.html",
        bookings=bookings
    )

# =========================
# TENANT MAINTENANCE
# =========================

@app.route("/maintenance/<int:property_id>", methods=["GET", "POST"])
def maintenance(property_id):

    # Login check
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Tenant check
    if session.get("role") != "Tenant":
        return redirect(url_for("login"))

    connection = get_db_connection()

    # Property check
    property_data = connection.execute(
        """
        SELECT *
        FROM properties
        WHERE id = ?
        """,
        (property_id,)
    ).fetchone()

    if not property_data:

        connection.close()

        return "Property Not Found", 404

    # =========================
    # SUBMIT MAINTENANCE
    # =========================

    if request.method == "POST":

        problem = request.form["problem"]

        connection.execute(
            """
            INSERT INTO maintenance_requests
            (tenant_id, property_id, problem, status)
            VALUES (?, ?, ?, ?)
            """,
            (
                session["user_id"],
                property_id,
                problem,
                "Pending"
            )
        )

        connection.commit()
        connection.close()

        return redirect(
            url_for("my_maintenance")
        )

    connection.close()

    return render_template(
        "maintenance.html",
        property=property_data
    )

# =========================
# OWNER MAINTENANCE
# =========================

@app.route("/owner-maintenance")
def owner_maintenance():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "Owner":
        return redirect(url_for("login"))

    connection = get_db_connection()

    maintenance_requests = connection.execute(
        """
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
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "owner_maintenance.html",
        maintenance_requests=maintenance_requests
    )

# =========================
# UPDATE MAINTENANCE STATUS
# =========================

@app.route("/update-maintenance/<int:request_id>/<status>")
def update_maintenance(request_id, status):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "Owner":
        return redirect(url_for("login"))

    allowed_status = [
        "Pending",
        "In Progress",
        "Completed"
    ]

    if status not in allowed_status:
        return "Invalid Status", 400

    connection = get_db_connection()

    request_data = connection.execute(
        """
        SELECT maintenance_requests.id

        FROM maintenance_requests

        JOIN properties
        ON maintenance_requests.property_id = properties.id

        WHERE maintenance_requests.id = ?

        AND properties.owner_id = ?
        """,
        (
            request_id,
            session["user_id"]
        )
    ).fetchone()

    if not request_data:

        connection.close()

        return "Maintenance Request Not Found", 404

    connection.execute(
        """
        UPDATE maintenance_requests
        SET status = ?
        WHERE id = ?
        """,
        (
            status,
            request_id
        )
    )

    connection.commit()
    connection.close()

    return redirect(
        url_for("owner_maintenance")
    )


# =========================
# OWNER RENTAL REQUESTS
# =========================

@app.route("/owner-requests")
def owner_requests():

    # Login check

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    # Owner check

    if session.get("role") != "Owner":

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    requests = connection.execute(
        """
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

        JOIN users
        ON bookings.user_id = users.id

        JOIN properties
        ON bookings.property_id = properties.id

        WHERE properties.owner_id = ?

        ORDER BY bookings.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "owner_requests.html",
        requests=requests
    )


# =========================
# ACCEPT RENTAL REQUEST
# =========================

@app.route("/accept-request/<int:request_id>")
@role_required("Owner")
def accept_request(request_id):
    connection = get_db_connection()
    row = connection.execute("""
        SELECT bookings.id, bookings.property_id
        FROM bookings JOIN properties ON bookings.property_id = properties.id
        WHERE bookings.id = ? AND properties.owner_id = ?
    """, (request_id, session["user_id"])).fetchone()
    if not row:
        connection.close(); return "Request Not Found", 404
    connection.execute("UPDATE bookings SET status='Rejected' WHERE property_id=? AND id<>? AND status='Pending'", (row["property_id"], request_id))
    connection.execute("UPDATE bookings SET status='Accepted' WHERE id=?", (request_id,))
    connection.execute("UPDATE properties SET status='Rented' WHERE id=?", (row["property_id"],))
    connection.commit(); connection.close()
    return redirect(url_for("owner_requests"))


@app.route("/reject-request/<int:request_id>")
@role_required("Owner")
def reject_request(request_id):
    connection = get_db_connection()
    row = connection.execute("""
        SELECT bookings.id, bookings.property_id
        FROM bookings JOIN properties ON bookings.property_id = properties.id
        WHERE bookings.id = ? AND properties.owner_id = ?
    """, (request_id, session["user_id"])).fetchone()
    if not row:
        connection.close(); return "Request Not Found", 404
    connection.execute("UPDATE bookings SET status='Rejected' WHERE id=?", (request_id,))
    connection.commit(); connection.close()
    return redirect(url_for("owner_requests"))

# =========================
# MY MAINTENANCE
# =========================

@app.route("/my-maintenance")
def my_maintenance():

    # Login check
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Tenant check
    if session.get("role") != "Tenant":
        return redirect(url_for("login"))

    connection = get_db_connection()

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

    connection.close()

    return render_template(
        "my_maintenance.html",
        maintenance_requests=maintenance_requests
    )


# =========================
# ADD MAINTENANCE REQUEST
# =========================

@app.route("/add-maintenance", methods=["GET", "POST"])
def add_maintenance():

    # Login check
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Tenant check
    if session.get("role") != "Tenant":
        return redirect(url_for("login"))

    if request.method == "POST":

        property_id = request.form["property_id"]

        problem = request.form["problem"]

        connection = get_db_connection()

        connection.execute("""
            INSERT INTO maintenance_requests
            (tenant_id, property_id, problem, status)
            VALUES (?, ?, ?, ?)
        """, (
            session["user_id"],
            property_id,
            problem,
            "Pending"
        ))

        connection.commit()

        connection.close()

        return redirect(
            url_for("my_maintenance")
        )

    connection = get_db_connection()

    properties_list = connection.execute("""
        SELECT DISTINCT properties.*
        FROM properties
        JOIN bookings ON bookings.property_id = properties.id
        WHERE bookings.user_id = ?
          AND bookings.status = 'Accepted'
        ORDER BY properties.id DESC
    """, (session["user_id"],)).fetchall()

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
    if request.method == "POST":
        tenant_id = request.form.get("tenant_id", type=int)
        property_id = request.form.get("property_id", type=int)
        amount = request.form.get("amount", type=int)
        due_date = request.form.get("due_date", "").strip()
        valid = connection.execute("""SELECT users.id FROM users JOIN bookings ON users.id=bookings.user_id JOIN properties ON bookings.property_id=properties.id WHERE users.id=? AND properties.id=? AND properties.owner_id=? AND bookings.status='Accepted'""", (tenant_id, property_id, session["user_id"])).fetchone()
        if not valid or not amount:
            connection.close(); return "Invalid tenant, property or amount.", 400
        connection.execute("INSERT INTO rent_records (tenant_id, property_id, amount, due_date, status) VALUES (?, ?, ?, ?, 'Pending')", (tenant_id, property_id, amount, due_date))
        connection.commit(); connection.close()
        return redirect(url_for("owner_rent"))
    properties_list = connection.execute("SELECT * FROM properties WHERE owner_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
    tenants = connection.execute("""SELECT DISTINCT users.id, users.name, users.email FROM users JOIN bookings ON users.id=bookings.user_id JOIN properties ON bookings.property_id=properties.id WHERE properties.owner_id=? AND bookings.status='Accepted' ORDER BY users.name""", (session["user_id"],)).fetchall()
    connection.close()
    return render_template("add_rent.html", properties=properties_list, tenants=tenants)


@app.route("/owner-rent")
@role_required("Owner")
def owner_rent():
    connection = get_db_connection()
    rent_records = connection.execute("""
        SELECT rent_records.*, users.name AS tenant_name, users.email AS tenant_email, properties.title AS property_title, properties.location AS property_location
        FROM rent_records JOIN users ON rent_records.tenant_id=users.id JOIN properties ON rent_records.property_id=properties.id
        WHERE properties.owner_id=? ORDER BY rent_records.id DESC
    """, (session["user_id"],)).fetchall()
    connection.close()
    return render_template("owner_rent.html", rent_records=rent_records)


@app.route("/edit-rent/<int:rent_id>", methods=["GET", "POST"])
@role_required("Owner")
def edit_rent(rent_id):
    connection = get_db_connection()
    rent = connection.execute("""SELECT rent_records.*, properties.title AS property_title FROM rent_records JOIN properties ON rent_records.property_id=properties.id WHERE rent_records.id=? AND properties.owner_id=?""", (rent_id, session["user_id"])).fetchone()
    if not rent:
        connection.close(); return "Rent Record Not Found", 404
    if request.method == "POST":
        amount = request.form.get("amount", type=int)
        due_date = request.form.get("due_date", "").strip()
        if not amount:
            connection.close(); return "Amount is required.", 400
        connection.execute("UPDATE rent_records SET amount=?, due_date=? WHERE id=?", (amount, due_date, rent_id))
        connection.commit(); connection.close()
        return redirect(url_for("owner_rent"))
    connection.close()
    return render_template("edit_rent.html", rent=rent)


@app.route("/delete-rent/<int:rent_id>")
@role_required("Owner")
def delete_rent(rent_id):
    connection = get_db_connection()
    connection.execute("DELETE FROM rent_records WHERE id=? AND property_id IN (SELECT id FROM properties WHERE owner_id=?)", (rent_id, session["user_id"]))
    connection.commit(); connection.close()
    return redirect(url_for("owner_rent"))


@app.route("/mark-rent-paid/<int:rent_id>")
@role_required("Owner")
def mark_rent_paid(rent_id):
    connection = get_db_connection()
    connection.execute("UPDATE rent_records SET status='Paid', payment_date=CURRENT_TIMESTAMP WHERE id=? AND property_id IN (SELECT id FROM properties WHERE owner_id=?)", (rent_id, session["user_id"]))
    connection.commit(); connection.close()
    return redirect(url_for("owner_rent"))


@app.route("/tenant-rent")
@role_required("Tenant")
def tenant_rent():
    connection = get_db_connection()
    rent_records = connection.execute("""SELECT rent_records.*, properties.title AS property_title, properties.location AS property_location FROM rent_records JOIN properties ON rent_records.property_id=properties.id WHERE rent_records.tenant_id=? ORDER BY rent_records.id DESC""", (session["user_id"],)).fetchall()
    connection.close()
    return render_template("tenant_rent.html", rent_records=rent_records)

# =========================
# MY PROFILE
# =========================

@app.route("/profile")
def profile():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

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

    return redirect(
        url_for("home")
    )


# =========================
# RUN APPLICATION
# =========================

if __name__ == "__main__":

    app.run(debug=True)