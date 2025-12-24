from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import uuid
import requests
from config import FIREBASE_WEB_API_KEY  # 🔑 IMPORTANT

# ======================
# FLASK INIT
# ======================
app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# ======================
# FIREBASE ADMIN INIT
# ======================
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ======================
# LOGIN ROUTE (SECURE)
# ======================
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        try:
            # 🔐 VERIFY EMAIL + PASSWORD USING FIREBASE AUTH REST API
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
            response = requests.post(url, json=payload)
            data = response.json()

            if "error" in data:
                return render_template("login.html", error="Invalid email or password")

            uid = data["localId"]

            # 🔎 CHECK ROLE FROM FIRESTORE
            user_doc = db.collection("users").document(uid).get()
            if not user_doc.exists:
                return render_template("login.html", error="User not registered")

            if user_doc.to_dict().get("role") != role:
                return render_template("login.html", error="Invalid role selected")

            # ✅ LOGIN SUCCESS
            session["user_id"] = uid
            session["role"] = role
            return redirect(
                url_for("admin_dashboard") if role == "admin" else url_for("staff_dashboard")
            )
        except Exception as e:
            print("LOGIN ERROR:", e)
            return render_template("login.html", error="Login failed")

    return render_template("login.html")

# ======================
# DASHBOARDS (PROTECTED)
# ======================
@app.route("/admin_dashboard")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    return render_template("admin_dashboard.html")

@app.route("/staff_dashboard")
def staff_dashboard():
    if session.get("role") != "staff":
        return redirect(url_for("login"))
    return render_template("staff_dashboard.html")

# ======================
# STAFF MANAGEMENT
# ======================
@app.route("/staff_management")
def staff_management():
    return render_template("staff_management.html")

@app.route("/staff/get_all")
def get_all_staff():
    staff_docs = db.collection("staff").stream()
    return jsonify([{"id": doc.id, **doc.to_dict()} for doc in staff_docs])

@app.route("/staff/add", methods=["POST"])
def add_staff():
    staff_id = str(uuid.uuid4())
    db.collection("staff").document(staff_id).set(request.json)
    return jsonify({"status": "success"})

@app.route("/staff/update/<staff_id>", methods=["PUT"])
def update_staff(staff_id):
    db.collection("staff").document(staff_id).update(request.json)
    return jsonify({"status": "success"})

@app.route("/staff/delete/<staff_id>", methods=["DELETE"])
def delete_staff(staff_id):
    db.collection("staff").document(staff_id).delete()
    return jsonify({"status": "success"})

# ======================
# PATIENT MANAGEMENT
# ======================
@app.route("/patient_management")
def patient_management():
    return render_template("patient_management.html")

@app.route("/patient/get_all")
def get_all_patients():
    patients = db.collection("patients").stream()
    return jsonify([{"id": doc.id, **doc.to_dict()} for doc in patients])

@app.route("/patient/add", methods=["POST"])
def add_patient():
    patient_id = str(uuid.uuid4())
    db.collection("patients").document(patient_id).set(request.json)
    return jsonify({"status": "success"})

@app.route("/patient/update/<patient_id>", methods=["PUT"])
def update_patient(patient_id):
    db.collection("patients").document(patient_id).update(request.json)
    return jsonify({"status": "success"})

@app.route("/patient/delete/<patient_id>", methods=["DELETE"])
def delete_patient(patient_id):
    db.collection("patients").document(patient_id).delete()
    return jsonify({"status": "success"})

# ======================
# BILLING MANAGEMENT
# ======================
@app.route("/billing_structure")
def billing_structure():
    return render_template("billing_structure.html")

@app.route("/billing/get_all")
def get_all_billing():
    billing_docs = db.collection("billing").stream()
    return jsonify([{"id": doc.id, **doc.to_dict()} for doc in billing_docs])

@app.route("/billing/add", methods=["POST"])
def add_billing():
    billing_id = str(uuid.uuid4())
    db.collection("billing").document(billing_id).set(request.json)
    return jsonify({"status": "success"})

@app.route("/billing/update/<billing_id>", methods=["PUT"])
def update_billing(billing_id):
    db.collection("billing").document(billing_id).update(request.json)
    return jsonify({"status": "success"})

@app.route("/billing/delete/<billing_id>", methods=["DELETE"])
def delete_billing(billing_id):
    db.collection("billing").document(billing_id).delete()
    return jsonify({"status": "success"})

# ======================
# BILL CALCULATION
# ======================
@app.route("/billing/calculate/<patient_id>")
def calculate_bill(patient_id):
    patient_doc = db.collection("patients").document(patient_id).get()
    if not patient_doc.exists:
        return jsonify({"error": "Patient not found"}), 404

    patient = patient_doc.to_dict()
    treatments = [t.strip().lower() for t in patient.get("treatment", "").split(",")]
    rooms = [r.strip().lower() for r in patient.get("room", "").split(",")]
    days = int(patient.get("no_of_days", 1))

    if len(treatments) != len(rooms):
        return jsonify({"error": "Number of treatments and rooms do not match"}), 400

    total = 0
    details = []

    for t, r in zip(treatments, rooms):
        found = False
        for b in db.collection("billing").stream():
            bd = b.to_dict()
            if bd["treatment"].lower() == t and bd["room_type"].lower() == r:
                total += bd["treatment_cost"] + (bd["room_cost"] * days)
                details.append(bd)
                found = True
                break
        if not found:
            return jsonify({"error": f"No billing found for {t} + {r}"}), 404

    return jsonify({
        "patient": patient.get("name"),
        "treatments": details,
        "days": days,
        "total": total
    })

# ======================
# LOGOUT
# ======================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(debug=True)