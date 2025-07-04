import kagglehub
import os
import glob
import re
import shutil
import pandas as pd
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Step 1: Download the Flickr Image Dataset
print("Downloading Flickr Image Dataset...")
path = kagglehub.dataset_download("hsankesara/flickr-image-dataset")
print("Path to dataset files:", path)

# Step 2: Locate the CSV file and image directory
csv_path = os.path.join(path, 'flickr30k_images/results.csv')
image_dir = os.path.join(path, "flickr30k_images/flickr30k_images/flickr30k_images")

if not os.path.exists(csv_path):
    raise FileNotFoundError("Could not find flickr30k_images.csv")
if not os.path.exists(image_dir):
    raise FileNotFoundError("Could not find image directory in dataset.")

# Step 3: Create assets directory
base_dir = os.getcwd()
assets_dir = os.path.join(base_dir, "content", "assets")
os.makedirs(assets_dir, exist_ok=True)
print(f"Assets directory: {assets_dir}")

# Step 4: Read the CSV
print("Reading captions from CSV...")
df = pd.read_csv(csv_path, sep='|', skipinitialspace=True)
df.columns = df.columns.str.strip()  # Clean column names
# Keep unique image_name and comment pairs
df = df[['image_name', 'comment']].drop_duplicates(subset='image_name')
if df.empty:
    raise ValueError("CSV is empty or has no valid image_name/comment pairs.")

# Step 5: Collect all Markdown files
articles_glob = os.path.join(base_dir, "content", "*", "articles", "*.md")
md_files = glob.glob(articles_glob, recursive=True)
if not md_files:
    raise FileNotFoundError("No Markdown files found in content/*/articles/")

print(f"Found {len(md_files)} Markdown files")

# Step 6: Extract caption and filename pairs from Markdown files
def extract_filenames(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    caption_filename_pairs = []
    # Extract image references (e.g., ![alt text](image.jpg))
    img_matches = re.findall(r'!\[(.*?)\]\(([^)]+\.jpg)\)', content)
    for caption, filename in img_matches:
        # Use filename as fallback if caption is empty
        caption = caption.strip() if caption.strip() else os.path.basename(filename).replace('.jpg', '').replace('_', ' ')
        caption_filename_pairs.append((caption, os.path.basename(filename)))
    return caption_filename_pairs

all_caption_filename_pairs = []
for md_file in md_files:
    pairs = extract_filenames(md_file)
    all_caption_filename_pairs.extend(pairs)

if not all_caption_filename_pairs:
    print("No image references found in Markdown files. Exiting.")
    exit()

# Remove duplicates while preserving order
seen = set()
unique_pairs = []
for pair in all_caption_filename_pairs:
    if pair[1] not in seen:
        seen.add(pair[1])
        unique_pairs.append(pair)

print(f"Extracted {len(unique_pairs)} unique image references from Markdown files")

# Step 7: Clean caption for cosine similarity
def clean_text_for_similarity(text):
    # Lowercase and remove special characters, keep spaces
    return re.sub(r'[^a-zA-Z0-9\s]', ' ', str(text)).lower().strip()

# Step 8: Clean caption for output (per user requirements)
def clean_caption_for_output(text):
    # Keep only English alphabetic characters and spaces, preserve spaces
    cleaned = re.sub(r'[^a-zA-Z\s]', '', str(text)).lower()
    # Remove extra spaces but preserve single spaces between words
    return re.sub(r'\s+', ' ', cleaned).strip()

# Step 9: Process each Markdown image reference
for caption, filename in unique_pairs:
    if not filename.endswith('.jpg'):
        print(f"Skipping {filename} (not a .jpg file)")
        continue
    
    # Skip if the Markdown-expected filename already exists in assets
    dest_path = os.path.join(assets_dir, filename)
    if os.path.exists(dest_path):
        print(f"Skipped {filename} (already exists in {assets_dir})")
        continue
    
    # Clean Markdown caption for similarity comparison
    caption_clean = clean_text_for_similarity(caption)
    
    # Prepare captions for cosine similarity
    csv_captions = df['comment'].dropna().apply(clean_text_for_similarity).tolist()
    all_captions = [caption_clean] + csv_captions
    
    # Compute TF-IDF vectors
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(all_captions)
    
    # Compute cosine similarity between Markdown caption and all CSV captions
    similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    
    # Find the best match
    best_match_idx = np.argmax(similarities)
    best_match_score = similarities[best_match_idx]
    best_match_image_name = df.iloc[best_match_idx]['image_name']
    best_match_caption = df.iloc[best_match_idx]['comment']
    
    # Clean the CSV caption for output
    cleaned_caption = clean_caption_for_output(best_match_caption)
    
    # Log the match
    print(f"\nProcessing Markdown image: {filename}")
    print(f"Markdown caption: {caption}")
    print(f"Best match image: {best_match_image_name}")
    print(f"Best match CSV caption: {best_match_caption}")
    print(f"Cleaned caption for output: {cleaned_caption}")
    print(f"Cosine similarity score: {best_match_score:.4f}")
    
    # Step 10: Copy the matched image to assets directory
    src_image_path = os.path.join(image_dir, best_match_image_name)
    if os.path.exists(src_image_path):
        shutil.copy(src_image_path, dest_path)
        print(f"Copied {best_match_image_name} to {dest_path}")
        print(f"Associated caption: {cleaned_caption}")
    else:
        print(f"Source image {src_image_path} does not exist. Skipping.")