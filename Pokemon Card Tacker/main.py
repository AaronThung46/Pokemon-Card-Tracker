"""Entry point for the Pokemon Card Tracker Flask app."""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "true").lower() == "true")


"""
//cd "C:\Users\Aaron\idk\Pokemon-Card-Tracker\Pokemon Card Tacker"
.venv\Scripts\python.exe main.py

http://127.0.0.1:5000
"""