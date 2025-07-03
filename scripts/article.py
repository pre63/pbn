import os
from datetime import datetime

import yaml
from slugify import slugify  # From python-slugify, don’t screw this up
from xai_sdk import Client
from xai_sdk.chat import system, user

# xAI API configuration (we call this LAST, so don’t burn my credits)
XAI_API_KEY = os.getenv("XAI_API_KEY")  # Yo, set this or we’re hosed
if not XAI_API_KEY:
  raise ValueError("XAI_API_KEY not set. Go beg xAI for one, you cheapskate.")


def load_domain_config(domain):
  """Load domain config from YAML. Don’t botch the paths, alright?"""
  config_path = f"domains/{domain}.yml"
  if not os.path.exists(config_path):
    raise FileNotFoundError(f"Config for {domain} not found at {config_path}. Did you run the Fish command?")
  try:
    with open(config_path, "r") as f:
      config = yaml.safe_load(f)
      if config is None:
        raise ValueError(f"YAML file {config_path} is empty or contains only comments. Add a valid config, you slacker.")
      if not isinstance(config, dict):
        raise ValueError(f"YAML file {config_path} doesn’t contain a valid dictionary. Fix your structure, genius.")
      return config
  except yaml.YAMLError as e:
    raise ValueError(f"Invalid YAML in {config_path}: {str(e)}. YAML ain’t rocket science, fix it.")


def load_article_specs(domain):
  """Load article specs from gen.yml. No file? No articles. Don’t cry to me."""
  gen_path = f"content/{domain}/gen.yml"
  if not os.path.exists(gen_path):
    raise FileNotFoundError(f"Article specs for {domain} not found at {gen_path}. Go write one, lazybones.")
  try:
    with open(gen_path, "r") as f:
      data = yaml.safe_load(f)
      if data is None:
        raise ValueError(f"YAML file {gen_path} is empty or contains only comments. Add some articles, you slacker.")
      if not isinstance(data, dict):
        raise ValueError(f"YAML file {gen_path} doesn’t contain a valid dictionary. Fix your structure, genius.")
      articles = data.get("articles", [])
      if not articles:
        print(f"No articles in {gen_path}. Why even have this domain, huh?")
      return articles
  except yaml.YAMLError as e:
    raise ValueError(f"Invalid YAML in {gen_path}: {str(e)}. C’mon, YAML’s not that hard.")


def validate_article_specs(articles, domain, config):
  """Validate article specs and prep front matter locally. No API calls yet, we’re not made of credits."""
  validated_articles = []
  articles_path = config["content"]["articles_path"]

  # Ensure articles directory exists
  os.makedirs(articles_path, exist_ok=True)

  for article in articles:
    # Check required fields
    required_fields = ["title", "topic", "keywords", "description", "author"]
    missing = [field for field in required_fields if field not in article or not article[field]]
    if missing:
      print(f"Skipping article in {domain}: Missing fields {missing} in {article.get('title', 'Untitled')}. Get your act together.")
      continue

    # Generate slug
    title = article["title"]
    slug = slugify(title, max_length=50, lowercase=True, separator="-")
    file_path = os.path.join(articles_path, f"{slug}.md")

    # Check for existing file
    if os.path.exists(file_path):
      print(f"Article {file_path} already exists. Not touching it, slacker.")
      continue

    # Prepare front matter
    front_matter = {
      "title": title,
      "slug": slug,
      "author": article["author"],
      "date": datetime.now().strftime("%Y-%m-%d"),
      "meta_description": article["description"],
      "meta_keywords": article["keywords"],
      "og_title": f"{title} - {config['site']['name']}",
      "og_description": article["description"],
      "og_image": article.get("og_image", config["content"]["default_image"]),
    }

    validated_articles.append(
      {
        "front_matter": front_matter,
        "file_path": file_path,
        "topic": article["topic"],
        "keywords": article["keywords"],
        "description": article["description"],
        "author": article["author"],
      }
    )

  return validated_articles


def generate_article(domain, topic, keywords, description, author, config):
  """Generate an NYT-style article with Grok 3 Mini. Only called after validation, so we’re spending credits wisely."""
  client = Client(api_key=XAI_API_KEY, timeout=300)  # 5-minute timeout, don’t hang forever
  chat = client.chat.create(model="grok-3-mini", temperature=0.8)  # Creative but not unhinged

  # Define author personality based on pseudonym
  personality_map = {
    "Joanna Aucton": "A witty, sharp-tongued observer with a knack for compelling narratives, inspired by Jane Austen’s anonymous ‘A Lady’ pseudonym.",
    "Jonah Stynebeck": "A grounded, pragmatic writer with dry wit and practical insights, riffing on John Steinbeck’s obscure ‘Amnesia Glasscock’ alias.",
    "Silas Twaine": "A folksy, storytelling voice with warmth and a touch of humor, echoing Mark Twain’s ‘Sieur Louis de Conte’ pseudonym.",
    "Emmeline Dickenson": "A reflective, poetic writer with deep, introspective takes, inspired by Emily Dickinson’s anonymous publications.",
    "Alec Dumass": "An energetic, bold narrator with dramatic, engaging prose, channeling Alexandre Dumas’ ‘Dumas père’ legacy.",
    "Eliza Alcotte": "A clear, motivational writer with a nurturing yet no-nonsense style, drawing from Louisa May Alcott’s ‘A.M. Barnard’ pseudonym.",
    "Earnest Hemmingweigh": "A direct, muscular voice focused on clarity and real-world implications, inspired by Ernest Hemingway’s ‘John Hadley Nicanor’ alias.",
    "Marcus Twyne": "A clever, slightly sardonic writer blending data and storytelling, twisting Mark Twain’s ‘Thomas Jefferson Snodgrass’ pseudonym.",
    "Lara Wylde": "A passionate, vivid storyteller with an optimistic, forward-looking tone, inspired by Laura Ingalls Wilder’s anonymous contributions.",
    "Davin Thorow": "A thoughtful, deliberate writer emphasizing practical solutions, echoing Henry David Thoreau’s anonymous essays.",
    "Marian Shelleigh": "A visionary writer with a bold, futuristic perspective grounded in reason, drawing from Mary Shelley’s anonymous reviews.",
    "Sara Brontee": "A lyrical yet pragmatic voice, emphasizing clarity and actionable insights, inspired by Charlotte Brontë’s ‘Currer Bell’ pseudonym.",
  }
  author_personality = personality_map.get(author, "A seasoned journalist with a sharp, authoritative voice, ready to cut through the noise.")

  # System prompt for author personality and editorial style
  chat.append(
    system(
      f"""
    You are {author}, a {author_personality} Write an editorial with a distinct, opinionated voice that reflects a center-right perspective on public issues (favoring free markets, limited government, and traditional values, avoiding 'woke' framing or social justice rhetoric). Maintain a professional and authoritative tone suitable for a New York Times editorial.
    """
    )
  )

  # User prompt for article content
  chat.append(
    user(
      f"""
    Write an 800–1200 word editorial article in the style of a New York Times editorial. The article should be engaging, well-researched, narrative-driven, and balanced, with a clear structure (introduction, analysis, evidence, conclusion). The topic is "{topic}" for the website {config['site']['name']}. Focus on the following description: {description}. Incorporate these keywords: {', '.join(keywords)}. 

    - Include 2–3 image placeholders in Markdown (e.g., `![Quantum processor in action](/content/assets/quantum-processor.jpg)`) with specific, fictional image names relevant to the topic (no generic 'placeholder.jpg'). Use descriptive captions that enhance the narrative.
    - Embed 3–5 authoritative, external sources as Markdown links (e.g., `[Source Name](https://example.com)`) seamlessly within paragraphs, citing credible outlets like IEEE, Wall Street Journal, or industry blogs. Ensure links are relevant to the topic.
    - For public issues (e.g., policy, economics, social trends), adopt a center-right perspective, emphasizing free-market solutions, limited government intervention, and traditional values, while avoiding extreme partisanship or 'woke' framing.
    - Format the content in Markdown with appropriate headings (e.g., # for main title, ## for sections) and paragraphs. Use American English and adhere to journalistic standards.
    """
    )
  )

  try:
    response = chat.sample()
    content = response.content
    return content
  except Exception as e:
    print(f"Error generating article for {topic}: {str(e)}. Grok’s throwing a digital tantrum.")
    return None


def save_article(front_matter, file_path, content):
  """Save article as Markdown with front matter. Don’t botch the save, we’re almost done."""
  markdown_content = f"""---
{yaml.dump(front_matter, sort_keys=False)}
---
{content}
"""

  try:
    with open(file_path, "w") as f:
      f.write(markdown_content)
    print(f"Saved article: {file_path}. Go bask in your SEO glory.")
  except Exception as e:
    print(f"Error saving article to {file_path}: {str(e)}. Disk full or what, nerd?")


import traceback


def main():
  """Generate and save articles for our PBN. Don’t waste my API credits, you hear?"""
  domains = ["connectnews24.com", "hilltopsnewspaper.com", "powersporta.com", "spotnews24.com", "terrafirmanews.com", "voltapowers.com"]

  for domain in domains:
    print(f"Processing articles for {domain}. Grab a coffee, this might take a sec...")
    try:
      # Load and validate all local data first
      config = load_domain_config(domain)
      articles = load_article_specs(domain)
      if not articles:
        continue

      validated_articles = validate_article_specs(articles, domain, config)
      if not validated_articles:
        print(f"No valid articles to generate for {domain}. Fix your gen.yml, slacker.")
        continue

      # Now burn some credits on API calls
      for article in validated_articles:
        print(f"Generating article: {article['front_matter']['title']}. Time to make Grok 3 Mini earn its keep!")
        content = generate_article(domain, article["topic"], article["keywords"], article["description"], article["author"], config)
        if content:
          save_article(article["front_matter"], article["file_path"], content)
        else:
          print(f"Skipping {article['front_matter']['title']}. Grok’s probably off sipping digital lattes.")
    except FileNotFoundError as e:
      print(f"Error: {str(e)}. Fix your file structure before I lose it.")
      print("Stack trace:")
      traceback.print_exc()
    except ValueError as e:
      print(f"Error: {str(e)}. YAML’s not rocket science, get it right.")
      print("Stack trace:")
      traceback.print_exc()
    except Exception as e:
      print(f"Unexpected error for {domain}: {str(e)}. What did you break this time?")
      print("Stack trace:")
      traceback.print_exc()


if __name__ == "__main__":
  main()
