import os

from src.app import create_app

if __name__ == "__main__":
  from waitress import serve

  app = create_app()

  DEV = os.getenv("DEV", False) == "True"
  host = "0.0.0.0"
  port = 8080

  print(f"Starting app on host: {host}, port: {port}")
  if DEV:
    print("Running in development mode...")
    app.run(debug=True, host=host, port=port)
  else:
    print("Running in production mode...")
    serve(app, host=host, port=port)
