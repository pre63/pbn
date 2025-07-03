import os
import yaml
from datetime import datetime
from slugify import slugify
from openai import OpenAI

# xAI API configuration
XAI_API_KEY = os.getenv("XAI_API_KEY")  # Set this in your environment
if not XAI_API_KEY:
    raise ValueError("XAI_API_KEY environment variable not set. Go get one, genius.")

client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
)

def load_domain_config(domain):
    """Load domain configuration from YAML. Don’t mess up the file paths, okay?"""
    config_path = f"domains/{domain}.yml"
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file for {domain} not found at {config_path}. Did you forget to run `make`?")
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def load_article_specs(domain):
    """Load article specs from gen.yml. No gen.yml? No articles. Simple as that."""
    gen_path = f"content/{domain}/gen.yml"
    if not os.path.exists(gen_path):
        raise FileNotFoundError(f"Article specs file for {domain} not found at {gen_path}. Go write one.")
    with open(gen_path, 'r') as f:
        data = yaml.safe_load(f)
        return data.get('articles', [])

def generate_article(domain, title, topic, keywords, description, author, og_image):
    """Generate an NYT-style article with Grok. Don’t expect Pulitzer-worthy prose on the first try."""
    config = load_domain_config(domain)
    
    # NYT editorial style prompt
    prompt = f"""
    Write an 800–1200 word editorial article in the style of a New York Times editorial. The article should be engaging, well-researched, narrative-driven, and balanced, with a clear structure (introduction, analysis, evidence, conclusion). The topic is "{topic}" for the website {config['site']['name']}. Focus on the following description: {description}. Incorporate these keywords: {', '.join(keywords)}. Use a professional and authoritative tone, suitable for an informed audience. Include real-world examples, data, or anecdotes where relevant, but avoid fabricating specific details unless plausible. Format the content in Markdown with appropriate headings (e.g., # for main title, ## for sections) and paragraphs. Ensure the article is written in American English and adheres to journalistic standards.
    """
    
    try:
        completion = client.chat.completions.create(
            model="grok-3",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,  # Approx. 800–1200 words
            temperature=0.7,  # Not too wild, not too boring
        )
        content = completion.choices[0].message.content
        return content
    except Exception as e:
        print(f"Error generating article for {title}: {str(e)}. API acting up again?")
        return None

def save_article(domain, title, topic, keywords, description, author, og_image, content):
    """Save the article as a Markdown file with front matter. Don’t overwrite my masterpieces."""
    config = load_domain_config(domain)
    articles_path = config['content']['articles_path']
    
    # Generate slug and truncate to 50 chars if needed
    slug = slugify(title, lowercase=True)
    if len(slug) > 50:
        slug = slug[:50].rsplit('-', 1)[0]  # Truncate at last hyphen
    
    # Ensure articles directory exists
    os.makedirs(articles_path, exist_ok=True)
    
    # Check for existing file to avoid overwrites
    file_path = os.path.join(articles_path, f"{slug}.md")
    if os.path.exists(file_path):
        print(f"Article {file_path} already exists. Not gonna touch it.")
        return
    
    # Create front matter
    front_matter = {
        'title': title,
        'slug': slug,
        'author': author,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'meta_description': description,
        'meta_keywords': keywords,
        'og_title': f"{title} - {config['site']['name']}",
        'og_description': description,
        'og_image': og_image or config['content']['default_image']
    }
    
    # Format Markdown file with front matter
    markdown_content = f"""---
{yaml.dump(front_matter, sort_keys=False)}
---
{content}
"""
    
    # Save to file
    try:
        with open(file_path, 'w') as f:
            f.write(markdown_content)
        print(f"Saved article: {file_path}. Go check it out, it’s probably awesome.")
    except Exception as e:
        print(f"Error saving article {title} to {file_path}: {str(e)}. Check your permissions, dude.")

def main():
    """Generate and save articles for our PBN domains. Don’t screw this up."""
    domains = [
        "connectnews24.com",
        "hilltopsnewspaper.com",
        "powersporta.com",
        "spotnews24.com",
        "terrafirmanews.com",
        "voltapowers.com"
    ]
    
    for domain in domains:
        print(f"Processing articles for {domain}. Hold onto your keyboard...")
        try:
            articles = load_article_specs(domain)
            if not articles:
                print(f"No articles in {domain}/gen.yml. What’s the point of this domain, then?")
                continue
            for article in articles:
                title = article['title']
                topic = article['topic']
                keywords = article['keywords']
                description = article['description']
                author = article['author']
                og_image = article.get('og_image', '')
                
                print(f"Generating article: {title}. This better be good.")
                content = generate_article(domain, title, topic, keywords, description, author, og_image)
                if content:
                    save_article(domain, title, topic, keywords, description, author, og_image, content)
                else:
                    print(f"Skipping {title}. Grok probably choked on it.")
        except FileNotFoundError as e:
            print(f"Error: {str(e)}. Fix your file structure, stat.")
        except Exception as e:
            print(f"Unexpected error for {domain}: {str(e)}. Ugh, what now?")

if __name__ == "__main__":
    main()