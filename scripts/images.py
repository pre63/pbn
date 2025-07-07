import argparse
import glob
import logging
import os
import re
import time
from typing import Dict, List, Optional, Tuple

import requests
import yaml
from xai_sdk import Client
from xai_sdk.chat import system, user

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
MAX_PROMPT_LENGTH = 1000  # Internal limit for prompt length
MAX_RETRIES = 3  # Number of retries for image download
RETRY_BACKOFF = 2  # Base seconds for exponential backoff


# Client Wrapper Module
class ClientWrapper:
  def __init__(self):
    pass

  def init_client(self) -> Client:
    """Initialize xAI client."""
    xai_api_key = os.getenv("XAI_API_KEY")
    if not xai_api_key:
      raise ValueError("XAI_API_KEY not set.")
    try:
      return Client(api_key=xai_api_key, timeout=300)
    except Exception as e:
      logger.error(f"Failed to initialize xAI client: {e}")
      raise


# Extraction Module
class Extraction:
  def __init__(self):
    pass

  def get_front_matter(self, file_path: str) -> Dict:
    """Parse front matter from a Markdown file using YAML."""
    with open(file_path, "r", encoding="utf-8") as f:
      content = f.read()
    front_matter_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not front_matter_match:
      return {}
    try:
      return yaml.safe_load(front_matter_match.group(1)) or {}
    except yaml.YAMLError as e:
      logger.error(f"Failed to parse YAML front matter in {file_path}: {e}")
      return {}

  def collect_markdown_files(self, md_dir: str) -> List[str]:
    """Collect all Markdown files in the specified directory."""
    articles_glob = os.path.join(md_dir, "**", "*.md")
    md_files = glob.glob(articles_glob, recursive=True)
    if not md_files:
      logger.warning(f"No Markdown files found in {md_dir}")
    logger.info(f"Found {len(md_files)} Markdown files")
    return md_files

  def collect_domain_yaml_files(self, domains_dir: str) -> List[str]:
    """Collect all YAML files in the domains directory."""
    yaml_glob = os.path.join(domains_dir, "*.yml")
    yaml_files = glob.glob(yaml_glob)
    if not yaml_files:
      logger.warning(f"No YAML files found in {domains_dir}")
    logger.info(f"Found {len(yaml_files)} YAML files")
    return yaml_files

  def extract_filenames(self, file_path: str) -> List[Tuple[str, str, str]]:
    """Extract caption, filename, and content from a Markdown file."""
    with open(file_path, "r", encoding="utf-8") as f:
      content = f.read()
    front_matter = self.get_front_matter(file_path)
    pairs = []
    img_matches = re.findall(r"!\[(.*?)\]\(([^)]+\.jpg)\)", content)
    for caption, filename in img_matches:
      caption = caption.strip() or os.path.basename(filename).replace(".jpg", "").replace("_", " ")
      pairs.append((caption, os.path.basename(filename), content))
    og_image = front_matter.get("og_image")
    title = front_matter.get("title", "")
    if og_image and og_image.endswith(".jpg"):
      caption = title.strip() or os.path.basename(og_image).replace(".jpg", "").replace("_", " ")
      pairs.append((caption, os.path.basename(og_image), content))
    return pairs

  def extract_yaml_info(self, file_path: str) -> Optional[Tuple[str, str]]:
    """Extract description and image filename from a domain YAML file."""
    try:
      print(f"Processing YAML file: {file_path}")
      with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
      content = data.get("content", {})
      topics = content.get("topics", [])
      topics = ", ".join(topics) if isinstance(topics, list) else topics
      site = content.get("site", {})
      description = site.get("description", "")
      if not topics:
        logger.warning(f"No topics found in {file_path}")
        return None
      image_path = content.get("logo") or content.get("default_image")
      if not image_path or not image_path.endswith(".jpg"):
        logger.warning(f"No valid og_image or default_image found in {file_path}")
        return None
      filename = os.path.basename(image_path)
      caption = f"{description.strip()} {topics.strip()}"
      return caption, filename
    except yaml.YAMLError as e:
      logger.error(f"Failed to parse YAML in {file_path}: {e}")
      return None

  def save_references(self, references: Dict[str, List[Dict]], references_file: str) -> None:
    """Save extracted references to YAML file."""
    os.makedirs(os.path.dirname(references_file), exist_ok=True)
    with open(references_file, "w", encoding="utf-8") as f:
      yaml.safe_dump(references, f, sort_keys=False)
    logger.info(f"Saved references to {references_file}")

  def load_references(self, references_file: str) -> Dict[str, List[Dict]]:
    """Load references from YAML file."""
    if os.path.exists(references_file):
      with open(references_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
    return {}


# Prompt Management Module
class PromptManager:
  def __init__(self):
    pass

  def load_prompts(self, prompts_file: str) -> Dict[str, str]:
    """Load prompts from YAML file."""
    if os.path.exists(prompts_file):
      with open(prompts_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
    return {}

  def save_prompts(self, prompts: Dict[str, str], prompts_file: str) -> None:
    """Save prompts to YAML file."""
    with open(prompts_file, "w", encoding="utf-8") as f:
      yaml.safe_dump(prompts, f, sort_keys=False)
    logger.info(f"Saved prompts to {prompts_file}")

  def generate_prompt(self, client: Client, article_content: str, caption: str) -> Optional[str]:
    """Generate an image prompt using Grok 3 Mini, ensuring length <= 1024."""
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
      logger.info(f"Generated prompt for caption '{caption}' (length: {len(prompt)}): {prompt[:100]}...")
      return prompt
    except Exception as e:
      logger.error(f"Failed to generate prompt for caption '{caption}': {e}")
      return None

  def generate_prompt_if_needed(
    self, client: Client, caption: str, filename: str, article_content: str, existing_prompts: Dict[str, str], prompts_file: str
  ) -> Optional[str]:
    """Generate a prompt for a single image if needed, updating prompts."""
    if filename in existing_prompts:
      logger.info(f"Using cached prompt for {filename}")
      return existing_prompts[filename]
    prompt = self.generate_prompt(client, article_content, caption)
    if prompt:
      existing_prompts[filename] = prompt
      self.save_prompts(existing_prompts, prompts_file)
    return prompt


# Image Generation Module
class ImageGenerator:
  def __init__(self):
    pass

  def load_urls(self, urls_file: str) -> Dict[str, str]:
    """Load URLs from YAML file."""
    if os.path.exists(urls_file):
      with open(urls_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
    return {}

  def save_urls(self, urls: Dict[str, str], urls_file: str) -> None:
    """Save URLs to YAML file."""
    with open(urls_file, "w", encoding="utf-8") as f:
      yaml.safe_dump(urls, f, sort_keys=False)
    logger.info(f"Saved URLs to {urls_file}")

  def generate_image(self, client: Client, prompt: str, filename: str, assets_dir: str, urls_file: str, downloader: "ImageDownloader") -> bool:
    """Generate an image, save URL, and attempt download."""
    os.makedirs(assets_dir, exist_ok=True)
    dest_path = os.path.join(assets_dir, filename)
    urls = self.load_urls(urls_file)

    # Check if we have a URL to retry
    if filename in urls:
      logger.info(f"Retrying download for {filename} using saved URL")
      success = downloader.download_image(urls[filename], dest_path)
      if success:
        del urls[filename]
        self.save_urls(urls, urls_file)
        return True
      else:
        logger.warning(f"Retry download failed for {filename}, regenerating image")
        del urls[filename]
        self.save_urls(urls, urls_file)

    try:
      prompt = prompt[:MAX_PROMPT_LENGTH]  # Failsafe truncation
      logger.info(f"Using prompt for {filename} (length: {len(prompt)})")
      response = client.image.sample(model="grok-2-image-1212", prompt=prompt, image_format="url")
      image_url = response.url
      logger.info(f"Generated image URL for {filename}: {image_url}")

      # Save URL to file
      urls[filename] = image_url
      self.save_urls(urls, urls_file)

      # Attempt download
      success = downloader.download_image(image_url, dest_path)
      if success:
        del urls[filename]
        self.save_urls(urls, urls_file)
        return True
      return False
    except Exception as e:
      logger.error(f"Failed to generate image for {filename}: {e}")
      return False


# Image Download Module
class ImageDownloader:
  def __init__(self):
    pass

  def download_image(self, url: str, dest_path: str) -> bool:
    """Download image with retries and exponential backoff."""
    for attempt in range(MAX_RETRIES):
      try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(dest_path, "wb") as img_file:
          img_file.write(response.content)
        logger.info(f"Successfully downloaded image to {dest_path}")
        return True
      except Exception as e:
        logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES} failed to download {url}: {e}")
        if attempt < MAX_RETRIES - 1:
          time.sleep(RETRY_BACKOFF * (2**attempt))
    logger.error(f"Failed to download image from {url} after {MAX_RETRIES} attempts")
    return False


# Command-Line Argument Parsing
def parse_args() -> Tuple[str, str, str]:
  """Parse command-line arguments for directories."""
  parser = argparse.ArgumentParser(description="Generate images for Markdown articles and domain YAML files.")
  parser.add_argument("--md-dir", default=os.path.join(os.getcwd(), "content"), help="Directory to scan for Markdown files (default: ./content)")
  parser.add_argument("--domains-dir", default=os.path.join(os.getcwd(), "domains"), help="Directory to scan for domain YAML files (default: ./domains)")
  parser.add_argument("--assets-dir", help="Directory for images and YAML files (default: md-dir/assets)")
  args = parser.parse_args()

  md_dir = os.path.abspath(args.md_dir)
  domains_dir = os.path.abspath(args.domains_dir)
  assets_dir = os.path.abspath(args.assets_dir) if args.assets_dir else os.path.join(md_dir, "assets")
  return md_dir, domains_dir, assets_dir


# Main Orchestration
def main():
  # Parse arguments
  md_dir, domains_dir, assets_dir = parse_args()
  references_file = os.path.join(assets_dir, "image_references.yaml")
  prompts_file = os.path.join(assets_dir, "image_prompts.yaml")
  urls_file = os.path.join(assets_dir, "image_urls.yaml")

  # Initialize components
  client_wrapper = ClientWrapper()
  extraction = Extraction()
  prompt_manager = PromptManager()
  image_generator = ImageGenerator()
  image_downloader = ImageDownloader()
  client = client_wrapper.init_client()

  # Process Markdown files
  md_files = extraction.collect_markdown_files(md_dir)
  references = extraction.load_references(references_file)

  for md_file in md_files:
    logger.info(f"Processing Markdown file: {md_file}")
    file_key = os.path.basename(md_file)

    # Extract and save references
    pairs = extraction.extract_filenames(md_file)
    if not pairs:
      logger.info(f"No image references found in {md_file}")
      continue

    references[file_key] = [{"caption": caption, "filename": filename, "content": content} for caption, filename, content in pairs]
    extraction.save_references(references, references_file)

    # Process each image reference
    for pair in pairs:
      caption, filename, article_content = pair
      if not filename.endswith(".jpg"):
        logger.info(f"Skipping {filename} (not a .jpg file)")
        continue

      # Check if image already exists
      if os.path.exists(os.path.join(assets_dir, filename)):
        logger.info(f"Skipping {filename} (image already exists at destination)")
        continue

      logger.info(f"Processing image: {filename}")
      logger.info(f"Caption: {caption}")

      # Generate prompt
      prompts = prompt_manager.load_prompts(prompts_file)
      prompt = prompt_manager.generate_prompt_if_needed(client, caption, filename, article_content, prompts, prompts_file)
      if not prompt:
        logger.warning(f"No prompt generated for {filename}, skipping")
        continue

      # Generate and download image
      success = image_generator.generate_image(client, prompt, filename, assets_dir, urls_file, image_downloader)
      if not success:
        logger.warning(f"Failed to process {filename}")

  # Process domain YAML files
  yaml_files = extraction.collect_domain_yaml_files(domains_dir)
  for yaml_file in yaml_files:
    logger.info(f"Processing domain YAML file: {yaml_file}")
    file_key = os.path.basename(yaml_file)

    # Extract description and image info
    yaml_info = extraction.extract_yaml_info(yaml_file)
    if not yaml_info:
      logger.info(f"No valid description or image found in {yaml_file}")
      continue

    caption, filename = yaml_info
    if not filename.endswith(".jpg"):
      logger.info(f"Skipping {filename} (not a .jpg file)")
      continue

    # Check if image already exists
    if os.path.exists(os.path.join(assets_dir, filename)):
      logger.info(f"Skipping {filename} (image already exists at destination)")
      continue

    logger.info(f"Processing image: {filename}")
    logger.info(f"Caption: {caption}")

    # Use description as content for prompt generation
    article_content = caption

    # Generate prompt
    prompts = prompt_manager.load_prompts(prompts_file)
    prompt = prompt_manager.generate_prompt_if_needed(client, caption, filename, article_content, prompts, prompts_file)
    if not prompt:
      logger.warning(f"No prompt generated for {filename}, skipping")
      continue

    # Generate and download image
    success = image_generator.generate_image(client, prompt, filename, assets_dir, urls_file, image_downloader)
    if not success:
      logger.warning(f"Failed to process {filename}")


if __name__ == "__main__":
  main()
