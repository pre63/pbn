import psycopg2
from flask import Response

from src.config import DB_CONFIG


def check_db_health() -> bool:
  """Check if the database is reachable."""
  if not DB_CONFIG:
    print("No database URL provided.")
    return False

  try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.close()
    print("Database connection successful.")
    return True
  except psycopg2.OperationalError as e:
    print(f"Database connection failed: {str(e)}")
    return False


def healthz_endpoint():
  """
    Health check endpoint using check_db_health.
    Returns 'healthy' with 200 if DB is reachable, 'unhealthy - <error>' with 500 if not.
    """
  print("Health check initiated.")

  ok = check_db_health()
  if not ok:
    print("Health check failed.")
    return Response("unhealthy - Database connection error", status=500, mimetype="text/plain")

  return Response("Ok", status=200, mimetype="text/plain")
