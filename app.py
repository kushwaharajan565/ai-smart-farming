import json
from urllib.request import urlopen
from urllib.parse import quote
from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import sqlite3
import os
import uuid
import subprocess


# =========================================================
# FLASK CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = "smart-farming-secret-key"

DATABASE = "database.db"

UPLOAD_FOLDER = os.path.join(
    "static",
    "uploads"
)

ALLOWED_PHOTO_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


# =========================================================
# CREATE UPLOAD FOLDER
# =========================================================

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():

    conn = sqlite3.connect(
        DATABASE
    )

    conn.row_factory = sqlite3.Row

    return conn
# =========================================================
# LIVE WEATHER
# =========================================================

def get_weather_condition(code):

    weather_codes = {
        0: "Clear Sky",
        1: "Mainly Clear",
        2: "Partly Cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Fog",
        51: "Light Drizzle",
        53: "Drizzle",
        55: "Heavy Drizzle",
        61: "Light Rain",
        63: "Rain",
        65: "Heavy Rain",
        71: "Light Snow",
        73: "Snow",
        75: "Heavy Snow",
        80: "Rain Showers",
        81: "Rain Showers",
        82: "Heavy Rain Showers",
        95: "Thunderstorm",
        96: "Thunderstorm with Hail",
        99: "Thunderstorm with Hail"
    }

    return weather_codes.get(
        code,
        "Unknown Weather"
    )


def get_live_weather(city="Bhopal"):

    try:

        # -------------------------------------------------
        # STEP 1: CITY -> LATITUDE/LONGITUDE
        # -------------------------------------------------

        geo_url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            "?name=" + quote(city)
            + "&count=1"
            + "&language=en"
            + "&format=json"
        )

        with urlopen(
            geo_url,
            timeout=10
        ) as response:

            geo_data = json.loads(
                response.read().decode("utf-8")
            )

        if not geo_data.get("results"):

            return {
                "error": "City not found. Please enter a valid city name."
            }

        location = geo_data["results"][0]

        latitude = location["latitude"]
        longitude = location["longitude"]

        city_name = location["name"]

        country = location.get(
            "country",
            ""
        )

        # -------------------------------------------------
        # STEP 2: GET LIVE WEATHER
        # -------------------------------------------------

        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=" + str(latitude)
            + "&longitude=" + str(longitude)

            + "&current="
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "precipitation,"
            "rain,"
            "weather_code,"
            "wind_speed_10m"

            + "&daily="
            "temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_probability_max"

            + "&forecast_days=5"
            + "&timezone=auto"
        )

        with urlopen(
            weather_url,
            timeout=10
        ) as response:

            weather_data = json.loads(
                response.read().decode("utf-8")
            )

        # -------------------------------------------------
        # CURRENT WEATHER
        # -------------------------------------------------

        current = weather_data.get(
            "current",
            {}
        )

        weather_code = current.get(
            "weather_code",
            0
        )

        condition = get_weather_condition(
            weather_code
        )

        # -------------------------------------------------
        # DAILY FORECAST
        # -------------------------------------------------

        daily = weather_data.get(
            "daily",
            {}
        )

        dates = daily.get(
            "time",
            []
        )

        max_temperatures = daily.get(
            "temperature_2m_max",
            []
        )

        min_temperatures = daily.get(
            "temperature_2m_min",
            []
        )

        rain_probability = daily.get(
            "precipitation_probability_max",
            []
        )

        forecast = []

        for i in range(
            len(dates)
        ):

            forecast.append(
                {
                    "date": dates[i],

                    "max_temp": max_temperatures[i]
                    if i < len(max_temperatures)
                    else "-",

                    "min_temp": min_temperatures[i]
                    if i < len(min_temperatures)
                    else "-",

                    "rain_probability":
                        rain_probability[i]
                        if i < len(rain_probability)
                        else 0
                }
            )

        # -------------------------------------------------
        # RETURN WEATHER DATA
        # -------------------------------------------------

        return {

            "city": city_name,

            "country": country,

            "temperature":
                current.get(
                    "temperature_2m"
                ),

            "humidity":
                current.get(
                    "relative_humidity_2m"
                ),

            "feels_like":
                current.get(
                    "apparent_temperature"
                ),

            "precipitation":
                current.get(
                    "precipitation"
                ),

            "rain":
                current.get(
                    "rain"
                ),

            "wind":
                current.get(
                    "wind_speed_10m"
                ),

            "condition":
                condition,

            "forecast":
                forecast
        }

    except Exception as e:

        print(
            "Weather Error:",
            e
        )

        return {
            "error":
                "Live weather is currently unavailable."
        }


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    conn = get_db()

    # -----------------------------------------------------
    # USERS TABLE
    # -----------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            profile_photo TEXT
        )
        """
    )

    # -----------------------------------------------------
    # ADD PROFILE PHOTO COLUMN IF OLD DATABASE
    # -----------------------------------------------------

    user_columns = conn.execute(
        "PRAGMA table_info(users)"
    ).fetchall()

    column_names = [
        column["name"]
        for column in user_columns
    ]

    if "profile_photo" not in column_names:

        conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN profile_photo TEXT
            """
        )

    # -----------------------------------------------------
    # CROPS TABLE
    # -----------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            soil_type TEXT,
            season TEXT,
            advice TEXT
        )
        """
    )

    # -----------------------------------------------------
    # DISEASES TABLE
    # -----------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS diseases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop TEXT NOT NULL,
            symptoms TEXT NOT NULL,
            disease TEXT NOT NULL,
            prevention TEXT,
            management TEXT
        )
        """
    )

    # -----------------------------------------------------
    # PREDICTIONS TABLE
    # -----------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            soil_type TEXT,
            soil_ph REAL,
            temperature REAL,
            humidity REAL,
            rainfall REAL,
            season TEXT,
            water_availability TEXT,
            recommended_crop TEXT,
            reason TEXT
        )
        """
    )

    # -----------------------------------------------------
    # DISEASE CHECKS TABLE
    # -----------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS disease_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            crop TEXT,
            symptoms TEXT,
            possible_disease TEXT,
            advice TEXT
        )
        """
    )

    # -----------------------------------------------------
    # AI ASSISTANT TABLE
    # -----------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS assistant_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question TEXT,
            answer TEXT
        )
        """
    )

    # -----------------------------------------------------
    # ADMIN TABLE
    # -----------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """
    )

    # -----------------------------------------------------
    # DEFAULT ADMIN
    # -----------------------------------------------------

    admin = conn.execute(
        """
        SELECT *
        FROM admins
        WHERE username = ?
        """,
        ("admin",)
    ).fetchone()

    if not admin:

        admin_password = generate_password_hash(
            "admin123"
        )

        conn.execute(
            """
            INSERT INTO admins (
                username,
                password
            )
            VALUES (?, ?)
            """,
            (
                "admin",
                admin_password
            )
        )

    conn.commit()

    conn.close()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        profile_photo = request.files.get(
            "profile_photo"
        )

        # -------------------------------------------------
        # BASIC VALIDATION
        # -------------------------------------------------

        if not name or not email or not password:

            return render_template(
                "register.html",
                error="Please fill all required fields."
            )

        if password != confirm_password:

            return render_template(
                "register.html",
                error="Passwords do not match."
            )

        # -------------------------------------------------
        # PROFILE PHOTO
        # -------------------------------------------------

        photo_filename = None

        if profile_photo and profile_photo.filename:

            original_name = secure_filename(
                profile_photo.filename
            )

            if "." not in original_name:

                return render_template(
                    "register.html",
                    error="Invalid profile photo."
                )

            extension = (
                original_name
                .rsplit(".", 1)[1]
                .lower()
            )

            if extension not in ALLOWED_PHOTO_EXTENSIONS:

                return render_template(
                    "register.html",
                    error="Only JPG, JPEG, PNG and WEBP images are allowed."
                )

            photo_filename = (
                "farmer_"
                + str(uuid.uuid4())
                + "."
                + extension
            )

            photo_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                photo_filename
            )

            profile_photo.save(
                photo_path
            )

        # -------------------------------------------------
        # PASSWORD HASH
        # -------------------------------------------------

        hashed_password = generate_password_hash(
            password
        )

        conn = get_db()

        try:

            conn.execute(
                """
                INSERT INTO users (
                    name,
                    email,
                    password,
                    profile_photo
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    hashed_password,
                    photo_filename
                )
            )

            conn.commit()

            conn.close()

            return redirect(
                url_for("login")
            )

        except sqlite3.IntegrityError:

            conn.close()

            # Delete uploaded photo if email already exists
            if photo_filename:

                photo_path = os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    photo_filename
                )

                if os.path.exists(photo_path):

                    os.remove(
                        photo_path
                    )

            return render_template(
                "register.html",
                error="Email already registered."
            )

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]

            session["user_name"] = user["name"]

            session["user_email"] = user["email"]

            return redirect(
                url_for("dashboard")
            )

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    return render_template(
        "login.html"
    )


@app.route(
    "/dashboard",
    methods=["GET", "POST"]
)
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            session["user_id"],
        )
    ).fetchone()

    conn.close()

    if not user:

        session.clear()

        return redirect(
            url_for("login")
        )

    # -------------------------------------------------
    # DEFAULT CITY
    # -------------------------------------------------

    city = "Bhopal"

    # -------------------------------------------------
    # CITY SEARCH
    # -------------------------------------------------

    if request.method == "POST":

        city = request.form.get(
            "city",
            "Bhopal"
        ).strip()

        if not city:

            city = "Bhopal"

    # -------------------------------------------------
    # LIVE WEATHER
    # -------------------------------------------------

    weather = get_live_weather(
        city
    )

    # -------------------------------------------------
    # DASHBOARD
    # -------------------------------------------------

    return render_template(
        "dashboard.html",
        user=user,
        weather=weather
    )
# =========================================================
# CROP PREDICTION
# =========================================================

@app.route(
    "/crop-prediction",
    methods=["GET", "POST"]
)
def crop_prediction():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    result = None

    if request.method == "POST":

        try:

            soil_type = request.form.get(
                "soil_type",
                ""
            )

            soil_ph = float(
                request.form.get(
                    "soil_ph",
                    7
                )
            )

            temperature = float(
                request.form.get(
                    "temperature",
                    25
                )
            )

            humidity = float(
                request.form.get(
                    "humidity",
                    60
                )
            )

            rainfall = float(
                request.form.get(
                    "rainfall",
                    100
                )
            )

            season = request.form.get(
                "season",
                ""
            )

            water_availability = request.form.get(
                "water_availability",
                ""
            )

        except ValueError:

            return render_template(
                "crop_prediction.html",
                result={
                    "crop": "Invalid Input",
                    "reason": "Please enter valid numerical values.",
                    "advice": "Check pH, temperature, humidity and rainfall values."
                }
            )

        # -------------------------------------------------
        # DEFAULT
        # -------------------------------------------------

        crop = "Millet"

        reason = (
            "Millet is a suitable option for relatively "
            "dry conditions and limited water availability."
        )

        advice = (
            "Use water carefully and maintain suitable "
            "soil moisture."
        )

        # -------------------------------------------------
        # RULE 1 - RICE
        # -------------------------------------------------

        if (
            rainfall >= 150
            and 20 <= temperature <= 35
            and water_availability == "High"
            and soil_type in [
                "Clay",
                "Loamy"
            ]
        ):

            crop = "Rice"

            reason = (
                "High rainfall, suitable temperature, "
                "good water availability and suitable "
                "soil support rice cultivation."
            )

            advice = (
                "Maintain proper water management and "
                "avoid unnecessary waterlogging."
            )

        # -------------------------------------------------
        # RULE 2 - WHEAT
        # -------------------------------------------------

        elif (
            50 <= rainfall < 150
            and 15 <= temperature <= 25
            and season == "Rabi"
            and soil_type in [
                "Loamy",
                "Clay"
            ]
        ):

            crop = "Wheat"

            reason = (
                "Moderate rainfall, cool temperature "
                "and Rabi season conditions are suitable "
                "for wheat."
            )

            advice = (
                "Maintain balanced irrigation and "
                "monitor soil nutrients."
            )

        # -------------------------------------------------
        # RULE 3 - MILLET
        # -------------------------------------------------

        elif (
            rainfall < 75
            and water_availability == "Low"
        ):

            crop = "Millet"

            reason = (
                "Low rainfall and limited water availability "
                "make millet a suitable drought-tolerant option."
            )

            advice = (
                "Use water carefully and maintain "
                "soil moisture conservation."
            )

        # -------------------------------------------------
        # RULE 4 - MAIZE
        # -------------------------------------------------

        elif (
            20 <= temperature <= 32
            and 50 <= rainfall <= 150
            and soil_type in [
                "Loamy",
                "Black"
            ]
        ):

            crop = "Maize"

            reason = (
                "The temperature and rainfall conditions "
                "are suitable for maize cultivation."
            )

            advice = (
                "Provide timely irrigation and maintain "
                "proper weed and nutrient management."
            )

        # -------------------------------------------------
        # RULE 5 - COTTON
        # -------------------------------------------------

        elif (
            21 <= temperature <= 35
            and 50 <= rainfall <= 100
            and soil_type == "Black"
            and season == "Kharif"
        ):

            crop = "Cotton"

            reason = (
                "Warm temperature, moderate rainfall, "
                "Black soil and Kharif season support cotton."
            )

            advice = (
                "Monitor soil moisture and regularly "
                "check for pest problems."
            )

        # -------------------------------------------------
        # SAVE PREDICTION
        # -------------------------------------------------

        conn = get_db()

        conn.execute(
            """
            INSERT INTO predictions (
                user_id,
                soil_type,
                soil_ph,
                temperature,
                humidity,
                rainfall,
                season,
                water_availability,
                recommended_crop,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                soil_type,
                soil_ph,
                temperature,
                humidity,
                rainfall,
                season,
                water_availability,
                crop,
                reason
            )
        )

        conn.commit()

        conn.close()

        result = {
            "crop": crop,
            "reason": reason,
            "advice": advice
        }

    return render_template(
        "crop_prediction.html",
        result=result
    )


# =========================================================
# DISEASE ASSISTANCE
# =========================================================

@app.route(
    "/disease",
    methods=["GET", "POST"]
)
def disease():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    result = None

    if request.method == "POST":

        crop = request.form.get(
            "crop",
            ""
        ).strip()

        symptoms = request.form.get(
            "symptoms",
            ""
        ).strip()

        crop_lower = crop.lower()

        symptoms_lower = symptoms.lower()

        # -------------------------------------------------
        # DEFAULT RESULT
        # -------------------------------------------------

        disease_name = "No specific match"

        symptom_text = (
            "The entered symptoms do not strongly match "
            "a predefined disease rule."
        )

        prevention = (
            "Monitor the crop regularly, maintain good "
            "field sanitation and use healthy planting material."
        )

        management = (
            "For accurate identification, consult a qualified "
            "agricultural professional."
        )

        # -------------------------------------------------
        # DATABASE SEARCH
        # -------------------------------------------------

        conn = get_db()

        # First try to find a record matching BOTH crop
        # and symptom keywords.

        disease_rows = conn.execute(
            """
            SELECT *
            FROM diseases
            WHERE LOWER(crop) LIKE ?
              AND LOWER(symptoms) LIKE ?
            ORDER BY id DESC
            """,
            (
                "%" + crop_lower + "%",
                "%" + symptoms_lower + "%"
            )
        ).fetchall()

        # If exact crop + symptom search does not find
        # anything, search symptom/disease keywords.

        if not disease_rows:

            disease_rows = conn.execute(
                """
                SELECT *
                FROM diseases
                WHERE LOWER(crop) LIKE ?
                   OR LOWER(symptoms) LIKE ?
                   OR LOWER(disease) LIKE ?
                ORDER BY id DESC
                """,
                (
                    "%" + crop_lower + "%",
                    "%" + symptoms_lower + "%",
                    "%" + symptoms_lower + "%"
                )
            ).fetchall()

        conn.close()

        # -------------------------------------------------
        # DATABASE MATCH
        # -------------------------------------------------

        if disease_rows:

            row = disease_rows[0]

            disease_name = row["disease"]

            symptom_text = row["symptoms"]

            prevention = row["prevention"]

            management = row["management"]

        # -------------------------------------------------
        # RICE BLAST
        # -------------------------------------------------

        elif (
            "rice" in crop_lower
            and (
                "diamond" in symptoms_lower
                or "spindle" in symptoms_lower
                or "blast" in symptoms_lower
            )
        ):

            disease_name = "Rice Blast"

            symptom_text = (
                "Spindle or diamond-shaped lesions may "
                "appear on rice leaves."
            )

            prevention = (
                "Use healthy seed, maintain balanced "
                "nutrition and avoid excessive nitrogen."
            )

            management = (
                "Monitor leaves and panicles regularly "
                "and seek local agricultural guidance."
            )

        # -------------------------------------------------
        # RICE BROWN SPOT
        # -------------------------------------------------

        elif (
            "rice" in crop_lower
            and (
                "brown spot" in symptoms_lower
                or "brown spots" in symptoms_lower
                or "brown" in symptoms_lower
            )
        ):

            disease_name = "Rice Brown Spot"

            symptom_text = (
                "Brown or reddish-brown spots may appear "
                "on rice leaves."
            )

            prevention = (
                "Use healthy seed and maintain balanced "
                "crop nutrition."
            )

            management = (
                "Maintain good crop management and seek "
                "local agricultural guidance."
            )

        # -------------------------------------------------
        # WHEAT YELLOW RUST
        # -------------------------------------------------

        elif (
            "wheat" in crop_lower
            and (
                "yellow stripe" in symptoms_lower
                or "yellow stripes" in symptoms_lower
                or "yellow rust" in symptoms_lower
                or "yellow" in symptoms_lower
            )
        ):

            disease_name = "Wheat Yellow Rust"

            symptom_text = (
                "Yellow or yellow-orange stripe-like "
                "patterns may appear on wheat leaves."
            )

            prevention = (
                "Regularly inspect the crop and use "
                "recommended resistant varieties where available."
            )

            management = (
                "Monitor disease spread and contact "
                "local agricultural guidance if suspected."
            )

        # -------------------------------------------------
        # COTTON LEAF BLIGHT
        # -------------------------------------------------

        elif (
            "cotton" in crop_lower
            and (
                "leaf spot" in symptoms_lower
                or "leaf spots" in symptoms_lower
                or "blight" in symptoms_lower
                or "brown" in symptoms_lower
            )
        ):

            disease_name = (
                "Cotton Alternaria Leaf Blight"
            )

            symptom_text = (
                "Brown or irregular leaf spots may "
                "develop into blighted areas."
            )

            prevention = (
                "Maintain crop spacing, remove infected "
                "plant residues and use healthy seed."
            )

            management = (
                "Monitor affected plants and follow "
                "locally recommended disease management."
            )

        # -------------------------------------------------
        # MAIZE COMMON RUST
        # -------------------------------------------------

        elif (
            "maize" in crop_lower
            and (
                "rust" in symptoms_lower
                or "powder" in symptoms_lower
                or "brown spot" in symptoms_lower
                or "brown spots" in symptoms_lower
            )
        ):

            disease_name = "Maize Common Rust"

            symptom_text = (
                "Small brown to cinnamon-coloured powdery "
                "pustules may appear on maize leaves."
            )

            prevention = (
                "Regularly inspect leaves and maintain good "
                "field sanitation. Use suitable varieties "
                "recommended for your region."
            )

            management = (
                "Monitor disease development and consult "
                "local agricultural guidance before applying "
                "any treatment."
            )

        # -------------------------------------------------
        # MILLET LEAF PROBLEM
        # -------------------------------------------------

        elif (
            "millet" in crop_lower
            and (
                "leaf spot" in symptoms_lower
                or "leaf spots" in symptoms_lower
                or "brown" in symptoms_lower
            )
        ):

            disease_name = (
                "Possible Millet Leaf Disease"
            )

            symptom_text = (
                "Brown or irregular spots may appear "
                "on millet leaves."
            )

            prevention = (
                "Maintain field sanitation, balanced crop "
                "nutrition and regular crop monitoring."
            )

            management = (
                "Monitor affected plants and seek local "
                "agricultural guidance for confirmation."
            )

        # -------------------------------------------------
        # GENERAL LEAF PROBLEM
        # -------------------------------------------------

        elif (
            "burning" in symptoms_lower
            or "brown leaves" in symptoms_lower
            or "leaf damage" in symptoms_lower
            or "leaf spot" in symptoms_lower
            or "leaf spots" in symptoms_lower
        ):

            disease_name = "Possible Leaf Problem"

            symptom_text = (
                "Leaf burning, browning or spots can have "
                "multiple possible causes."
            )

            prevention = (
                "Maintain suitable irrigation, monitor soil "
                "condition and inspect crops regularly."
            )

            management = (
                "Because different problems can produce similar "
                "symptoms, professional identification is recommended."
            )

        # -------------------------------------------------
        # RESULT
        # -------------------------------------------------

        result = {
            "crop": crop,
            "disease": disease_name,
            "symptoms": symptom_text,
            "prevention": prevention,
            "management": management
        }

        # -------------------------------------------------
        # SAVE DISEASE CHECK
        # -------------------------------------------------

        conn = get_db()

        conn.execute(
            """
            INSERT INTO disease_checks (
                user_id,
                crop,
                symptoms,
                possible_disease,
                advice
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                crop,
                symptoms,
                disease_name,
                management
            )
        )

        conn.commit()

        conn.close()

    return render_template(
        "disease.html",
        result=result
    )


# =========================================================
# AI FARMING ASSISTANT
# =========================================================

@app.route(
    "/assistant",
    methods=["GET", "POST"]
)
def assistant():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    answer = None

    question = None

    if request.method == "POST":

        question = request.form.get(
            "question",
            ""
        ).strip()

        if question:

            answer = farming_ai_answer(
                question
            )

            conn = get_db()

            conn.execute(
                """
                INSERT INTO assistant_queries (
                    user_id,
                    question,
                    answer
                )
                VALUES (?, ?, ?)
                """,
                (
                    session["user_id"],
                    question,
                    answer
                )
            )

            conn.commit()

            conn.close()

    return render_template(
        "assistant.html",
        answer=answer,
        question=question
    )


# =========================================================
# RULE-BASED AI FARMING ANSWER
# =========================================================

def farming_ai_answer(question):

    question = question.lower().strip()

    # -----------------------------------------------------
    # GREETING
    # -----------------------------------------------------

    if (
        "hello" in question
        or "hi" in question
        or "namaste" in question
    ):

        return (
            "Hello! I am Smart Farming AI Assistant. "
            "You can ask me about crops, soil, irrigation, "
            "rainfall, fertilizer, pests, diseases and "
            "crop management."
        )

    # -----------------------------------------------------
    # HIGH RAINFALL
    # -----------------------------------------------------

    if (
        "high rainfall" in question
        or "heavy rainfall" in question
        or "heavy rain" in question
        or "high rain" in question
        or "zyada barish" in question
        or "adhik barish" in question
    ):

        return (
            "High rainfall conditions can support crops "
            "such as rice when soil, temperature and water "
            "conditions are appropriate. Proper drainage "
            "is important to prevent waterlogging."
        )

    # -----------------------------------------------------
    # LOW RAINFALL
    # -----------------------------------------------------

    if (
        "low rainfall" in question
        or "less rainfall" in question
        or "low rain" in question
        or "kam barish" in question
        or "sukha" in question
        or "drought" in question
    ):

        return (
            "For low rainfall or dry conditions, "
            "drought-tolerant crops such as millets can "
            "be considered. Water conservation and "
            "soil moisture management are important."
        )

    # -----------------------------------------------------
    # SOIL PH
    # -----------------------------------------------------

    if (
        "soil ph" in question
        or "ph of soil" in question
        or "soil ka ph" in question
        or "mitti ka ph" in question
        or "what is ph" in question
    ):

        return (
            "Soil pH indicates whether soil is acidic, "
            "neutral or alkaline. It affects nutrient "
            "availability and crop growth. The suitable "
            "range depends on the crop."
        )

    # -----------------------------------------------------
    # IRRIGATION
    # -----------------------------------------------------

    if (
        "irrigation" in question
        or "watering" in question
        or "water crops" in question
        or "water crop" in question
        or "paani" in question
        or "sinchai" in question
    ):

        return (
            "Irrigation should depend on crop type, soil, "
            "weather and growth stage. Maintain suitable "
            "soil moisture and avoid both unnecessary "
            "water loss and waterlogging."
        )

    # -----------------------------------------------------
    # FERTILIZER
    # -----------------------------------------------------

    if (
        "fertilizer" in question
        or "fertiliser" in question
        or "khad" in question
        or "nutrient" in question
        or "urea" in question
    ):

        return (
            "Fertilizer decisions should depend on soil "
            "condition and crop requirements. Soil testing "
            "is useful before making specific nutrient "
            "recommendations. Avoid unnecessary fertilizer use."
        )

    # -----------------------------------------------------
    # CROP ROTATION
    # -----------------------------------------------------

    if (
        "crop rotation" in question
        or "crop rotate" in question
        or "fasal rotation" in question
    ):

        return (
            "Crop rotation means growing different crops "
            "on the same field in different seasons or years. "
            "It can help maintain soil health and reduce "
            "the buildup of some pests and diseases."
        )

    # -----------------------------------------------------
    # DISEASE
    # -----------------------------------------------------

    if (
        "prevent disease" in question
        or "disease prevention" in question
        or "crop disease" in question
        or "disease" in question
        or "rog" in question
        or "bimari" in question
    ):

        return (
            "To help prevent crop diseases, use healthy "
            "planting material, maintain field cleanliness, "
            "provide proper spacing, avoid excessive moisture "
            "and regularly monitor crops for unusual symptoms."
        )

    # -----------------------------------------------------
    # PEST
    # -----------------------------------------------------

    if (
        "pest" in question
        or "insect" in question
        or "keeda" in question
        or "insects" in question
    ):

        return (
            "Regularly inspect crops for insect activity, "
            "leaf damage and unusual growth. Maintain field "
            "sanitation and monitor crops regularly. For "
            "serious infestation, consult a qualified "
            "agricultural professional."
        )

    # -----------------------------------------------------
    # WHEAT
    # -----------------------------------------------------

    if "wheat" in question:

        return (
            "Wheat is generally associated with the Rabi "
            "season and relatively cool conditions. Suitable "
            "soil moisture, balanced irrigation and proper "
            "nutrient management are important."
        )

    # -----------------------------------------------------
    # RICE
    # -----------------------------------------------------

    if (
        "rice" in question
        or "paddy" in question
        or "dhan" in question
    ):

        return (
            "Rice generally requires adequate water and "
            "warm growing conditions. Consider soil type, "
            "rainfall, water availability and drainage "
            "before cultivation."
        )

    # -----------------------------------------------------
    # MILLET
    # -----------------------------------------------------

    if (
        "millet" in question
        or "bajra" in question
        or "jowar" in question
    ):

        return (
            "Millets can be suitable for relatively dry "
            "conditions and areas with limited water "
            "availability. Soil moisture conservation "
            "is useful for crop management."
        )

    # -----------------------------------------------------
    # MAIZE
    # -----------------------------------------------------

    if (
        "maize" in question
        or "corn" in question
        or "makka" in question
    ):

        return (
            "Maize generally performs well under suitable "
            "warm conditions with adequate soil moisture. "
            "Timely irrigation, weed control and nutrient "
            "management are important."
        )

    # -----------------------------------------------------
    # COTTON
    # -----------------------------------------------------

    if (
        "cotton" in question
        or "kapas" in question
    ):

        return (
            "Cotton generally prefers warm conditions. "
            "Black soil can be suitable in many areas. "
            "Monitor soil moisture and regularly inspect "
            "the crop for pest problems."
        )

    # -----------------------------------------------------
    # SOIL
    # -----------------------------------------------------

    if (
        "soil" in question
        or "mitti" in question
        or "soil type" in question
    ):

        return (
            "Good soil management includes maintaining "
            "organic matter, suitable moisture, proper "
            "drainage and balanced nutrient management. "
            "Soil testing can help understand soil condition."
        )

    # -----------------------------------------------------
    # TEMPERATURE
    # -----------------------------------------------------

    if (
        "temperature" in question
        or "garmi" in question
        or "heat" in question
    ):

        return (
            "Temperature affects crop growth, flowering "
            "and water requirements. During hot conditions, "
            "maintain suitable soil moisture and monitor "
            "plants for heat stress."
        )

    # -----------------------------------------------------
    # HUMIDITY
    # -----------------------------------------------------

    if (
        "humidity" in question
        or "moisture in air" in question
        or "nami" in question
    ):

        return (
            "High humidity can increase the risk of some "
            "crop diseases. Proper spacing, field ventilation "
            "and avoiding unnecessary moisture can help "
            "reduce disease risk."
        )

    # -----------------------------------------------------
    # GENERAL FARMING
    # -----------------------------------------------------

    if (
        "farming" in question
        or "farmer" in question
        or "crop" in question
        or "fasal" in question
        or "kheti" in question
    ):

        return (
            "For better farming decisions, consider soil "
            "type, soil pH, temperature, rainfall, humidity, "
            "season and water availability. These factors "
            "can help in selecting suitable crops and "
            "farming practices."
        )

    # -----------------------------------------------------
    # UNKNOWN
    # -----------------------------------------------------

    return (
        "I could not find a predefined answer for that "
        "question. Try asking about crop selection, soil "
        "pH, rainfall, irrigation, fertilizer, pests, "
        "crop diseases, crop rotation or farming tips."
    )


# =========================================================
# FARMING ASSISTANCE
# =========================================================

@app.route(
    "/farming-assistance",
    methods=["GET", "POST"]
)
def farming_assistance():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    answer = None

    if request.method == "POST":

        category = request.form.get(
            "category",
            "general"
        )

        question = request.form.get(
            "question",
            ""
        ).strip()

        if question:

            answer = farming_assistance_answer(
                category,
                question
            )

    return render_template(
        "farming_assistance.html",
        answer=answer
    )


# =========================================================
# FARMING ASSISTANCE RULES
# =========================================================

def farming_assistance_answer(
    category,
    question
):

    question = question.lower().strip()

    # -----------------------------------------------------
    # CROP
    # -----------------------------------------------------

    if category == "crop":

        if (
            "rice" in question
            or "paddy" in question
        ):

            return (
                "Rice generally requires adequate water "
                "and warm conditions. Consider rainfall, "
                "soil type, drainage and water availability."
            )

        elif "wheat" in question:

            return (
                "Wheat is generally associated with the "
                "Rabi season and relatively cool conditions. "
                "Maintain suitable soil moisture and "
                "balanced irrigation."
            )

        elif (
            "millet" in question
            or "bajra" in question
        ):

            return (
                "Millets can be suitable for relatively "
                "dry conditions and limited water availability."
            )

        elif (
            "maize" in question
            or "corn" in question
        ):

            return (
                "Maize generally requires suitable warm "
                "conditions and adequate soil moisture. "
                "Timely irrigation and nutrient management "
                "are important."
            )

        else:

            return (
                "For crop selection, consider soil type, "
                "soil pH, temperature, rainfall, season "
                "and water availability."
            )

    # -----------------------------------------------------
    # WATER
    # -----------------------------------------------------

    if category == "water":

        return (
            "Irrigation should depend on crop type, soil, "
            "weather and growth stage. Avoid excessive "
            "irrigation and unnecessary water loss. "
            "Maintain suitable soil moisture and drainage."
        )

    # -----------------------------------------------------
    # SOIL
    # -----------------------------------------------------

    if category == "soil":

        if "ph" in question:

            return (
                "Soil pH indicates whether soil is acidic "
                "or alkaline. It affects nutrient availability "
                "and crop growth. Suitable pH depends on "
                "the crop."
            )

        elif (
            "fertilizer" in question
            or "fertiliser" in question
            or "khad" in question
        ):

            return (
                "Fertilizer decisions should consider soil "
                "condition and crop requirements. Soil testing "
                "is useful before making specific nutrient "
                "recommendations."
            )

        return (
            "Good soil management includes maintaining "
            "organic matter, suitable moisture, proper "
            "drainage and balanced nutrient management."
        )

    # -----------------------------------------------------
    # PEST
    # -----------------------------------------------------

    if category == "pest":

        return (
            "Regularly inspect crops for unusual spots, "
            "discoloration, wilting or pest activity. "
            "Maintain field sanitation, use healthy planting "
            "material and avoid excessive moisture."
        )

    # -----------------------------------------------------
    # DEFAULT
    # -----------------------------------------------------

    return farming_ai_answer(
        question
    )


# =========================================================
# FARMING TIPS
# =========================================================

@app.route("/tips")
@app.route("/farming-tips")
def farming_tips():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    tips = [

        "Check soil condition before selecting a crop.",

        "Select crops according to season and local conditions.",

        "Maintain suitable irrigation according to crop needs.",

        "Avoid unnecessary water usage and maintain proper drainage.",

        "Use soil testing to understand nutrient requirements.",

        "Maintain organic matter for better soil health.",

        "Regularly inspect crops for pests and diseases.",

        "Use healthy seeds and planting material.",

        "Crop rotation can help maintain soil health.",

        "Monitor crops regularly during different growth stages.",

        "Avoid excessive fertilizer use.",

        "During heavy rainfall, maintain proper field drainage."

    ]

    return render_template(
        "farming_tips.html",
        tips=tips
    )


# =========================================================
# VOICE ASSISTANT - LISTEN
# =========================================================

def listen_from_microphone():

    try:

        powershell_script = r'''
Add-Type -AssemblyName System.Speech

$recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine

$recognizer.SetInputToDefaultAudioDevice()

$recognizer.LoadGrammar(
    (New-Object System.Speech.Recognition.DictationGrammar)
)

$result = $recognizer.Recognize()

if ($result -ne $null) {
    Write-Output $result.Text
}

$recognizer.Dispose()
'''

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                powershell_script
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        text = result.stdout.strip()

        if text:

            return text

        return None

    except Exception:

        return None


# =========================================================
# VOICE ASSISTANT - SPEAK
# =========================================================

def speak_text(text):

    try:

        safe_text = text.replace(
            "'",
            "''"
        )

        powershell_script = f"""
Add-Type -AssemblyName System.Speech

$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer

$speaker.Speak('{safe_text}')

$speaker.Dispose()
"""

        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                powershell_script
            ]
        )

    except Exception:

        pass


# =========================================================
# VOICE ASSISTANT
# =========================================================

@app.route(
    "/voice-assistant",
    methods=["GET", "POST"]
)
def voice_assistant():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    question = None

    answer = None

    voice_error = None

    if request.method == "POST":

        question = listen_from_microphone()

        if question:

            answer = farming_ai_answer(
                question
            )

            conn = get_db()

            conn.execute(
                """
                INSERT INTO assistant_queries (
                    user_id,
                    question,
                    answer
                )
                VALUES (?, ?, ?)
                """,
                (
                    session["user_id"],
                    question,
                    answer
                )
            )

            conn.commit()

            conn.close()

            speak_text(
                answer
            )

        else:

            voice_error = (
                "Voice input was not detected. "
                "Please check your microphone and try again."
            )

    return render_template(
        "voice_assistant.html",
        question=question,
        answer=answer,
        voice_error=voice_error
    )


# =========================================================
# USER PROFILE
# =========================================================

@app.route("/profile")
def profile():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            session["user_id"],
        )
    ).fetchone()

    conn.close()

    if not user:

        session.clear()

        return redirect(
            url_for("login")
        )

    return render_template(
        "profile.html",
        user=user
    )


# =========================================================
# USER LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db()

        admin = conn.execute(
            """
            SELECT *
            FROM admins
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        conn.close()

        if admin and check_password_hash(
            admin["password"],
            password
        ):

            session["admin_id"] = admin["id"]

            session["admin_username"] = admin["username"]

            return redirect(
                url_for("admin_dashboard")
            )

        return render_template(
            "admin_login.html",
            error="Invalid admin username or password."
        )

    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    total_users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    total_predictions = conn.execute(
        "SELECT COUNT(*) FROM predictions"
    ).fetchone()[0]

    total_disease_checks = conn.execute(
        "SELECT COUNT(*) FROM disease_checks"
    ).fetchone()[0]

    total_crops = conn.execute(
        "SELECT COUNT(*) FROM crops"
    ).fetchone()[0]

    total_diseases = conn.execute(
        "SELECT COUNT(*) FROM diseases"
    ).fetchone()[0]

    total_questions = conn.execute(
        "SELECT COUNT(*) FROM assistant_queries"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_predictions=total_predictions,
        total_disease_checks=total_disease_checks,
        total_crops=total_crops,
        total_diseases=total_diseases,
        total_questions=total_questions
    )


# =========================================================
# ADMIN USERS
# =========================================================

@app.route("/admin/users")
def admin_users():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    users = conn.execute(
        """
        SELECT id, name, email, profile_photo
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_users.html",
        users=users
    )


# =========================================================
# DELETE USER
# =========================================================

@app.route(
    "/admin/users/delete/<int:user_id>",
    methods=["POST"]
)
def delete_user(user_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    user = conn.execute(
        """
        SELECT profile_photo
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    conn.execute(
        "DELETE FROM users WHERE id = ?",
        (user_id,)
    )

    conn.commit()

    conn.close()

    # Delete profile photo from uploads folder
    if user and user["profile_photo"]:

        photo_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            user["profile_photo"]
        )

        if os.path.exists(photo_path):

            os.remove(
                photo_path
            )

    return redirect(
        url_for("admin_users")
    )


# =========================================================
# ADMIN CROPS
# =========================================================

@app.route("/admin/crops")
def admin_crops():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    crops = conn.execute(
        """
        SELECT *
        FROM crops
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_crops.html",
        crops=crops
    )


# =========================================================
# ADD CROP
# =========================================================

@app.route(
    "/admin/crops/add",
    methods=["GET", "POST"]
)
def add_crop():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        soil_type = request.form.get(
            "soil_type",
            ""
        ).strip()

        season = request.form.get(
            "season",
            ""
        ).strip()

        advice = request.form.get(
            "advice",
            ""
        ).strip()

        if name:

            conn = get_db()

            conn.execute(
                """
                INSERT INTO crops (
                    name,
                    soil_type,
                    season,
                    advice
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    soil_type,
                    season,
                    advice
                )
            )

            conn.commit()

            conn.close()

        return redirect(
            url_for("admin_crops")
        )

    return render_template(
        "add_crop.html"
    )


# =========================================================
# EDIT CROP
# =========================================================

@app.route(
    "/admin/crops/edit/<int:crop_id>",
    methods=["GET", "POST"]
)
def edit_crop(crop_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    crop = conn.execute(
        """
        SELECT *
        FROM crops
        WHERE id = ?
        """,
        (crop_id,)
    ).fetchone()

    if not crop:

        conn.close()

        return redirect(
            url_for("admin_crops")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        soil_type = request.form.get(
            "soil_type",
            ""
        ).strip()

        season = request.form.get(
            "season",
            ""
        ).strip()

        advice = request.form.get(
            "advice",
            ""
        ).strip()

        conn.execute(
            """
            UPDATE crops
            SET name = ?,
                soil_type = ?,
                season = ?,
                advice = ?
            WHERE id = ?
            """,
            (
                name,
                soil_type,
                season,
                advice,
                crop_id
            )
        )

        conn.commit()

        conn.close()

        return redirect(
            url_for("admin_crops")
        )

    conn.close()

    return render_template(
        "edit_crop.html",
        crop=crop
    )


# =========================================================
# DELETE CROP
# =========================================================

@app.route(
    "/admin/crops/delete/<int:crop_id>",
    methods=["POST"]
)
def delete_crop(crop_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    conn.execute(
        "DELETE FROM crops WHERE id = ?",
        (crop_id,)
    )

    conn.commit()

    conn.close()

    return redirect(
        url_for("admin_crops")
    )


# =========================================================
# ADMIN DISEASES
# =========================================================

@app.route("/admin/diseases")
def admin_diseases():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    search = request.args.get(
        "search",
        ""
    ).strip()

    conn = get_db()

    if search:

        keyword = "%" + search + "%"

        diseases = conn.execute(
            """
            SELECT *
            FROM diseases
            WHERE crop LIKE ?
               OR symptoms LIKE ?
               OR disease LIKE ?
            ORDER BY id DESC
            """,
            (
                keyword,
                keyword,
                keyword
            )
        ).fetchall()

    else:

        diseases = conn.execute(
            """
            SELECT *
            FROM diseases
            ORDER BY id DESC
            """
        ).fetchall()

    conn.close()

    return render_template(
        "admin_diseases.html",
        diseases=diseases,
        search=search
    )


# =========================================================
# ADD DISEASE
# =========================================================

@app.route(
    "/admin/diseases/add",
    methods=["GET", "POST"]
)
def add_disease():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    if request.method == "POST":

        crop = request.form.get(
            "crop",
            ""
        ).strip()

        symptoms = request.form.get(
            "symptoms",
            ""
        ).strip()

        disease_name = request.form.get(
            "disease",
            ""
        ).strip()

        prevention = request.form.get(
            "prevention",
            ""
        ).strip()

        management = request.form.get(
            "management",
            ""
        ).strip()

        if crop and symptoms and disease_name:

            conn = get_db()

            conn.execute(
                """
                INSERT INTO diseases (
                    crop,
                    symptoms,
                    disease,
                    prevention,
                    management
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    crop,
                    symptoms,
                    disease_name,
                    prevention,
                    management
                )
            )

            conn.commit()

            conn.close()

        return redirect(
            url_for("admin_diseases")
        )

    return render_template(
        "add_disease.html"
    )


# =========================================================
# EDIT DISEASE
# =========================================================

@app.route(
    "/admin/diseases/edit/<int:disease_id>",
    methods=["GET", "POST"]
)
def edit_disease(disease_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    disease_data = conn.execute(
        """
        SELECT *
        FROM diseases
        WHERE id = ?
        """,
        (disease_id,)
    ).fetchone()

    if not disease_data:

        conn.close()

        return redirect(
            url_for("admin_diseases")
        )

    if request.method == "POST":

        crop = request.form.get(
            "crop",
            ""
        ).strip()

        symptoms = request.form.get(
            "symptoms",
            ""
        ).strip()

        disease_name = request.form.get(
            "disease",
            ""
        ).strip()

        prevention = request.form.get(
            "prevention",
            ""
        ).strip()

        management = request.form.get(
            "management",
            ""
        ).strip()

        conn.execute(
            """
            UPDATE diseases
            SET crop = ?,
                symptoms = ?,
                disease = ?,
                prevention = ?,
                management = ?
            WHERE id = ?
            """,
            (
                crop,
                symptoms,
                disease_name,
                prevention,
                management,
                disease_id
            )
        )

        conn.commit()

        conn.close()

        return redirect(
            url_for("admin_diseases")
        )

    conn.close()

    return render_template(
        "edit_disease.html",
        disease=disease_data
    )


# =========================================================
# DELETE DISEASE
# =========================================================

@app.route(
    "/admin/diseases/delete/<int:disease_id>",
    methods=["POST"]
)
def delete_disease(disease_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    conn.execute(
        "DELETE FROM diseases WHERE id = ?",
        (disease_id,)
    )

    conn.commit()

    conn.close()

    return redirect(
        url_for("admin_diseases")
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin_id",
        None
    )

    session.pop(
        "admin_username",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# ERROR - FILE TOO LARGE
# =========================================================

@app.errorhandler(413)
def file_too_large(error):

    return render_template(
        "register.html",
        error="Profile photo must be smaller than 5 MB."
    ), 413


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True
    )