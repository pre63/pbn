import os

import frontmatter
import markdown
import yaml
from flask import Flask, Response, redirect, render_template, request, send_from_directory, url_for

from src.text_analytics import compute_tfidf, cosine_similarity_manual, tokenize

DEV = os.getenv("DEV", False) == "True"


# Add this near the top of your file, with other imports
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}


def find_similar_image_filename(requested_filename, directory="content/assets", threshold=0.9):
  """
    Find an image in the directory with a filename most similar to the requested filename
    using cosine similarity on tokenized filenames (without extensions).
    """
  requested_name, _ = os.path.splitext(requested_filename.lower())
  image_files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)) and os.path.splitext(f.lower())[1] in IMAGE_EXTENSIONS]

  if not image_files:
    return None

  image_names = [os.path.splitext(f.lower())[0] for f in image_files]

  # Compute TF-IDF for image names to get vocabulary
  tfidf_vectors, vocab = compute_tfidf(image_names)
  if not tfidf_vectors:
    return None

  # Compute TF-IDF for requested name using the same vocabulary
  query_vector = compute_tfidf([requested_name], vocab=vocab)[0][0]

  # Compute cosine similarities
  sim_scores = [(image_files[i], cosine_similarity_manual(query_vector, tfidf_vectors[i])) for i in range(len(image_files))]

  # Sort by similarity score (descending)
  sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

  # Return the top match if its similarity is above the threshold
  if sim_scores and sim_scores[0][1] > threshold:
    print(f"Found similar image: {sim_scores[0][0]} for {requested_filename} with similarity {sim_scores[0][1]}")
    return sim_scores[0][0]

  return None


def load_domain_config():
  """Load domain config based on request host. Don’t mess this up, or we’re serving 404s all day."""

  domain = request.host if not DEV else "connectnews24.com"

  config_path = f"domains/{domain}.yml"
  if not os.path.exists(config_path):
    print(f"Config for {domain} not found at {config_path}. Falling back to default.")
    return {
      "site": {"name": "Default Blog", "description": "A blog platform", "keywords": []},
      "content": {"topics": [], "articles_path": f"content/{domain}/articles", "default_image": "/content/assets/tech-bg.jpg"},
      "seo": {"og_image": "/content/assets/tech-bg.jpg", "twitter_image": "/content/assets/tech-bg.jpg"},
    }
  try:
    with open(config_path, "r") as f:
      return yaml.safe_load(f)
  except yaml.YAMLError as e:
    print(f"Invalid YAML in {config_path}: {str(e)}. Default config it is, then.")
    return {
      "site": {"name": "Default Blog", "description": "A blog platform", "keywords": []},
      "content": {"topics": [], "articles_path": f"content/{domain}/articles", "default_image": "/content/assets/tech-bg.jpg"},
      "seo": {"og_image": "/content/assets/tech-bg.jpg", "twitter_image": "/content/assets/tech-bg.jpg"},
    }


def load_articles(domain):
  """Load articles from content/[domain]/articles. No articles? Good luck with that empty blog."""
  articles_path = f"content/{domain}/articles"
  articles = []
  if not os.path.exists(articles_path):
    print(f"No articles directory for {domain} at {articles_path}. You got nothing to show.")
    return []
  for filename in os.listdir(articles_path):
    if filename.endswith(".md"):
      try:
        with open(os.path.join(articles_path, filename), "r") as f:
          post = frontmatter.load(f)
          articles.append(
            {
              "title": post.get("title", "Untitled"),
              "slug": post.get("slug", filename[:-3]),
              "meta_description": post.get("meta_description", ""),
              "meta_keywords": post.get("meta_keywords", []),
              "og_title": post.get("og_title", post.get("title", "Untitled")),
              "og_description": post.get("og_description", post.get("meta_description", "")),
              "og_image": post.get("og_image", ""),
              "author": post.get("author", "Anonymous"),
              "date": post.get("date", ""),
              "body": post.content,
            }
          )
      except Exception as e:
        print(f"Error loading article {filename}: {str(e)}. Skipping that mess.")
  return sorted(articles, key=lambda x: x["date"], reverse=True)


def get_related_articles(articles, current_article):
  """Find related articles using TF-IDF. If this breaks, your search is gonna suck."""
  if not articles:
    return []
  if not current_article:
    return articles[:3]  # Fallback: return 3 recent articles

  documents = [f"{a['title']} {a['meta_description']} {' '.join(a['meta_keywords'])}" for a in articles]
  tfidf_vectors, vocab = compute_tfidf(documents)
  current_text = f"{current_article['title']} {current_article['meta_description']} {' '.join(current_article['meta_keywords'])}"
  current_vector = compute_tfidf([current_text], vocab=vocab)[0][0]

  similarities = [(articles[i], cosine_similarity_manual(current_vector, vector)) for i, vector in enumerate(tfidf_vectors)]
  similarities.sort(key=lambda x: x[1], reverse=True)
  return [article for article, score in similarities[:3] if score > 0.2 and article["slug"] != current_article["slug"]]


def create_app():
  app = Flask(__name__, template_folder="../templates", static_folder="../static")

  DEV = os.getenv("DEV", False) == "True"

  @app.context_processor
  def inject_config():
    """Inject domain config into all templates. Don’t ask me to do this manually."""
    return dict(config=load_domain_config())

  @app.route("/")
  def index():
    """Homepage with featured and recent articles. No articles? Enjoy the silence."""
    domain = request.host if not DEV else "connectnews24.com"
    articles = load_articles(domain)
    latest_article = articles[0] if articles else None
    latest_articles = articles[1:5] if len(articles) > 1 else []
    related_articles = get_related_articles(articles, None)
    return render_template("index.html", latest_article=latest_article, latest_articles=latest_articles, related_articles=related_articles)

  @app.route("/article/<slug>")
  def article(slug):
    """Serve an article by slug. Wrong slug? You’re getting a sneaky 404."""
    domain = request.host if not DEV else "connectnews24.com"
    articles = load_articles(domain)
    article = next((a for a in articles if a["slug"] == slug), None)
    if not article:
      return handle_404(None)
    related_articles = get_related_articles(articles, article)
    return render_template("article.html", article=article, related_articles=related_articles)

  @app.route("/search")
  def search():
    """Search articles with TF-IDF. Don’t expect miracles if your query’s garbage."""
    query = request.args.get("q", "").lower()
    if not query:
      return redirect(url_for("index"))
    domain = request.host if not DEV else "connectnews24.com"
    articles = load_articles(domain)
    results = []
    if articles:
      # Step 1: Compute TF-IDF for documents to get the vocabulary
      documents = [f"{a['title']} {a['meta_description']} {' '.join(a['meta_keywords'])} {a['body']}" for a in articles]
      tfidf_vectors, vocab = compute_tfidf(documents)

      # Step 2: Compute TF-IDF for the query using the same vocabulary
      query_vector = compute_tfidf([query], vocab=vocab)[0][0]  # Pass the vocab explicitly

      # Step 3: Compute cosine similarities
      for i, article in enumerate(articles):
        score = cosine_similarity_manual(query_vector, tfidf_vectors[i])
        if score > 0.1:  # Adjust threshold as needed
          results.append(article)

    results.sort(key=lambda x: x["date"], reverse=True)
    return render_template("index.html", latest_article=None, latest_articles=results, related_articles=articles[:3], search_query=query)

  @app.route("/contact", methods=["GET", "POST"])
  def contact():
    """Contact form. Don’t spam me, or I’ll yeet your email into the void."""
    if request.method == "POST":
      name = request.form.get("name")
      email = request.form.get("email")
      message = request.form.get("message")
      if name and email and message:
        # TODO: Implement email sending (e.g., Amazon SES) or database storage
        print(f"Contact form submission: {name}, {email}, {message}")
        return redirect(url_for("thank_you"))
      print(f"Invalid contact form submission: {name}, {email}, {message}")
    return render_template("contact.html")

  @app.route("/subscribe", methods=["POST"])
  def subscribe():
    """Newsletter signup. Don’t expect a welcome basket."""
    email = request.form.get("email")
    if email:
      # TODO: Implement newsletter storage (e.g., SQLite) or email service
      print(f"Newsletter subscription: {email}")
      return redirect(url_for("thank_you"))
    print("Invalid subscription attempt: No email provided.")
    return redirect(url_for("index"))

  @app.route("/thank_you")
  def thank_you():
    """Thank you page for forms. You’re welcome, I guess."""
    return render_template("thank_you.html")

  @app.route("/guest_poster")
  def guest_poster():
    """Guest poster page. Don’t send me garbage pitches."""
    return render_template("guest_poster.html")

  @app.route("/privacy")
  def privacy():
    """Privacy policy. Yeah, we care about your data... sorta."""
    return render_template("privacy.html")

  @app.route("/sitemap.xml")
  def sitemap():
    """Sitemap for SEO. Google better love this."""
    domain = request.host if not DEV else "connectnews24.com"
    articles = load_articles(domain)
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += f'<url><loc>{url_for("index", _external=True)}</loc></url>\n'
    for article in articles:
      xml += f'<url><loc>{url_for("article", slug=article["slug"], _external=True)}</loc></url>\n'
    xml += "</urlset>"
    return Response(xml, mimetype="application/xml")

  # Replace the existing serve_content_images route
  @app.route("/content/assets/<path:filename>")
  def serve_content_images(filename):
    """Serve images from /content/assets, attempting to find a similar image for missing files before falling back."""
    # Check if the filename has an image extension
    _, ext = os.path.splitext(filename.lower())
    is_image = ext in IMAGE_EXTENSIONS
    content_relative_dir_path = "../content/assets"

    if is_image:
      file_path = os.path.join("content/assets", filename)
      if os.path.exists(file_path) and os.path.isfile(file_path):
        print(f"Serving image: {file_path}")
        return send_from_directory(content_relative_dir_path, filename)
      else:
        print(f"Image not found: {file_path}")
        # Try to find a similar image
        similar_image = find_similar_image_filename(filename)
        if similar_image:
          similar_image_path = os.path.join("content/assets", similar_image)
          if os.path.exists(similar_image_path):
            print(f"Serving similar image: {similar_image}")
            return send_from_directory(content_relative_dir_path, similar_image)

        # Fallback to not-found.jpg
        default_image = "not-found.jpg"
        default_image_path = os.path.join("content/assets", default_image)
        if os.path.exists(default_image_path):
          print(f"Serving fallback image: {default_image}")
          return send_from_directory(content_relative_dir_path, default_image)
        else:
          print(f"Fallback image not found: {default_image_path}")
          # Final fallback to vancouver-bg.jpg
          return send_from_directory(content_relative_dir_path, "vancouver-bg.jpg")
    else:
      # For non-image assets, let the 404 handler deal with it
      return render_template("404.html", related_articles=[]), 404

  # Register custom Markdown filter
  @app.template_filter("markdown")
  def markdown_filter(text):
    return markdown.markdown(text, extensions=["extra", "codehilite", "toc"])

  @app.errorhandler(404)
  def handle_404(e):
    """Sneaky 404 handler that tries to find articles and returns 200. Don’t tell Google."""
    domain = request.host if not DEV else "connectnews24.com"
    articles = load_articles(domain)
    path = request.path.strip("/")
    slug = path.split("/")[-1] if path.startswith("article/") else path

    # Try exact slug match
    for article in articles:
      if slug.lower() in article["slug"].lower() or slug.lower() in article["title"].lower():
        return render_template("article.html", article=article, related_articles=get_related_articles(articles, article)), 200

    # Try TF-IDF similarity
    if articles:
      documents = [f"{a['title']} {a['meta_description']} {' '.join(a['meta_keywords'])}" for a in articles]
      tfidf_vectors, vocab = compute_tfidf(documents)
      slug_vector = compute_tfidf([slug], vocab=vocab)[0][0]
      similarities = [(articles[i], cosine_similarity_manual(slug_vector, vector)) for i, vector in enumerate(tfidf_vectors)]
      similarities.sort(key=lambda x: x[1], reverse=True)

      if similarities and similarities[0][1] > 0.7:  # Threshold for match
        matched_article = similarities[0][0]
        return render_template("article.html", article=matched_article, related_articles=get_related_articles(articles, matched_article)), 200

    # Fallback to 404 page with suggested articles
    return render_template("404.html", related_articles=articles[:3]), 200

  return app
