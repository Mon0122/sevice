

from datetime import date
from functools import wraps

import pymysql
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import execute, fetch_all, fetch_one

app = Flask(__name__)
app.secret_key = "serviceflow-classroom-project-key"
app.config["TEMPLATES_AUTO_RELOAD"] = True
STATUSES = ["Pending", "Scheduled", "In Progress", "Completed", "Cancelled"]


@app.before_request
def load_user():
    user_id = session.get("user_id")
    g.user = fetch_one("SELECT * FROM users WHERE id=%s AND active=1", (user_id,)) if user_id else None


@app.context_processor
def shared_values():
    unread = 0
    if g.user:
        unread = fetch_one("SELECT COUNT(*) total FROM notifications WHERE user_id=%s AND is_read=0", (g.user["id"],))["total"]
    return {"current_user": g.user, "unread_count": unread}


def login_required(page):
    @wraps(page)
    def protected(*args, **kwargs):
        return page(*args, **kwargs) if g.user else redirect(url_for("login"))
    return protected


def role_required(role):
    def decorator(page):
        @wraps(page)
        @login_required
        def protected(*args, **kwargs):
            if g.user["role"] != role:
                flash(f"This page is for {role} accounts.", "error")
                return redirect(url_for("dashboard"))
            return page(*args, **kwargs)
        return protected
    return decorator


def visible_request(request_id):
    """Return a job only if the logged-in person is allowed to see it."""
    sql = """SELECT r.*,c.full_name customer_name,c.phone customer_phone,
                    COALESCE(r.service_address,c.address) address,
                    c.latitude customer_latitude,c.longitude customer_longitude,
                    s.name service_name,a.id appointment_id,a.technician_id,
                    a.start_time,a.end_time,t.full_name technician_name
             FROM service_requests r JOIN users c ON c.id=r.customer_id
             JOIN service_types s ON s.id=r.service_type_id
             LEFT JOIN appointments a ON a.request_id=r.id
             LEFT JOIN users t ON t.id=a.technician_id WHERE r.id=%s"""
    values = [request_id]
    if g.user["role"] == "customer":
        sql += " AND r.customer_id=%s"
    else:
        sql += " AND (a.technician_id=%s OR (a.id IS NULL AND r.status='Pending'))"
    values.append(g.user["id"])
    return fetch_one(sql, values)


# ACCOUNT PAGES
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = fetch_one("SELECT * FROM users WHERE username=%s AND active=1", (request.form["username"],))
        if user and check_password_hash(user["password"], request.form["password"]):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html")


@app.route("/create-account", methods=["GET", "POST"])
def create_account():
    if request.method == "POST":
        role = request.form.get("role")
        if role not in ("customer", "technician"):
            flash("Choose Customer or Technician.", "error")
        elif len(request.form["password"]) < 6:
            flash("Password must have at least 6 characters.", "error")
        elif role == "customer" and not request.form.get("address", "").strip():
            flash("Customers must enter their address.", "error")
        else:
            try:
                user_id = execute(
                    """INSERT INTO users(username,password,full_name,role,phone,address,latitude,longitude)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (request.form["username"].strip(), generate_password_hash(request.form["password"]),
                     request.form["full_name"].strip(), role, request.form.get("phone"),
                     request.form.get("address") or None, request.form.get("latitude") or None,
                     request.form.get("longitude") or None),
                )
                session.clear()
                session["user_id"] = user_id
                flash("Account created. Welcome to ServiceFlow!", "success")
                return redirect(url_for("dashboard"))
            except pymysql.err.IntegrityError:
                flash("That username is already being used.", "error")
    return render_template("create_account.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# DASHBOARD
@app.route("/")
@login_required
def dashboard():
    if g.user["role"] == "customer":
        totals = {
            "active": fetch_one("SELECT COUNT(*) total FROM service_requests WHERE customer_id=%s AND status NOT IN ('Completed','Cancelled')", (g.user["id"],))["total"],
            "scheduled": fetch_one("""SELECT COUNT(*) total FROM appointments a
                                      JOIN service_requests r ON r.id=a.request_id
                                      WHERE r.customer_id=%s AND r.status NOT IN ('Completed','Cancelled')""", (g.user["id"],))["total"],
            "completed": fetch_one("SELECT COUNT(*) total FROM service_requests WHERE customer_id=%s AND status='Completed'", (g.user["id"],))["total"],
        }
        jobs = fetch_all("""SELECT r.id,r.status,r.preferred_date,s.name service_name,
                                    t.full_name technician_name,a.start_time
                             FROM service_requests r JOIN service_types s ON s.id=r.service_type_id
                             LEFT JOIN appointments a ON a.request_id=r.id LEFT JOIN users t ON t.id=a.technician_id
                             WHERE r.customer_id=%s ORDER BY r.created_at DESC LIMIT 5""", (g.user["id"],))
        available_jobs = []
    else:
        totals = {
            "today": fetch_one("""SELECT COUNT(*) total FROM appointments a JOIN service_requests r ON r.id=a.request_id
                                   WHERE a.technician_id=%s AND DATE(a.start_time)=CURDATE()
                                   AND r.status!='Cancelled'""", (g.user["id"],))["total"],
            "active": fetch_one("""SELECT COUNT(*) total FROM appointments a JOIN service_requests r ON r.id=a.request_id
                                    WHERE a.technician_id=%s AND r.status NOT IN ('Completed','Cancelled')""", (g.user["id"],))["total"],
            "available": fetch_one("""SELECT COUNT(*) total FROM service_requests r WHERE r.status='Pending'
                                       AND NOT EXISTS(SELECT 1 FROM appointments a WHERE a.request_id=r.id)""")["total"],
        }
        jobs = fetch_all("""SELECT r.id,r.status,c.full_name customer_name,s.name service_name,a.start_time
                             FROM appointments a JOIN service_requests r ON r.id=a.request_id
                             JOIN users c ON c.id=r.customer_id JOIN service_types s ON s.id=r.service_type_id
                             WHERE a.technician_id=%s AND r.status NOT IN ('Completed','Cancelled')
                             ORDER BY a.start_time ASC LIMIT 5""", (g.user["id"],))
        available_jobs = fetch_all("""SELECT r.id,r.preferred_date,c.full_name customer_name,
                                             COALESCE(r.service_address,c.address) address,
                                             s.name service_name
                                      FROM service_requests r JOIN users c ON c.id=r.customer_id
                                      JOIN service_types s ON s.id=r.service_type_id
                                      LEFT JOIN appointments a ON a.request_id=r.id
                                      WHERE r.status='Pending' AND a.id IS NULL
                                      ORDER BY r.created_at ASC LIMIT 5""")
    return render_template("dashboard.html", totals=totals, jobs=jobs, available_jobs=available_jobs)


# SERVICE REQUESTS
@app.route("/requests")
@login_required
def requests_page():
    sql = """SELECT r.*,c.full_name customer_name,s.name service_name,
                    a.technician_id,t.full_name technician_name,a.start_time
             FROM service_requests r JOIN users c ON c.id=r.customer_id
             JOIN service_types s ON s.id=r.service_type_id
             LEFT JOIN appointments a ON a.request_id=r.id LEFT JOIN users t ON t.id=a.technician_id WHERE """
    if g.user["role"] == "customer":
        sql += "r.customer_id=%s"
        values = (g.user["id"],)
        view_mode = "mine"
        technician_counts = None
    else:
        view_mode = request.args.get("view", "available")
        if view_mode == "mine":
            sql += "a.technician_id=%s"
            values = (g.user["id"],)
        else:
            view_mode = "available"
            sql += "a.id IS NULL AND r.status='Pending'"
            values = ()
        technician_counts = {
            "available": fetch_one("""SELECT COUNT(*) total FROM service_requests r
                                       LEFT JOIN appointments a ON a.request_id=r.id
                                       WHERE r.status='Pending' AND a.id IS NULL""")["total"],
            "mine": fetch_one("SELECT COUNT(*) total FROM appointments WHERE technician_id=%s", (g.user["id"],))["total"],
        }
    rows = fetch_all(sql + " ORDER BY r.created_at DESC", values)
    return render_template("requests.html", rows=rows, view_mode=view_mode, technician_counts=technician_counts)

@app.route("/requests/new", methods=["GET", "POST"])
@role_required("customer")
def request_new():

    if request.method == "POST":

        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")
        location_accuracy = request.form.get("location_accuracy")

        # Require the customer to add the service location
        if not latitude or not longitude:
            flash(
                "Please add your current service location before sending the request.",
                "error"
            )

            return render_template(
                "request_form.html",
                service_types=fetch_all(
                    "SELECT * FROM service_types ORDER BY name"
                )
            )

        try:
            latitude = float(latitude)
            longitude = float(longitude)

            if not (-90 <= latitude <= 90):
                raise ValueError

            if not (-180 <= longitude <= 180):
                raise ValueError

        except (TypeError, ValueError):

            flash(
                "The service location is invalid. Please get your location again.",
                "error"
            )

            return render_template(
                "request_form.html",
                service_types=fetch_all(
                    "SELECT * FROM service_types ORDER BY name"
                )
            )


        request_id = execute(
            """
            INSERT INTO service_requests(
                customer_id,
                service_type_id,
                description,
                service_address,
                preferred_date,
                latitude,
                longitude,
                location_accuracy
            )
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                g.user["id"],
                request.form["service_type_id"],
                request.form.get("description"),
                request.form.get("service_address", "").strip() or g.user["address"],
                request.form.get("preferred_date") or None,
                latitude,
                longitude,
                location_accuracy or None
            )
        )


        execute(
            """
            INSERT INTO status_history(
                request_id,
                status,
                note,
                changed_by
            )
            VALUES(%s,'Pending','Request created',%s)
            """,
            (
                request_id,
                g.user["id"]
            )
        )


        flash(
            "Your service request was created.",
            "success"
        )

        return redirect(
            url_for(
                "request_detail",
                request_id=request_id
            )
        )


    return render_template(
        "request_form.html",
        service_types=fetch_all(
            "SELECT * FROM service_types ORDER BY name"
        )
    )


@app.route("/requests/<int:request_id>")
@login_required
def request_detail(request_id):
    item = visible_request(request_id)
    if not item:
        flash("Request not found or not available to you.", "error")
        return redirect(url_for("requests_page"))
    history = fetch_all("""SELECT h.*,u.full_name changed_by_name FROM status_history h
                           JOIN users u ON u.id=h.changed_by WHERE request_id=%s ORDER BY created_at DESC""", (request_id,))
    return render_template("request_detail.html", item=item, history=history, statuses=STATUSES)


@app.route("/requests/<int:request_id>/accept", methods=["GET", "POST"])
@role_required("technician")
def accept_request(request_id):
    item = visible_request(request_id)
    if not item or item["appointment_id"]:
        flash("This request has already been accepted.", "error")
        return redirect(url_for("requests_page"))
    if request.method == "POST":
        start, end = request.form["start_time"], request.form["end_time"]
        conflict = fetch_one("SELECT id FROM appointments WHERE technician_id=%s AND start_time<%s AND end_time>%s", (g.user["id"], end, start))
        if end <= start:
            flash("End time must be after start time.", "error")
        elif conflict:
            flash("You already have a job at that time.", "error")
        else:
            execute("INSERT INTO appointments(request_id,technician_id,start_time,end_time,notes) VALUES(%s,%s,%s,%s,%s)", (request_id, g.user["id"], start, end, request.form.get("notes")))
            execute("UPDATE service_requests SET status='Scheduled' WHERE id=%s", (request_id,))
            execute("INSERT INTO status_history(request_id,status,note,changed_by) VALUES(%s,'Scheduled','Accepted by technician',%s)", (request_id, g.user["id"]))
            execute("INSERT INTO notifications(user_id,message,link) VALUES(%s,%s,%s)", (item["customer_id"], f"{g.user['full_name']} accepted request #{request_id}.", url_for("request_detail", request_id=request_id)))
            flash("Job accepted and added to your schedule.", "success")
            return redirect(url_for("request_detail", request_id=request_id))
    return render_template("accept_request.html", item=item)


@app.post("/requests/<int:request_id>/status")
@role_required("technician")
def request_status(request_id):
    item = visible_request(request_id)
    status = request.form.get("status")
    if not item or item["technician_id"] != g.user["id"] or status not in STATUSES:
        flash("You cannot update that request.", "error")
        return redirect(url_for("requests_page"))
    execute("UPDATE service_requests SET status=%s WHERE id=%s", (status, request_id))
    execute("INSERT INTO status_history(request_id,status,note,changed_by) VALUES(%s,%s,%s,%s)", (request_id, status, request.form.get("note"), g.user["id"]))
    execute("INSERT INTO notifications(user_id,message,link) VALUES(%s,%s,%s)", (item["customer_id"], f"Request #{request_id} is now {status}.", url_for("request_detail", request_id=request_id)))
    flash("Job status updated.", "success")
    return redirect(url_for("request_detail", request_id=request_id))


# SCHEDULE, NOTIFICATIONS, MAP, AND GPS
@app.route("/schedule")
@login_required
def schedule():
    selected = request.args.get("date", date.today().isoformat())
    sql = """SELECT a.*,r.status,c.full_name customer_name,
                    COALESCE(r.service_address,c.address) address,
                    s.name service_name,t.full_name technician_name
             FROM appointments a JOIN service_requests r ON r.id=a.request_id
             JOIN users c ON c.id=r.customer_id JOIN service_types s ON s.id=r.service_type_id
             JOIN users t ON t.id=a.technician_id WHERE DATE(a.start_time)=%s AND """
    sql += "r.customer_id=%s" if g.user["role"] == "customer" else "a.technician_id=%s"
    rows = fetch_all(sql + " ORDER BY a.start_time", (selected, g.user["id"]))
    return render_template("schedule.html", rows=rows, selected=selected)


@app.route("/notifications")
@login_required
def notifications():
    rows = fetch_all("SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 50", (g.user["id"],))
    execute("UPDATE notifications SET is_read=1 WHERE user_id=%s", (g.user["id"],))
    return render_template("notifications.html", rows=rows)

@app.route("/map")
@login_required
def live_map():
    selected_request = request.args.get("request", type=int)
    customers = []

    if g.user["role"] == "customer":
        sql = """SELECT r.id request_id,u.full_name name,
                        COALESCE(r.service_address,u.address) address,
                        COALESCE(r.latitude,u.latitude) latitude,
                        COALESCE(r.longitude,u.longitude) longitude,
                        r.location_accuracy,r.status,s.name service_name,a.start_time,
                        t.full_name technician_name
                 FROM service_requests r JOIN users u ON u.id=r.customer_id
                 JOIN service_types s ON s.id=r.service_type_id
                 LEFT JOIN appointments a ON a.request_id=r.id
                 LEFT JOIN users t ON t.id=a.technician_id
                 WHERE r.customer_id=%s AND r.status NOT IN ('Completed','Cancelled')
                   AND COALESCE(r.latitude,u.latitude) IS NOT NULL
                   AND COALESCE(r.longitude,u.longitude) IS NOT NULL"""
        values = [g.user["id"]]
        if selected_request:
            sql += " AND r.id=%s"
            values.append(selected_request)
        customers = fetch_all(sql + " ORDER BY (a.id IS NULL),r.created_at DESC", values)
    else:
        sql = """SELECT DISTINCT r.id request_id,c.full_name name,
                        COALESCE(r.service_address,c.address) address,
                        COALESCE(r.latitude,c.latitude) latitude,
                        COALESCE(r.longitude,c.longitude) longitude,
                        r.location_accuracy,r.status,s.name service_name,a.start_time
                 FROM appointments a JOIN service_requests r ON r.id=a.request_id
                 JOIN users c ON c.id=r.customer_id
                 JOIN service_types s ON s.id=r.service_type_id
                 WHERE a.technician_id=%s AND r.status IN ('Scheduled','In Progress')
                   AND COALESCE(r.latitude,c.latitude) IS NOT NULL
                   AND COALESCE(r.longitude,c.longitude) IS NOT NULL"""
        values = [g.user["id"]]
        if selected_request:
            sql += " AND r.id=%s"
            values.append(selected_request)
        customers = fetch_all(sql + " ORDER BY a.start_time", values)

    for customer in customers:
        customer["latitude"] = float(customer["latitude"])
        customer["longitude"] = float(customer["longitude"])
        if customer["location_accuracy"] is not None:
            customer["location_accuracy"] = float(customer["location_accuracy"])

    return render_template("map.html", customers=customers, selected_request=selected_request)


@app.route("/share-location")
@role_required("technician")
def share_location():
    return redirect(url_for("live_map"))


@app.post("/api/customer-location")
@role_required("customer")
def customer_location_api():
    data = request.get_json(silent=True) or {}
    try:
        request_id = int(data["request_id"])
        latitude = float(data["latitude"])
        longitude = float(data["longitude"])
        accuracy = float(data["accuracy"]) if data.get("accuracy") is not None else None
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify(error="Invalid location details"), 400

    item = fetch_one("""SELECT id FROM service_requests
                        WHERE id=%s AND customer_id=%s
                          AND status NOT IN ('Completed','Cancelled')""",
                     (request_id, g.user["id"]))
    if not item:
        return jsonify(error="This service request cannot be changed"), 403

    address = str(data.get("address", "")).strip()
    if not address:
        return jsonify(error="Enter the service address"), 400

    execute("""UPDATE service_requests
               SET service_address=%s,latitude=%s,longitude=%s,location_accuracy=%s
               WHERE id=%s""", (address, latitude, longitude, accuracy, request_id))
    return jsonify(saved=True, address=address, latitude=latitude, longitude=longitude)


@app.post("/api/sharing")
@role_required("technician")
def sharing_api():
    enabled = bool((request.get_json(silent=True) or {}).get("enabled"))
    execute("UPDATE users SET sharing_location=%s WHERE id=%s", (enabled, g.user["id"]))
    return jsonify(enabled=enabled)


@app.post("/api/location")
@role_required("technician")
def location_api():
    if not fetch_one("SELECT sharing_location FROM users WHERE id=%s", (g.user["id"],))["sharing_location"]:
        return jsonify(error="Location sharing is off"), 403
    data = request.get_json(silent=True) or {}
    try:
        latitude, longitude = float(data["latitude"]), float(data["longitude"])
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify(error="Invalid coordinates"), 400
    execute("INSERT INTO technician_locations(technician_id,latitude,longitude,accuracy) VALUES(%s,%s,%s,%s)", (g.user["id"], latitude, longitude, data.get("accuracy")))
    return jsonify(saved=True)


@app.get("/api/locations")
@login_required
def locations_api():
    if g.user["role"] == "customer":
        sql = """SELECT u.id,u.full_name name,l.latitude,l.longitude,l.accuracy,l.recorded_at,
                        GROUP_CONCAT(DISTINCT r.id ORDER BY r.id) request_ids
                 FROM appointments a JOIN service_requests r ON r.id=a.request_id
                 JOIN users u ON u.id=a.technician_id
                 JOIN technician_locations l ON l.id=(SELECT id FROM technician_locations
                     WHERE technician_id=u.id ORDER BY recorded_at DESC LIMIT 1)
                 WHERE r.customer_id=%s AND r.status IN ('Scheduled','In Progress')
                   AND u.role='technician' AND u.sharing_location=1
                   AND l.recorded_at >= NOW() - INTERVAL 2 MINUTE
                 GROUP BY u.id,u.full_name,l.latitude,l.longitude,l.accuracy,l.recorded_at"""
        values = (g.user["id"],)
    else:
        sql = """SELECT u.id,u.full_name name,l.latitude,l.longitude,l.accuracy,l.recorded_at
                 FROM users u JOIN technician_locations l ON l.id=(SELECT id FROM technician_locations
                     WHERE technician_id=u.id ORDER BY recorded_at DESC LIMIT 1)
                 WHERE u.id=%s AND u.role='technician' AND u.sharing_location=1
                   AND l.recorded_at >= NOW() - INTERVAL 2 MINUTE"""
        values = (g.user["id"],)
    rows = fetch_all(sql, values)
    for row in rows:
        row["latitude"], row["longitude"] = float(row["latitude"]), float(row["longitude"])
        row["accuracy"] = float(row["accuracy"]) if row["accuracy"] is not None else None
        row["recorded_at"] = row["recorded_at"].isoformat()
        if row.get("request_ids"):
            row["request_ids"] = [int(value) for value in row["request_ids"].split(",")]
    return jsonify(technicians=rows)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
