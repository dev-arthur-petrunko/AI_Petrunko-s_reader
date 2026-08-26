"""Точка входу для локальної розробки та деплою на Render."""

from app import app

if __name__ == "__main__":
    app.run(debug=True, port=5000)
