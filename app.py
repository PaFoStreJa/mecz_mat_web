from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import os
import json
from dotenv import load_dotenv
from datetime import datetime
from users import USERS
from tasks import TASKS
from werkzeug.utils import secure_filename

zadania_rozwiazania = {}  # przechowuje info kto wysłał rozwiązanie (task_id na username)
UPLOAD_FOLDER = os.path.join('static', 'uploads', 'solutions')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
players_location = {}
zadania_czasy = {}
task_times = []
load_dotenv()

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
    return jsonify({"status": "success"})

@app.route("/get_locations")
def get_locations():
    if "username" not in session or session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(players_location)

@app.route("/zadanie/<task_id>")
def pokaz_zadanie(task_id):
    username = session.get("username")
    if not username or task_id not in TASKS:
        return redirect(url_for("player_dashboard"))

    if username in zadania_rozwiazania and task_id in zadania_rozwiazania[username]:
        return redirect(url_for("player_dashboard"))

    if username not in zadania_czasy:
        zadania_czasy[username] = {}

    if task_id not in zadania_czasy[username]:
        zadania_czasy[username][task_id] = {"start": datetime.now(), "end": None}

    start_time = zadania_czasy[username][task_id]["start"]
    start_time_iso = start_time.isoformat()
    end_time = zadania_czasy[username][task_id]["end"]
    end_time_iso = end_time.isoformat() if end_time else None

    tresc = TASKS[task_id]
    return render_template("zadanie.html", task_id=task_id, tresc=tresc, start_time_iso=start_time_iso, end_time_iso=end_time_iso, username=username)

@app.route("/zakoncz_zadanie/<task_id>", methods=["POST"])
def zakoncz_zadanie(task_id):
    username = session.get("username")
    if not username or username not in zadania_czasy or task_id not in zadania_czasy[username]:
        return jsonify({"error": "Brak danych"}), 400

    zadania_czasy[username][task_id]["end"] = datetime.now()
    return jsonify({"status": "zako\u0144czono", "task_id": task_id})

@app.route("/upload_solution/<task_id>", methods=["POST"])
def upload_solution(task_id):
    username = session.get("username")
    if not username:
        return jsonify({"error": "Unauthorized"}), 401

    if username not in zadania_rozwiazania:
        zadania_rozwiazania[username] = set()

    if task_id in zadania_rozwiazania[username]:
        return jsonify({"error": "Rozwi\u0105zanie ju\u017c zosta\u0142o przes\u0142ane"}), 400

    if 'file' not in request.files:
        return jsonify({"error": "Brak pliku"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Brak nazwy pliku"}), 400

    filename = secure_filename(f"{username}_{task_id}.jpg")
    user_folder = os.path.join(UPLOAD_FOLDER, username)
    os.makedirs(user_folder, exist_ok=True)
    filepath = os.path.join(user_folder, filename)
    file.save(filepath)

    zadania_rozwiazania[username].add(task_id)

    if username in zadania_czasy and task_id in zadania_czasy[username]:
        start_time = zadania_czasy[username][task_id]["start"]
        end_time = datetime.now()
        zadania_czasy[username][task_id]["end"] = end_time
        duration = end_time - start_time

        task_times.append({
            "username": username,
            "task_id": task_id,
            "start": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": str(duration)
        })

    return jsonify({"status": "success"})

@app.route("/get_task_times")
def get_task_times():
    return jsonify(task_times)

@app.route("/get_gallery")
def get_gallery():
    gallery = []
    for user in os.listdir(UPLOAD_FOLDER):
        user_path = os.path.join(UPLOAD_FOLDER, user)
        if os.path.isdir(user_path):
            for filename in os.listdir(user_path):
                if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                    gallery.append({"username": user, "filename": filename})
    return jsonify(gallery)

if __name__ == "__main__":
    app.run(debug=True)
