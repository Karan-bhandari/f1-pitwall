import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from f1_backend import create_app

app = create_app()

# This is the entry point for Vercel's Python serverless functions
if __name__ == "__main__":
    app.run(debug=True, port=5005)
