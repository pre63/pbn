import kagglehub
import os
import glob
import re
import zipfile
import shutil
from fuzzywuzzy import fuzz
import pandas as pd
from pathlib import Path

# Step 1: Download the Flickr Image Dataset
print("Downloading Flickr Image Dataset...")
path = kagglehub.dataset_download("hsankesara/flickr-image-dataset")
print("Path to dataset files:", path)

# Step 2: Find and unzip the dataset
zip_path = None
for root, dirs, files in os.walk(path):
    for file in files:
        if file.endswith('.zip'):
            zip_path = os.path.join(root, file)
            break
if not zip_path:
    raise FileNotFoundError("No ZIP file found in the dataset directory.")

extract_dir = os.path.join(path, "extracted")
os.makedirs(extract_dir, exist_ok=True)

print(f"Unzipping {zip_path} to {extract_dir}...")
with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(extract_dir)

# Step 3: Locate the CSV file and image directory
csv_path = None
image_dir = None
for root, dirs, files in os.walk(extract_dir):
    for file in files:
        if file == 'flickr30k_images.csv':
            csv_path = os.path.join(root, file)
        if file.endswith('.jpg'):
            image_dir = os.path.dirname(os.path.join(root, file))
            break

if not csv_path:
    raise FileNotFoundError("Could not find flickr30k_images.csv")
if not image_dir:
    raise FileNotFoundError("Could not find image directory in dataset.")

# Step 4: Move images to content/assets/, skipping existing files
base_dir = os.getcwd()
assets_dir = os.path.join(base_dir, "content", "assets")
os.makedirs(assets_dir, exist_ok=True)
print(f"Assets directory: {assets_dir}")

print("Moving images to content/assets/...")
image_count = 0
for file in os.listdir(image_dir):
    if file.endswith('.jpg'):
        src_path = os.path.join(image_dir, file)
        dest_path = os.path.join(assets_dir, file)
        if not os.path.exists(dest_path):  # Skip if file already exists
            shutil.move(src_path, dest_path)
            image_count += 1
        else:
            print(f"Skipped {file} (already exists in {assets_dir})")
print(f"Moved {image_count} new images to {assets_dir}")

# Step 5: Read the CSV
print("Reading captions from CSV...")
df = pd.read_csv(csv_path, sep='|', skipinitialspace=True)
df.columns = df.columns.str.strip()  # Clean column names
# Keep unique image_name and comment pairs
df = df[['image_name', 'comment']].drop_duplicates(subset='image_name')
if df.empty:
    raise ValueError("CSV is empty or has no valid image_name/comment pairs.")

# Step 6: Collect all Markdown files
articles_glob = os.path.join(base_dir, "content", "*", "articles", "*.md")
md_files = glob.glob(articles_glob, recursive=True)
if not md_files:
    raise FileNotFoundError("No Markdown files found in content/*/articles/")

print(f"Found {len(md_files)} Markdown files")

# Step 7: Extract filenames from Markdown files
def extract_filenames(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    filenames = set()
    # Extract image references (e.g., ![alt text](image.jpg))
    img_matches = re.findall(r'!\[.*?\]\((.*?)\)', content)
    for match in img_matches:
        if match.endswith('.jpg'):
            filenames.add(os.path.basename(match))
    # Extract filenames from body text (e.g., two_dogs_playing_in_grass.jpg)
    text_matches = re.findall(r'(\b[\w_]+\.jpg\b)', content)
    filenames.update(text_matches)
    return filenames

all_filenames = set()
for md_file in md_files:
    filenames = extract_filenames(md_file)
    all_filenames.update(filenames)

if not all_filenames:
    print("No .jpg filenames found in Markdown files. Exiting.")
    exit()

print(f"Extracted {len(all_filenames)} unique .jpg filenames from Markdown files")

# Step 8: Match filenames to CSV captions and rank by similarity
def clean_text(text):
    # Remove special characters, lowercase, replace spaces with underscores
    return re.sub(r'[^a-zA-Z0-9\s]', '', str(text)).lower().replace(' ', '_')

matches = []

# Match filenames to CSV captions
for filename in all_filenames:
    if not filename.endswith('.jpg'):
        continue
    
    # Skip if the Markdown-expected filename already exists in assets
    dest_path = os.path.join(assets_dir, filename)
    if os.path.exists(dest_path):
        print(f"Skipped {filename} (already exists in {assets_dir})")
        continue
    
    # Get filename without extension
    filename_base = filename.replace('.jpg', '')
    filename_clean = clean_text(filename_base)
    
    # Find best matching caption in CSV
    best_match_score = 0
    best_match_caption = None
    best_match_image_name = None
    
    for _, row in df.iterrows():
        caption = row['comment']
        image_name = row['image_name']
        if pd.isna(caption) or pd.isna(image_name):
            continue
        caption_clean = clean_text(caption)
        score = fuzz.token_sort_ratio(filename_clean, caption_clean)
        if score > best_match_score:
            best_match_score = score
            best_match_caption = caption
            best_match_image_name = image_name
    
    if best_match_image_name:
        matches.append({
            'md_filename': filename,
            'image_name': best_match_image_name,
            'caption': best_match_caption,
            'score': best_match_score
        })
    else:
        print(f"No caption match found for {filename}")

# Step 9: Select and copy the top-ranked image
if not matches:
    print("No new matches found between Markdown filenames and CSV captions. Exiting.")
    exit()

# Sort matches by similarity score (highest first)
matches.sort(key=lambda x: x['score'], reverse=True)
top_match = matches[0]

# Copy the top-ranked image to content/assets/ with the Markdown-expected filename
src_image_path = os.path.join(assets_dir, top_match['image_name'])
dest_image_path = os.path.join(assets_dir, top_match['md_filename'])

if os.path.exists(src_image_path):
    if not os.path.exists(dest_image_path):  # Double-check to avoid overwriting
        shutil.copy2(src_image_path, dest_image_path)
        print(f"Copied top-ranked image {top_match['image_name']} to {dest_image_path} "
              f"(matched '{top_match['caption']}', score: {top_match['score']})")
    else:
        print(f"Skipped copying {top_match['md_filename']} (already exists in {assets_dir})")
else:
    print(f"Top-ranked image {top_match['image_name']} not found in {assets_dir}")

# Step 10: Summary
print(f"Processed {len(matches)} new filename matches")
if os.path.exists(dest_image_path):
    print(f"Top-ranked image copied to {assets_dir} with filename {top_match['md_filename']}")
else:
    print("No new top-ranked image copied (either no match or file already exists).")