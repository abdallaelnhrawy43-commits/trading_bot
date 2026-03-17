from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3, json, requests
from datetime import datetime, timedelta
import os

# تحديد مسار المشروع
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# تشغيل Flask وربط templates
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = "secret"

@app.route('/')
def home():
    return redirect('/login')

# دالة الاتصال بالداتابيز
def db():
    return sqlite3.connect("users.db")

# (اختياري للتأكد)
print("Templates Path:", os.path.join(BASE_DIR, "templates"))
# ================== PayPal ==================
PAYPAL_CLIENT_ID = "PUT_CLIENT_ID"
PAYPAL_SECRET = "PUT_SECRET"

def get_paypal_token():
    url = "https://api-m.sandbox.paypal.com/v1/oauth2/token"
    res = requests.post(url,
        data={"grant_type":"client_credentials"},
        auth=(PAYPAL_CLIENT_ID,PAYPAL_SECRET))
    return res.json()["access_token"]

# ================== Activate ==================
def activate_user(email, plan):
    conn = db()
    c = conn.cursor()

    expiry = (datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d")

    c.execute("""
    UPDATE users SET is_paid=1, plan=?, expiry=? WHERE email=?
    """,(plan, expiry, email))
    conn.commit()

    with open("users.json") as f:
        data = json.load(f)

    user = c.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
    chat_id = str(user[5])

    if chat_id not in data:
        data[chat_id] = {}

    data[chat_id]["is_paid"] = True
    data[chat_id]["plan"] = plan

    with open("users.json","w") as f:
        json.dump(data,f,indent=4)

# ================== Register ==================
@app.route("/register", methods=["GET","POST"])
def register():
    chat_id = request.args.get("chat_id")

    if request.method=="POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = db()
        c = conn.cursor()

        c.execute("""
        INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?)
        """,(name,email,password,1,"0000",chat_id,"free",0,"0"))

        conn.commit()
        session["user"] = email
        return redirect("/dashboard")

    return render_template("register.html", chat_id=chat_id)

# ================== Login ==================
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = db()
        c = conn.cursor()

        user = c.execute("SELECT * FROM users WHERE email=? AND password=?",
                         (email,password)).fetchone()

        if user:
            session["user"] = email
            return redirect("/dashboard")

    return render_template("login.html")

# ================== Dashboard ==================
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# ================== PayPal Create ==================
@app.route("/create-payment", methods=["POST"])
def create_payment():
    token = get_paypal_token()
    plan = request.form["plan"]

    prices = {"basic":"19.99","pro":"59.99","vip":"99.99"}

    data = {
        "intent":"CAPTURE",
        "purchase_units":[{
            "amount":{"currency_code":"USD","value":prices[plan]}
        }]
    }

    res = requests.post(
        "https://api-m.sandbox.paypal.com/v2/checkout/orders",
        headers={"Authorization":f"Bearer {token}"},
        json=data
    ).json()

    return res

# ================== PayPal Webhook ==================
@app.route("/paypal-webhook", methods=["POST"])
def paypal_webhook():
    data = request.json

    email = data["resource"]["payer"]["email_address"]
    amount = float(data["resource"]["amount"]["value"])

    if amount == 19.99:
        plan="basic"
    elif amount == 59.99:
        plan="pro"
    else:
        plan="vip"

    activate_user(email, plan)
    return "OK"

# ================== Admin ==================
@app.route("/admin-login", methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        if request.form["email"]=="admin@admin.com" and request.form["password"]=="123456":
            session["admin"]=True
            return redirect("/admin")

    return render_template("login.html")

@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/admin-login")

    conn = db()
    c = conn.cursor()
    users = c.execute("SELECT * FROM users").fetchall()

    return render_template("admin.html", users=users)

@app.route("/activate", methods=["POST"])
def activate():
    email = request.form["email"]
    plan = request.form["plan"]
    activate_user(email, plan)
    return redirect("/admin")

@app.route("/deactivate", methods=["POST"])
def deactivate():
    email = request.form["email"]
    conn = db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_paid=0 WHERE email=?", (email,))
    conn.commit()
    return redirect("/admin")

@app.route("/delete", methods=["POST"])
def delete():
    email = request.form["email"]
    conn = db()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE email=?", (email,))
    conn.commit()
    return redirect("/admin")

# ================== Stats ==================
@app.route("/stats")
def stats():
    with open("users.json") as f:
        users = json.load(f)
    return jsonify({"users": len(users)})

# ================== API ==================
@app.route("/api/login", methods=["POST"])
def api_login():
    return {"status":"ok"}

@app.route("/api/data")
def api_data():
    with open("users.json") as f:
        return json.load(f)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)