# app.py
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from users import USERS
import os
from dotenv import load_dotenv
from datetime import datetime

players_location={}

load_dotenv()
print("SECRET:", os.getenv("FLASK_SECRET_KEY"))

app = Flask(__name__)
app.secret_key = os.getenv("SK")

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = USERS.get(username)
        if user and user["password"] == password:
            session["username"] = username
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Nieprawidłowe dane")

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))
    
    if session["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    else:
        return redirect(url_for("player_dashboard"))

@app.route("/player")
def player_dashboard():
    if session.get("role") != "player":
        return redirect(url_for("login"))
    return render_template("player_dashboard.html", username=session["username"])

@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    return render_template("admin_dashboard.html", username=session["username"])

@app.route("/update_location", methods=["POST"])
def update_location():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if latitude is None or longitude is None:
        return jsonify({"error": "Invalid data"}), 400

    username = session["username"]
    players_location[username] = {
        "latitude": latitude,
        "longitude": longitude,
        "last_update": datetime.utcnow().isoformat() + "Z"
    }
    print(f"Location updated for {username}: {latitude}, {longitude}")
    return jsonify({"status": "success"})

@app.route("/get_locations")
def get_locations():
    if "username" not in session or session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(players_location)

if __name__ == "__main__":
    app.run(debug=True)
