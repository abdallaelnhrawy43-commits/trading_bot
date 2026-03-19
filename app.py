from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "🔥 الموقع شغال على السيرفر الصح"

@app.route("/test")
def test():
    return "test ok"