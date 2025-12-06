# wsgi.py
from project import create_app  # make sure this matches your __init__.py

app = create_app()

# Optional: small sanity check if you run this directly
if __name__ == "__main__":
    app.run()
