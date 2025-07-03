import datetime
import glob
import os
import random

import dateutil
import numpy as np
import yaml
from dateutil.parser import parse

# Define the path to your Markdown files
path = "content/*/articles/*.md"


# Function to generate a random date on a logarithmic scale
def random_log_date(start_date, end_date):
  # Convert dates to timestamps
  start_ts = start_date.timestamp()
  end_ts = end_date.timestamp()

  # Generate a random number on a logarithmic scale
  # We use np.logspace to create a distribution that favors recent dates
  log_random = np.random.uniform(0, 1)
  scaled = start_ts + (end_ts - start_ts) * (1 - log_random**2)

  # Convert back to datetime
  random_date = datetime.datetime.fromtimestamp(scaled)
  return random_date


# Set the date range (past 10 years)
end_date = datetime.datetime.now()
start_date = end_date - datetime.timedelta(days=365 * 10)

# Process each Markdown file
for filepath in glob.glob(path, recursive=True):
  try:
    # Read the file
    with open(filepath, "r", encoding="utf-8") as f:
      content = f.read()

    # Split front matter and content
    parts = content.split("---", 2)
    if len(parts) < 3:
      print(f"Skipping {filepath}: No valid front matter found")
      continue

    front_matter_str = parts[1].strip()
    body = parts[2].strip()

    # Parse front matter
    front_matter = yaml.safe_load(front_matter_str)
    if not front_matter:
      print(f"Skipping {filepath}: Invalid front matter")
      continue

    # Generate random date
    new_date = random_log_date(start_date, end_date)

    # Format date (adjust format to match your front matter)
    # Assuming ISO format (e.g., 2023-04-15 or 2023-04-15T10:30:00)
    if "date" in front_matter:
      old_date = front_matter["date"]
      # Check if date is a string or datetime
      if isinstance(old_date, str):
        try:
          parsed_date = parse(old_date)
          date_format = old_date[:10]  # Use YYYY-MM-DD
          new_date_str = new_date.strftime("%Y-%m-%d")
        except ValueError:
          print(f"Warning: Invalid date format in {filepath}: {old_date}")
          continue
      elif isinstance(old_date, datetime.datetime):
        new_date_str = new_date.strftime("%Y-%m-%d")
      else:
        print(f"Warning: Unsupported date type in {filepath}: {type(old_date)}")
        continue
    else:
      new_date_str = new_date.strftime("%Y-%m-%d")

    # Update front matter
    front_matter["date"] = new_date_str

    # Convert front matter back to YAML
    new_front_matter_str = yaml.dump(front_matter, allow_unicode=True, sort_keys=False)

    # Reconstruct the file content
    new_content = f"---\n{new_front_matter_str}---\n{body}"

    # Write back to file
    with open(filepath, "w", encoding="utf-8") as f:
      f.write(new_content)

    print(f"Updated {filepath}: date set to {new_date_str}")

  except Exception as e:
    print(f"Error processing {filepath}: {str(e)}")

print("Processing complete.")
