import glob
import json
import os
import re
import shutil
from pathlib import Path

import kagglehub
import nltk
import numpy as np
import pandas as pd
import requests
import torch
from dotenv import load_dotenv
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from PIL import Image
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import CLIPModel, CLIPProcessor

# Load environment variables
load_dotenv()

# Configuration
SIMILARITY_THRESHOLD = 0.5  # Cosine similarity for datasets
CLIP_THRESHOLD = 0.25  # CLIP similarity
HD_MIN_WIDTH = 1920  # Minimum width for HD
HD_MIN_HEIGHT = 1080  # Minimum height for HD
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
CLIP_SAMPLE_SIZE = 20  # Small sample for CLIP


# Step 1: Manage NLTK Resources
def setup_nltk():
  try:
    nltk.data.find("corpora/stopwords")
    nltk.data.find("corpora/wordnet")
    print("NLTK resources already installed.")
  except LookupError:
    print("Downloading NLTK resources (stopwords, wordnet)...")
    nltk.download("stopwords", quiet=True)
    nltk.download("wordnet", quiet=True)
  try:
    stop_words = set(stopwords.words("english"))
    lemmatizer = WordNetLemmatizer()
    return stop_words, lemmatizer
  except Exception as e:
    raise RuntimeError(f"Failed to initialize NLTK: {e}")


stop_words, lemmatizer = setup_nltk()

# Step 2: Initialize CLIP (Minimal)
try:
  clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
  clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
except Exception as e:
  print(f"Failed to initialize CLIP: {e}. Skipping CLIP matching.")
  clip_model = None
  clip_processor = None

# Step 3: Download Datasets
print("Downloading Flickr30k Dataset...")
flickr_path = kagglehub.dataset_download("hsankesara/flickr-image-dataset")
print("Downloading COCO 2017 Dataset...")
coco_path = kagglehub.dataset_download("awsaf49/coco-2017-dataset")
print("Dataset paths:", flickr_path, coco_path)

# Step 4: Locate Files
flickr_csv = os.path.join(flickr_path, "flickr30k_images/results.csv")
flickr_image_dir = os.path.join(flickr_path, "flickr30k_images/flickr30k_images/flickr30k_images")
coco_annotations = os.path.join(coco_path, "coco2017/annotations/captions_train2017.json")
coco_image_dir = os.path.join(coco_path, "coco2017/train2017")

for path in [flickr_csv, flickr_image_dir, coco_annotations, coco_image_dir]:
  if not os.path.exists(path):
    raise FileNotFoundError(f"Could not find {path}")

# Step 5: Create Assets Directory
base_dir = os.getcwd()
assets_dir = os.path.join(base_dir, "content", "assets")
os.makedirs(assets_dir, exist_ok=True)
print(f"Assets directory: {assets_dir}")


# Step 6: Process Datasets (HD Filtering)
def is_hd_image(image_path):
  try:
    with Image.open(image_path) as img:
      width, height = img.size
      return width >= HD_MIN_WIDTH or height >= HD_MIN_HEIGHT
  except Exception:
    return False


# Flickr30k
print("Processing Flickr30k (HD only)...")
flickr_df = pd.read_csv(flickr_csv, sep="|", skipinitialspace=True)
flickr_df.columns = flickr_df.columns.str.strip()
flickr_df = flickr_df[["image_name", "comment"]].drop_duplicates(subset="image_name")
flickr_df["image_path"] = flickr_df["image_name"].apply(lambda x: os.path.join(flickr_image_dir, x))
flickr_df["is_hd"] = flickr_df["image_path"].apply(is_hd_image)
flickr_df = flickr_df[flickr_df["is_hd"]].assign(dataset="flickr")

# COCO
print("Processing COCO (HD only)...")
with open(coco_annotations, "r") as f:
  coco_data = json.load(f)

image_metadata = {img["id"]: img for img in coco_data["images"]}
coco_captions = []
for ann in coco_data["annotations"]:
  image_id = ann["image_id"]
  if image_id in image_metadata:
    img = image_metadata[image_id]
    if img["width"] >= HD_MIN_WIDTH or img["height"] >= HD_MIN_HEIGHT:
      coco_captions.append(
        {"image_name": f"{image_id:012d}.jpg", "comment": ann["caption"], "image_path": os.path.join(coco_image_dir, f"{image_id:012d}.jpg")}
      )

coco_df = pd.DataFrame(coco_captions).drop_duplicates(subset="image_name").assign(dataset="coco")

# Combine Datasets
df = pd.concat([flickr_df, coco_df], ignore_index=True)
if df.empty:
  print("Warning: No HD images found in datasets. Relying on Unsplash.")
else:
  print(f"Found {len(df)} HD images.")

# Step 7: Collect Markdown Files
articles_glob = os.path.join(base_dir, "content", "*", "articles", "*.md")
md_files = glob.glob(articles_glob, recursive=True)
if not md_files:
  raise FileNotFoundError("No Markdown files found.")

print(f"Found {len(md_files)} Markdown files")


# Step 8: Extract Caption-Filename Pairs
def extract_filenames(file_path):
  with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()
  pairs = []
  img_matches = re.findall(r"!\[(.*?)\]\(([^)]+\.jpg)\)", content)
  for caption, filename in img_matches:
    caption = caption.strip() or os.path.basename(filename).replace(".jpg", "").replace("_", " ")
    pairs.append((caption, os.path.basename(filename)))
  return pairs


all_pairs = []
for md_file in md_files:
  all_pairs.extend(extract_filenames(md_file))

if not all_pairs:
  print("No image references found. Exiting.")
  exit()

seen = set()
unique_pairs = [pair for pair in all_pairs if not (pair[1] in seen or seen.add(pair[1]))]
print(f"Extracted {len(unique_pairs)} unique image references")


# Step 9: Caption Preprocessing
def clean_text_for_similarity(text):
  text = re.sub(r"[^a-zA-Z0-9\s]", " ", str(text)).lower().strip()
  words = text.split()
  words = [lemmatizer.lemmatize(w) for w in words if w not in stop_words]
  return " ".join(words)


def clean_caption_for_output(text):
  cleaned = re.sub(r"[^a-zA-Z\s]", "", str(text)).lower()
  return re.sub(r"\s+", " ", cleaned).strip()


# Step 10: Unsplash Search
def search_unsplash(query):
  if not UNSPLASH_ACCESS_KEY:
    print("Unsplash API key missing.")
    return None
  url = "https://api.unsplash.com/search/photos"
  headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
  params = {"query": query, "per_page": 1, "orientation": "landscape"}
  try:
    response = requests.get(url, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    results = response.json()["results"]
    if results:
      return (results[0]["urls"]["full"], results[0]["alt_description"] or query)
    return None
  except Exception as e:
    print(f"Unsplash search failed: {e}")
    return None


# Step 11: CLIP Similarity
def compute_clip_similarity(caption, image_paths):
  if not clip_model or not clip_processor:
    return np.zeros(len(image_paths))
  try:
    images = [Image.open(p) for p in image_paths]
    inputs = clip_processor(text=[caption], images=images, return_tensors="pt", padding=True)
    with torch.no_grad():
      outputs = clip_model(**inputs)
    similarities = outputs.logits_per_image.softmax(dim=1).cpu().numpy().flatten()
    return similarities
  except Exception as e:
    print(f"CLIP processing failed: {e}")
    return np.zeros(len(image_paths))


# Step 12: Process Markdown Images
for caption, filename in unique_pairs:
  if not filename.endswith(".jpg"):
    print(f"Skipping {filename} (not a .jpg file)")
    continue

  base_dest_path = os.path.join(assets_dir, filename)
  if os.path.exists(base_dest_path):
    print(f"Skipped {filename} (exists)")
    continue

  print(f"\nProcessing: {filename}")
  print(f"Caption: {caption}")
  caption_clean = clean_text_for_similarity(caption)

  # Dataset Matching
  dataset_match = None
  csv_captions = df["comment"].dropna().apply(clean_text_for_similarity).tolist()
  if csv_captions:
    all_captions = [caption_clean] + csv_captions
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(all_captions)
    similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    best_idx = np.argmax(similarities)
    if similarities[best_idx] >= SIMILARITY_THRESHOLD:
      dataset_match = (
        df.iloc[best_idx]["image_name"],
        df.iloc[best_idx]["comment"],
        df.iloc[best_idx]["image_path"],
        similarities[best_idx],
        df.iloc[best_idx]["dataset"],
      )

  # Unsplash Matching
  unsplash_result = search_unsplash(caption_clean)

  # CLIP Matching
  clip_match = None
  available_images = df["image_path"].dropna().tolist()
  if available_images and clip_model:
    sample_images = random.sample(available_images, min(CLIP_SAMPLE_SIZE, len(available_images)))
    clip_similarities = compute_clip_similarity(caption, sample_images)
    best_idx = np.argmax(clip_similarities)
    if clip_similarities[best_idx] >= CLIP_THRESHOLD:
      clip_match = (
        df[df["image_path"] == sample_images[best_idx]]["image_name"].iloc[0],
        df[df["image_path"] == sample_images[best_idx]]["comment"].iloc[0],
        sample_images[best_idx],
        clip_similarities[best_idx],
        df[df["image_path"] == sample_images[best_idx]]["dataset"].iloc[0],
      )

  # Download/Copy Matches
  base, ext = os.path.splitext(filename)

  if dataset_match:
    image_name, csv_caption, image_path, score, dataset = dataset_match
    cleaned_caption = clean_caption_for_output(csv_caption)
    dest_path = os.path.join(assets_dir, f"{base}_dataset{ext}")
    print(f"Dataset Match ({dataset}):")
    print(f"  Image: {image_name}")
    print(f"  Caption: {csv_caption}")
    print(f"  Cleaned: {cleaned_caption}")
    print(f"  Score: {score:.4f}")
    if os.path.exists(image_path):
      shutil.copy(image_path, dest_path)
      print(f"  Copied to {dest_path}")
    else:
      print(f"  Image {image_path} not found.")

  if unsplash_result:
    url, description = unsplash_result
    cleaned_caption = clean_caption_for_output(description)
    dest_path = os.path.join(assets_dir, f"{base}_unsplash{ext}")
    print(f"Unsplash Match:")
    print(f"  Caption: {description}")
    print(f"  Cleaned: {cleaned_caption}")
    try:
      response = requests.get(url, timeout=10)
      response.raise_for_status()
      with open(dest_path, "wb") as f:
        f.write(response.content)
      print(f"  Downloaded to {dest_path}")
    except Exception as e:
      print(f"  Download failed: {e}")

  if clip_match:
    image_name, csv_caption, image_path, score, dataset = clip_match
    cleaned_caption = clean_caption_for_output(csv_caption)
    dest_path = os.path.join(assets_dir, f"{base}_clip{ext}")
    print(f"CLIP Match ({dataset}):")
    print(f"  Image: {image_name}")
    print(f"  Caption: {csv_caption}")
    print(f"  Cleaned: {cleaned_caption}")
    print(f"  Score: {score:.4f}")
    if os.path.exists(image_path):
      shutil.copy(image_path, dest_path)
      print(f"  Copied to {dest_path}")
    else:
      print(f"  Image {image_path} not found.")
