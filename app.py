from flask import Flask, render_template, request, redirect, session, url_for, jsonify, send_from_directory
import os
import json
from dotenv import load_dotenv
from datetime import datetime
from users import USERS
from tasks import TASKS
from werkzeug.utils import secure_filename
import hashlib

# Konfiguracja ścieżek i folderów
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Katalog gdzie jest app.py
DATA_DIR = os.path.join(BASE_DIR, 'data')
TASK_TIMES_FILE = os.path.join(DATA_DIR, 'task_times.json')
SOLUTIONS_FILE = os.path.join(DATA_DIR, 'zadania_rozwiazania.json')
LOCATIONS_FILE = os.path.join(DATA_DIR, 'players_location.json')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'solutions')  # Zawsze w folderze projektu

# Tworzenie folderów
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Debug info przy starcie
print(f"=== FLASK APP DEBUG INFO ===")
print(f"BASE_DIR (katalog aplikacji): {BASE_DIR}")
print(f"DATA_DIR: {DATA_DIR}")
print(f"UPLOAD_FOLDER: {UPLOAD_FOLDER}")
print(f"Current working directory: {os.getcwd()}")
print(f"Upload folder exists: {os.path.exists(UPLOAD_FOLDER)}")
print("==============================")

# Dozwolone rozszerzenia plików
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SK", "fallback-secret-key-change-me")

# Funkcje pomocnicze do zarządzania danymi
def load_json_file(filepath, default_value):
    """Bezpieczne ładowanie pliku JSON"""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Błąd odczytu {filepath}: {e}")
            return default_value
    return default_value

def save_json_file(filepath, data):
    """Bezpieczne zapisywanie pliku JSON"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return True
    except IOError as e:
        print(f"Błąd zapisu {filepath}: {e}")
        return False

def allowed_file(filename):
    """Sprawdza czy plik ma dozwolone rozszerzenie"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Ładowanie danych przy starcie
task_times = load_json_file(TASK_TIMES_FILE, [])
zadania_rozwiazania = load_json_file(SOLUTIONS_FILE, {})
players_location = load_json_file(LOCATIONS_FILE, {})

# Konwersja set na list dla JSON (jeśli potrzebne)
for username in zadania_rozwiazania:
    if isinstance(zadania_rozwiazania[username], list):
        zadania_rozwiazania[username] = set(zadania_rozwiazania[username])

zadania_czasy = {}  # Tymczasowe dane sesji

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template("login.html", error="Proszę podać nazwę użytkownika i hasło")

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

    data = request.get_json()
    if not data:
        return jsonify({"error": "Brak danych JSON"}), 400

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if latitude is None or longitude is None:
        return jsonify({"error": "Nieprawidłowe dane lokalizacji"}), 400

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (ValueError, TypeError):
        return jsonify({"error": "Nieprawidłowy format współrzędnych"}), 400

    username = session["username"]
    players_location[username] = {
        "latitude": latitude,
        "longitude": longitude,
        "last_update": datetime.utcnow().isoformat() + "Z"
    }
    
    # Zapisz do pliku
    save_json_file(LOCATIONS_FILE, players_location)
    
    return jsonify({"status": "success"})

@app.route("/get_locations")
def get_locations():
    if "username" not in session or session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(players_location)

@app.route("/zadanie/<task_id>")
def pokaz_zadanie(task_id):
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))
    
    if task_id not in TASKS:
        return redirect(url_for("player_dashboard"))

    # Sprawdź czy użytkownik już rozwiązał to zadanie
    user_solutions = zadania_rozwiazania.get(username, set())
    if isinstance(user_solutions, list):
        user_solutions = set(user_solutions)
    
    if task_id in user_solutions:
        return redirect(url_for("player_dashboard"))

    # Inicjalizuj czas rozpoczęcia
    if username not in zadania_czasy:
        zadania_czasy[username] = {}

    if task_id not in zadania_czasy[username]:
        zadania_czasy[username][task_id] = {"start": datetime.now(), "end": None}

    start_time = zadania_czasy[username][task_id]["start"]
    start_time_iso = start_time.isoformat()
    end_time = zadania_czasy[username][task_id]["end"]
    end_time_iso = end_time.isoformat() if end_time else None

    tresc = TASKS[task_id]
    return render_template("zadanie.html", 
                         task_id=task_id, 
                         tresc=tresc, 
                         start_time_iso=start_time_iso, 
                         end_time_iso=end_time_iso, 
                         username=username)

@app.route("/zakoncz_zadanie/<task_id>", methods=["POST"])
def zakoncz_zadanie(task_id):
    username = session.get("username")
    if not username:
        return jsonify({"error": "Unauthorized"}), 401
        
    if username not in zadania_czasy or task_id not in zadania_czasy[username]:
        return jsonify({"error": "Brak danych o zadaniu"}), 400

    zadania_czasy[username][task_id]["end"] = datetime.now()
    return jsonify({"status": "zakończono", "task_id": task_id})

@app.route("/upload_solution/<task_id>", methods=["POST"])
def upload_solution(task_id):
    username = session.get("username")
    if not username:
        return jsonify({"error": "Unauthorized"}), 401

    if task_id not in TASKS:
        return jsonify({"error": "Nieprawidłowe zadanie"}), 400

    # Sprawdź czy użytkownik już wysłał rozwiązanie
    if username not in zadania_rozwiazania:
        zadania_rozwiazania[username] = set()
    elif isinstance(zadania_rozwiazania[username], list):
        zadania_rozwiazania[username] = set(zadania_rozwiazania[username])

    if task_id in zadania_rozwiazania[username]:
        return jsonify({"status": "already_sent", "message": "Rozwiązanie już zostało wysłane"}), 200

    # Sprawdź plik
    if 'file' not in request.files:
        return jsonify({"error": "Brak pliku"}), 400
        
    file = request.files['file']
    if file.filename == "":
        return jsonify({"error": "Nie wybrano pliku"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Nieprawidłowy typ pliku. Dozwolone: png, jpg, jpeg, gif"}), 400

    try:
        # Bezpieczna nazwa pliku
        filename = secure_filename(f"{username}_{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        user_folder = os.path.join(UPLOAD_FOLDER, username)
        os.makedirs(user_folder, exist_ok=True)
        filepath = os.path.join(user_folder, filename)
        
        print(f"DEBUG: Zapisuję plik: {filepath}")
        print(f"DEBUG: User folder: {user_folder}")
        print(f"DEBUG: Upload folder exists: {os.path.exists(UPLOAD_FOLDER)}")
        
        # Zapisz plik
        file.save(filepath)
        
        print(f"DEBUG: Plik zapisany pomyślnie: {os.path.exists(filepath)}")
        print(f"DEBUG: Rozmiar pliku: {os.path.getsize(filepath) if os.path.exists(filepath) else 'BRAK'}")

        # Dodaj do rozwiązań
        zadania_rozwiazania[username].add(task_id)

        # Oblicz czas wykonania
        if username in zadania_czasy and task_id in zadania_czasy[username]:
            start = zadania_czasy[username][task_id]["start"]
            end = datetime.now()
            zadania_czasy[username][task_id]["end"] = end
            duration = str(end - start)
        else:
            start = datetime.now()
            end = datetime.now()
            duration = "0:00:00"

        # Dodaj rekord do task_times
        record = {
            "username": username,
            "task_id": task_id,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "duration": duration,
            "filename": filename
        }
        task_times.append(record)

        # Zapisz dane do plików
        # Konwertuj set na list dla JSON
        solutions_for_json = {}
        for user, solutions in zadania_rozwiazania.items():
            solutions_for_json[user] = list(solutions) if isinstance(solutions, set) else solutions

        save_json_file(SOLUTIONS_FILE, solutions_for_json)
        save_json_file(TASK_TIMES_FILE, task_times)

        return jsonify({"status": "success", "message": "Rozwiązanie zostało wysłane"})

    except Exception as e:
        print(f"Błąd podczas uploadu: {e}")
        return jsonify({"error": "Błąd podczas zapisywania pliku"}), 500

@app.route("/get_task_times")
def get_task_times():
    if "username" not in session or session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(task_times)

@app.route("/get_gallery")
def get_gallery():
    """Endpoint do pobierania listy zdjęć w galerii"""
    if "username" not in session or session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 401
        
    gallery = []
    try:
        if os.path.exists(UPLOAD_FOLDER):
            for user in os.listdir(UPLOAD_FOLDER):
                user_path = os.path.join(UPLOAD_FOLDER, user)
                if os.path.isdir(user_path):
                    for filename in os.listdir(user_path):
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                            # Generuj różne warianty URL-ów do testowania
                            gallery.append({
                                'username': user, 
                                'filename': filename, 
                                'rel_url': f"uploads/solutions/{user}/{filename}",
                                'image_url': url_for('uploaded_file', user=user, filename=filename),
                                'static_url': url_for('static', filename=f'uploads/solutions/{user}/{filename}'),
                                'direct_path': f'/static/uploads/solutions/{user}/{filename}',
                                'full_path': os.path.join(user_path, filename),
                                'file_exists': os.path.exists(os.path.join(user_path, filename)),
                                'file_size': os.path.getsize(os.path.join(user_path, filename)) if os.path.exists(os.path.join(user_path, filename)) else 0
                            })
    except Exception as e:
        print(f"Błąd podczas pobierania galerii: {e}")
        return jsonify({"error": f"Błąd podczas pobierania galerii: {str(e)}"}), 500
        
    return jsonify(gallery)

@app.route('/uploads/solutions/<user>/<filename>')
def uploaded_file(user, filename):
    """Serwuje przesłane pliki"""
    if "username" not in session or session.get("role") != "admin":
        return "Unauthorized", 401
    
    # Bezpieczne sprawdzenie ścieżki
    safe_user = secure_filename(user)
    safe_filename = secure_filename(filename)
    
    user_folder = os.path.join(UPLOAD_FOLDER, safe_user)
    print(f"DEBUG: Szukam pliku w: {user_folder}/{safe_filename}")
    
    if not os.path.exists(user_folder):
        print(f"DEBUG: Folder użytkownika nie istnieje: {user_folder}")
        return f"User folder not found: {user_folder}", 404
    
    file_path = os.path.join(user_folder, safe_filename)
    if not os.path.exists(file_path):
        print(f"DEBUG: Plik nie istnieje: {file_path}")
        return f"File not found: {file_path}", 404
    
    print(f"DEBUG: Serwuję plik: {file_path}")
    # Użyj send_from_directory zamiast send_static_file
    return send_from_directory(user_folder, safe_filename)

@app.route("/debug_files")
def debug_files():
    """Endpoint do debugowania - pokazuje strukturę plików"""
    if "username" not in session or session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 401
    
    debug_info = {
        "upload_folder_exists": os.path.exists(UPLOAD_FOLDER),
        "upload_folder_path": UPLOAD_FOLDER,
        "current_working_directory": os.getcwd(),
        "files_structure": {}
    }
    
    try:
        if os.path.exists(UPLOAD_FOLDER):
            for user in os.listdir(UPLOAD_FOLDER):
                user_path = os.path.join(UPLOAD_FOLDER, user)
                if os.path.isdir(user_path):
                    debug_info["files_structure"][user] = {
                        "path": user_path,
                        "files": os.listdir(user_path)
                    }
    except Exception as e:
        debug_info["error"] = str(e)
    
    return jsonify(debug_info)

@app.route("/get_gallery_images")
def get_gallery_images():
    """Alternatywny endpoint dla galerii (kompatybilność z HTML)"""
    return get_gallery()

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.errorhandler(404)
def not_found(error):
    return render_template('login.html', error="Strona nie została znaleziona"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('login.html', error="Wystąpił błąd serwera"), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)