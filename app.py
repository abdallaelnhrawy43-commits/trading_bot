from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "🔥 الموقع شغال يا معلم"

@app.route("/test")
def test():
    return "test ok"