from api import create_app

app = create_app()

# This is the entry point for Vercel's Python serverless functions
if __name__ == "__main__":
    app.run(debug=True, port=5005)
