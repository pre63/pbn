#!/usr/bin/env python3

import random
import os
from datetime import datetime, timedelta
import frontmatter
import shutil
import logging
from glob import glob

# Setup logging for snarky, SEO-juiced output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Current date for fallback (today is July 3, 2025, 11:26 AM PDT)
CURRENT_DATE = datetime.now().strftime('%Y-%m-%d')

def discover_sites(content_root='content'):
    """Infer sites from content/*/articles directories. No gen.yml, just filesystem swagger."""
    sites = {}
    article_dirs = glob(f"{content_root}/*/articles")
    for article_dir in article_dirs:
        domain = article_dir.split('/')[1]  # Extract domain from content/[domain]/articles
        site_name = domain.replace('.com', '').replace('-', ' ').title()
        sites[domain] = {
            'name': site_name,
            'articles_path': f"content/{domain}/articles",
            'domain': f"https://{domain}"
        }
    if not sites:
        logger.error("No sites found in content/. Did someone torch the articles folder?")
    else:
        logger.info(f"Discovered {len(sites)} sites: {list(sites.keys())}")
    return sites

def list_markdown_files(articles_path):
    """List .md filenames in the articles directory. Names only, no memory hogging."""
    try:
        markdown_files = glob(f"{articles_path}/*.md")
        if not markdown_files:
            logger.warning(f"No .md files found in {articles_path}. Ghost town vibes.")
        return markdown_files
    except Exception as e:
        logger.error(f"Failed to list files in {articles_path}: {e}. Filesystem’s throwing shade.")
        return []

def sample_files(files, num_samples=10):
    """Sample 10% of filenames (min 10). Random, like a plot twist in a Hollywood blockbuster."""
    num_samples = max(num_samples, len(files) // 10)  # At least 10% or 10
    if len(files) < num_samples:
        logger.warning(f"Only {len(files)} files available, sampling all instead of {num_samples}")
        return files
    return random.sample(files, num_samples)

def copy_and_update_article(source_file, original_site, target_site):
    """Copy .md file, update date, prepend editorial header with proper backlink, add original metadata."""
    # Use the original slug (filename without path or .md)
    slug = os.path.basename(source_file).replace('.md', '')
    target_file = f"{target_site['articles_path']}/{slug}.md"

    # Parse source file’s frontmatter to get the original date
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)
    except Exception as e:
        logger.error(f"Failed to parse {source_file}: {e}. Skipping, no backlink tears shed.")
        return

    if 'date' not in post.metadata:
        logger.warning(f"No date in {source_file}. Using {CURRENT_DATE} as fallback.")
        original_date = CURRENT_DATE
    else:
        original_date = str(post.metadata['date'])

    # Update date: original date + 2 weeks
    try:
        pub_date = datetime.strptime(original_date, '%Y-%m-%d')
        new_date = (pub_date + timedelta(weeks=2)).strftime('%Y-%m-%d')
    except ValueError:
        logger.warning(f"Invalid date format in {source_file}: {original_date}. Using {CURRENT_DATE}")
        new_date = CURRENT_DATE

    # Editorial header with backlink to the actual article URL
    original_url = f"{original_site['domain']}/post/{slug}"
    cross_post_header = (
        f"_This article originally appeared in [{original_site['name']}]({original_url}) "
        f"on {original_date}. It is republished here with permission._\n\n"
    )

    # Prepend header to original content
    new_content = cross_post_header + post.content

    # Update frontmatter with original metadata plus new fields
    post.metadata['date'] = new_date
    post.metadata['original_site'] = original_site['name']
    post.metadata['original_url'] = original_url
    post.content = new_content

    # Ensure target directory exists
    os.makedirs(target_site['articles_path'], exist_ok=True)

    # Save the updated file
    try:
        with open(target_file, 'w', encoding='utf-8') as f:
            frontmatter.dump(post, f)
        logger.info(f"Cross-posted '{post.metadata.get('title', slug)}' to {target_file}. Backlink SEO juice flowing!")
    except Exception as e:
        logger.error(f"Failed to save {target_file}: {e}. Someone’s getting a 404 in SEO hell.")

def cross_post_articles(target_site_name, sites):
    """Cross-post 10% of .md files from other sites to the target site’s blog. Backlinks for days!"""
    if target_site_name not in sites:
        logger.error(f"Target site {target_site_name} not found. Did you botch the domain?")
        return

    target_site = sites[target_site_name]
    logger.info(f"Cross-posting to {target_site_name}. Get ready for a backlink bonanza!")

    # Sample .md files from other sites
    for site_name, site_info in sites.items():
        if site_name == target_site_name:
            continue  # Skip the target site

        logger.info(f"Sampling .md files from {site_name}...")
        files = list_markdown_files(site_info['articles_path'])
        sampled_files = sample_files(files, num_samples=10)

        for source_file in sampled_files:
            logger.info(f"Cross-posting {os.path.basename(source_file)} from {site_name} to {target_site_name}")
            copy_and_update_article(source_file, site_info, target_site)

    logger.info(f"Finished cross-posting to {target_site_name}. Content empire juiced up with backlinks!")

def main():
    """Run the cross-posting script for all sites. Let’s sling backlinks like a digital SEO ninja!"""
    sites = discover_sites()
    if not sites:
        logger.error("No sites found in content/. Filesystem’s giving us the cold shoulder.")
        return

    for site_name in sites:
        cross_post_articles(site_name, sites)

if __name__ == "__main__":
    logger.info("Starting cross-posting script. Strap in, we’re slinging .md files with backlink swagger!")
    main()
    logger.info("Cross-posting complete. Backlinks zapped across sites like a snarky SEO lightning bolt!")