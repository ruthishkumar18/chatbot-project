from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import requests
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"  

API_KEY = os.getenv("API_KEY")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# ----- DB Setup -----
def init_db():
    with sqlite3.connect("chatbot.db") as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE,
                        password TEXT
                    )""")
        c.execute("""CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        message TEXT,
                        reply TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    )""")

init_db()

# ----- Chatbot Query -----
def query_openrouter(user_message):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "meta-llama/llama-3-70b-instruct",
        "messages": [
            {"role": "system",
             "content": (
                 "You are an advanced AI assistant, acting as a highly skilled tutor, programmer, and explainer — similar to ChatGPT advanced version.\n"
                 "\nYour goals:\n"
                 "- Provide detailed, clear, and human-like answers.\n"
                 "- Always organize content neatly with appropriate HTML structure.\n"
                 "- Include bullet points (•), numbered lists (1., 2.), and tables where needed.\n"
                 "- Use <h3>, <h4> for headings.\n"
                 "- Present code with proper indentation in <pre><code> blocks (no broken formatting or paragraphs for code).\n"
                 "- Do not use markdown syntax like **, *, ``` or # — only proper HTML tags.\n"
                 "- Separate ideas in distinct <p> paragraphs.\n"
                 "- Always format output so it looks clean in a web chat interface.\n"
                 "\nCode output:\n"
                 "- For code, wrap in <pre><code> and keep indentation intact.\n"
                 "- Show syntax exactly as it should be written.\n"
                 "- For long code, split into logical sections if needed.\n"
                 "\nOther output:\n"
                 "- For step-by-step guides, use numbered lists.\n"
                 "- Wrap outputs in <div class='output'>...</div>.\n"
                 "- For definitions, use <strong> for key terms.\n"
                 "- For important notes, prefix with ⚠ or ✅.\n"
                 "- When giving examples, clearly separate input and output.\n"
                 "\nFeatures:\n"
                 "- You can answer programming questions in any language (Python, JavaScript, C++, etc.).\n"
                 "- You can provide calculations, logic explanation, and diagram descriptions.\n"
                 "- You can summarize, explain concepts in depth, or provide quick answers as needed.\n"
                 "- You can generate tables using HTML <table>, <tr>, <td> tags.\n"
                 "- When showing JSON, XML, YAML or other structured data, format cleanly in <pre><code>.\n"
                 "- You will never break formatting into paragraphs for code — code should appear cleanly.\n"
                 "\nInteraction tone:\n"
                 "- Be friendly, supportive, and professional.\n"
                 "- Be friendly, supportive, and professional.\n"
                 "\nLimitations:\n"
                 "- Never return markdown syntax (like **bold**, ```code```, etc.).\n"
                 "- Never include raw HTML entities (e.g., &lt;, &gt;) inside code blocks — render as real < and >.\n"
                 "\nEnsure:\n"
                 "- Every reply is clean, well-structured, and easy to read in a web chat UI.\n"
                 "- Make the reply look clean for a chat window.\n"
                 "- Every code block looks correct in indentation and spacing, just like ChatGPT would provide."
                 )
             },
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 6000,
        "temperature": 0.6,
        "top_p": 1
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    else:
        return f"Error: {response.status_code} - {response.text}"

# ----- Routes -----
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
            else:
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
    user_id = session["user_id"]
    user_msg = request.json.get("msg", "").strip()
    if not user_msg:
        return jsonify({"reply": "Please enter a valid question."})

    bot_reply = query_openrouter(user_msg)

    with sqlite3.connect("chatbot.db") as conn:
        c = conn.cursor()
        c.execute("INSERT INTO history (user_id, message, reply) VALUES (?, ?, ?)",
                  (user_id, user_msg, bot_reply))
        conn.commit()

    return jsonify({"reply": bot_reply})

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  
    app.run(host="0.0.0.0", port=port, debug=False)
