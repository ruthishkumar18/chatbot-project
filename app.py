from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import requests
import os

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default-fallback-if-not-set")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY missing. Set it in environment for security!")

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY missing. Set it in environment for OpenRouter!")
    
API_URL = "https://openrouter.ai/api/v1/chat/completions"


# Initialize DB
def init_db():
    with sqlite3.connect("chatbot.db") as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                reply TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

init_db()

# Query OpenRouter
def query_openrouter(user_message):
    if not API_KEY:
        return "⚠ API key not configured. Please check server environment variables."
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "meta-llama/llama-3-70b-instruct",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a friendly and professional AI assistant. "
                    "Your answers are cleanly formatted using HTML. "
                    "Use bullet points, numbered lists, <pre><code> for code, "
                    "<h3>, <h4> for headings, and <table> where appropriate."
                )
            },
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 3000,
        "temperature": 0.6,
        "top_p": 1
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    else:
        return f"❌ Error {response.status_code}: {response.text}"

# Routes
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("chat"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with sqlite3.connect("chatbot.db") as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
            user = c.fetchone()
        if user:
            session["user_id"] = user[0]
            return redirect(url_for("chat"))
        return "Invalid credentials. <a href='/login'>Try again</a>."
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        try:
            with sqlite3.connect("chatbot.db") as conn:
                c = conn.cursor()
                c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return "Username already exists. <a href='/signup'>Try another</a>."
    return render_template("signup.html")

@app.route("/chat")
def chat():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("chat.html")

@app.route("/get", methods=["POST"])
def get_reply():
    if "user_id" not in session:
        return jsonify({"reply": "Unauthorized. Please log in."})
    
    user_msg = request.json.get("msg", "").strip()
    if not user_msg:
        return jsonify({"reply": "Please enter a valid message."})

    bot_reply = query_openrouter(user_msg)

    with sqlite3.connect("chatbot.db") as conn:
        c = conn.cursor()
        c.execute("INSERT INTO history (user_id, message, reply) VALUES (?, ?, ?)",
                  (session["user_id"], user_msg, bot_reply))
        conn.commit()

    return jsonify({"reply": bot_reply})

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render sets this env var
    app.run(host="0.0.0.0", port=port)
