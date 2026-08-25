"""Entry point for local development and Render deployment.

Usage:
    python run.py

Or with gunicorn:
    gunicorn "run:app" --bind 0.0.0.0:5000
"""

from app import app

if __name__ == "__main__":
    app.run(debug=True, port=5000)
