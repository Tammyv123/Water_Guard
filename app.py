from flask import Flask, request, jsonify, session
from flask_cors import CORS
import os
import smtplib
import sqlite3
import bcrypt
from email.message import EmailMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# ---------------- Load Environment Variables ----------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASS = os.getenv("SENDER_PASS")

if not GOOGLE_API_KEY:
    raise Exception("❌ GOOGLE_API_KEY not found in .env")
if not SENDER_EMAIL or not SENDER_PASS:
    raise Exception("❌ Email credentials not found in .env")

os.environ['GOOGLE_API_KEY'] = GOOGLE_API_KEY

# ---------------- Flask Setup ----------------
app = Flask(__name__)
app.secret_key = "waterguard_secret"
CORS(app, supports_credentials=True)

# ---------------- SQLite DB Init ----------------
def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password BLOB NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------------- Gemini Chatbot ----------------
llm = ChatGoogleGenerativeAI(
    model="models/gemini-1.5-flash-latest",
    temperature=0.4
)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_prompt = data.get("prompt", "")

    if not user_prompt:
        return jsonify({"reply": "❌ Please provide a valid question."}), 400

    try:
        prompt = (
            "You are AquaBot, an expert on water sanitation and cleaning. "
            "Answer the user's question clearly and accurately with practical and reliable information.\n\n"
            f"User's Question: {user_prompt}\n"
            "Answer:"
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        return jsonify({"reply": response.content.strip()})
    except Exception as e:
        return jsonify({"reply": f"❌ An error occurred: {str(e)}"}), 500

# ---------------- Email Utility ----------------
def send_email(to, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = to

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(SENDER_EMAIL, SENDER_PASS)
        smtp.send_message(msg)

# ---------------- Signup ----------------
@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"message": "❌ All fields required"}), 400

    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    try:
        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed_pw))
        conn.commit()
        conn.close()

        subject = "🎉 Welcome to WaterGuard!"
        body = f"""Hi {name},

Thank you for signing up to 💧 WaterGuard — your smart partner for clean and safe water!

🚀 Features you now have access to:
- Check your water quality instantly
- Book doorstep testing kits
- Chat with AquaBot for water safety advice
- Get personalized insights & alerts

Explore now: https://your-waterguard-site.com

Clean water. Clear life.
— Team WaterGuard
"""
        send_email(email, subject, body)
        session['user'] = email
        return jsonify({"message": "✅ Signup successful and welcome email sent!"})
    except sqlite3.IntegrityError:
        return jsonify({"message": "❌ Email already registered"}), 409
    except Exception as e:
        return jsonify({"message": f"❌ Server error: {str(e)}"}), 500

# ---------------- Login ----------------
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE email = ?", (email,))
    result = cur.fetchone()
    conn.close()

    if result and bcrypt.checkpw(password.encode(), result[0]):
        session['user'] = email
        return jsonify({"message": "✅ Login successful"})
    return jsonify({"message": "❌ Invalid credentials"}), 401

# ---------------- Logout ----------------
@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({"message": "✅ Logged out"})

# ---------------- Auth Check ----------------
@app.route('/check-auth', methods=['GET'])
def check_auth():
    if 'user' in session:
        return jsonify({"authenticated": True})
    return jsonify({"authenticated": False}), 401

# ---------------- Book Kit (Protected) ----------------
@app.route('/book-kit', methods=['POST'])
def book_kit():
    if 'user' not in session:
        return jsonify({"message": "❌ Please login to book a kit."}), 401

    data = request.json
    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")
    address = data.get("address")
    date = data.get("date")

    subject = "✅ WaterGuard Kit Booking Confirmed!"
    body = f"""Hi {name},

Thanks for booking your Water Testing Kit with 💧 WaterGuard!

📍 Address:
{address}

📦 Your kit will reach your doorstep by: {date}

📘 The kit includes:
- pH Level Tester
- TDS Meter
- Turbidity Check
- Temperature Sensor
- Setup Manual

Stay safe & drink clean 🌊
— Team WaterGuard
"""
    try:
        send_email(email, subject, body)
        return jsonify({"message": "✅ Booking confirmed and email sent!"})
    except Exception as e:
        return jsonify({"message": f"❌ Email sending failed: {str(e)}"}), 500

# ---------------- Run Server ----------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)


