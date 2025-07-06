import glob
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import requests
from xai_sdk import Client
from xai_sdk.chat import system, user

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
XAI_API_KEY = os.getenv("XAI_API_KEY")
if not XAI_API_KEY:
  raise ValueError("XAI_API_KEY not set. Set it in your environment variables.")

# Configuration
HD_MIN_WIDTH = 1920  # Minimum width for HD
HD_MIN_HEIGHT = 1080  # Minimum height for HD
ASSETS_DIR = os.path.join(os.getcwd(), "content", "assets")

# Initialize xAI Client


def init_xai_client():
  try:
    client = Client(api_key=XAI_API_KEY, timeout=300)
    return client
  except Exception as e:
    logger.error(f"Failed to initialize xAI client: {e}")
    raise


# Step 1: Create Assets Directory


def setup_assets_directory():
  os.makedirs(ASSETS_DIR, exist_ok=True)
  logger.info(f"Assets directory: {ASSETS_DIR}")


# Step 2: Collect Markdown Files


def collect_markdown_files():
  articles_glob = os.path.join(os.getcwd(), "content", "*", "articles", "*.md")
  md_files = glob.glob(articles_glob, recursive=True)
  if not md_files:
    raise FileNotFoundError("No Markdown files found.")
  logger.info(f"Found {len(md_files)} Markdown files")
  return md_files


# Step 3: Extract Caption-Filename Pairs

def get__front_matter(file_path):
  """Extract front matter from a Markdown file."""
  with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()
  front_matter = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
  if front_matter:
    return front_matter.group(1).strip()
  return ""

def og_image_from_front_matter(file_path):
  """Extract og:image from front matter of a Markdown file."""
  front_matter = get__front_matter(file_path)
  if not front_matter:
    return None
  match = re.search(r"^og:image:\s*(.+)$", front_matter, re.MULTILINE)
  if match:
    return match.group(1).strip()
  return None

def extract_filenames(file_path):
  with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()
  pairs = []
  img_matches = re.findall(r"!\[(.*?)\]\(([^)]+\.jpg)\)", content)
  for caption, filename in img_matches:
    caption = caption.strip() or os.path.basename(filename).replace(".jpg", "").replace("_", " ")
    pairs.append((caption, os.path.basename(filename), content))

  og_image = og_image_from_front_matter(file_path)
  pairs.append(("og:image", og_image, content)) if og_image and og_image.endswith(".jpg") else None
  return pairs


# Step 4: Generate Image Prompt with Grok 3 Mini


def generate_image_prompt(client, article_content, caption):
  try:
    chat = client.chat.create(model="grok-3-mini", temperature=0.7, max_tokens=1000)
    chat.append(
      system(
        """
                You are a creative assistant tasked with generating detailed image prompts for an AI image generation model. Your prompts should be vivid, specific, and tailored to the context of an article and a given caption. The image should be high-definition (1920x1080 or larger), photorealistic, and suitable for a professional editorial article.
                """
      )
    )
    chat.append(
      user(
        f"""
                Generate a detailed image prompt (100-150 words) for an image that illustrates the caption "{caption}" in the context of the following article content:

                {article_content[:2000]}  # Truncate to avoid API limits

                The prompt should:
                - Describe a specific scene or object that visually represents the caption and article context.
                - Include details on lighting, color palette, composition, and style (photorealistic, editorial quality).
                - Ensure the image is HD (1920x1080 or larger) and suitable for a professional article.
                - Avoid generic descriptions; be precise and evocative.
                """
      )
    )
    response = chat.sample()
    prompt = response.content.strip()
    logger.info(f"Generated prompt for caption '{caption}': {prompt[:100]}...")
    return prompt
  except Exception as e:
    logger.error(f"Failed to generate prompt for caption '{caption}': {e}")
    return None


# Step 5: Generate Image with Grok


def generate_image(client, prompt, filename):
  # TODO: Replace with actual xAI image generation API endpoint
  # The provided documentation only covers image understanding (grok-2-vision).
  # Assuming an image generation endpoint similar to chat API, e.g., client.image.create.
  # Check https://x.ai/api or xAI support for the correct endpoint/model.

  try:
    # Save the image to the assets directory
    dest_path = os.path.join(ASSETS_DIR, filename)
    if os.path.exists(dest_path):
      logger.info(f"Skipping {filename} (already exists)")
      return False

    if len(prompt) > 1020:
      # "Prompt len is larger than the maximum allowed length which is 1024"
      prompt = prompt[:1020]  # Truncate to avoid API limits

    response = client.image.sample(model="grok-2-image-1212", prompt=prompt, image_format="url")

    print(response.url)

    try:
      image_data = requests.get(response.url).content
      with open(dest_path, "wb") as img_file:
        img_file.write(image_data)

    except Exception as e:
      logger.error(f"Failed to download image from {response.url}: {e}")
      return False

    logger.info(f"Image generated and saved to {dest_path}")
    return True

  except Exception as e:
    logger.error(f"Failed to generate image for prompt '{prompt}': {e}")
    return False


# Step 6: Process Single Image Task


def process_image_task(client, caption, filename, article_content):
  logger.info(f"\nProcessing: {filename}")
  logger.info(f"Caption: {caption}")

  # Generate prompt with Grok 3 Mini
  prompt = generate_image_prompt(client, article_content, caption)
  if not prompt:
    logger.warning(f"Skipping {filename} (prompt generation failed)")
    return False

  # Generate and save image
  if generate_image(client, prompt, filename):
    logger.info(f"Successfully processed {filename}")
    return True
  else:
    logger.warning(f"Failed to process {filename}")
    return False


# Main Processing


def main():
  setup_assets_directory()
  md_files = collect_markdown_files()
  client = init_xai_client()

  # Collect all image references
  all_pairs = []
  for md_file in md_files:
    pairs = extract_filenames(md_file)
    all_pairs.extend(pairs)

  if not all_pairs:
    logger.error("No image references found. Exiting.")
    return

  # Deduplicate filenames
  seen = set()
  unique_pairs = [pair for pair in all_pairs if not (pair[1] in seen or seen.add(pair[1]))]
  logger.info(f"Extracted {len(unique_pairs)} unique image references")

  # Process images sequentially
  i = 0
  for caption, filename, article_content in unique_pairs:
    print(f"\nProcessing: {i} of {len(unique_pairs)}")
    if not filename.endswith(".jpg"):
      logger.info(f"Skipping {filename} (not a .jpg file)")
      continue
    if os.path.exists(os.path.join(ASSETS_DIR, filename)):
      logger.info(f"Skipped {filename} (exists)")
      continue
    success = process_image_task(client, caption, filename, article_content)
    if not success:
      logger.warning(f"Failed or skipped {filename}")
    # count
    i += 1


# Run
if __name__ == "__main__":
  main()
