"""Petrunko's Reader — Flask application package."""

from app.routes import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
