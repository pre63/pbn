import math
import re
from collections import Counter, defaultdict

import numpy as np

# Configure logging

# Define stop words list
STOP_WORDS = {
  "a",
  "an",
  "and",
  "are",
  "as",
  "at",
  "be",
  "by",
  "for",
  "from",
  "has",
  "he",
  "in",
  "inc",
  "is",
  "it",
  "its",
  "ltd",
  "of",
  "on",
  "that",
  "the",
  "to",
  "w",
  "e",
  "n",
  "s",
  "was",
  "were",
  "will",
  "with",
  "co",
  "corp",
  "company",
  "llc",
  "or",
  "but",
  "this",
  "these",
  "those",
  "vancouver",
  "bc",
  "s",
  "canada",
  "based",
  "explore",
  "st",
  "which",
  "who",
  "what",
  "when",
  "where",
  "why",
  "how",
  "not",
  "no",
  "ave",
  "street",
  "road",
  "drive",
  "dr",
  "st.",
  "ave.",
  "rd.",
  "blvd",
  "boulevard",
}


def tokenize(text):
  """Convert text to lowercase, split into words, remove punctuation, and filter stop words."""
  if not isinstance(text, str):
    # print(f"Non-string input to tokenize: {type(text)}")
    return []
  text = text.lower()
  words = re.findall(r"\b\w+\b", text)
  # Filter out stop words
  words = [word for word in words if word not in STOP_WORDS]
  return words


def compute_tf(text):
  """Compute term frequency for a document."""
  words = tokenize(text)
  word_counts = Counter(words)
  total_words = len(words)
  if total_words == 0:
    return {}
  return {word: count / total_words for word, count in word_counts.items()}


def compute_idf(documents):
  """Compute inverse document frequency across a list of documents."""
  doc_count = len(documents)
  word_doc_count = defaultdict(int)

  for doc in documents:
    words = set(tokenize(doc))
    for word in words:
      word_doc_count[word] += 1

  idf = {}
  for word, count in word_doc_count.items():
    idf[word] = math.log(doc_count / (1 + count))  # Add 1 to avoid division by zero
  return idf


def compute_tfidf(documents, vocab=None):
  """Compute TF-IDF vectors for a list of documents and report top 50 words by frequency."""
  if not documents:
    # print("Empty document list provided to compute_tfidf")
    return [], []

  # Compute word frequencies across all documents for the report
  all_words = []
  for doc in documents:
    all_words.extend(tokenize(doc))
  word_counts = Counter(all_words)

  # Log top 50 words by frequency
  top_words = word_counts.most_common(50)
  # print("Top 50 words by frequency (after stop words filtering):")
  # print(f"{'Word':<50} {'Count':<10}")
  # print("-" * 30)
  # for word, count in top_words:
  #     print(f"{word:<50} {count:<10}")

  tf_vectors = [compute_tf(doc) for doc in documents]
  idf = compute_idf(documents)

  # Use provided vocab or build a new one
  if vocab is None:
    vocab = sorted(set(word for tf in tf_vectors for word, _ in tf.items()))

  tfidf_vectors = []
  for i, tf in enumerate(tf_vectors):
    vector = np.zeros(len(vocab))
    for word, tf_value in tf.items():
      if word in idf and word in vocab:  # Ensure word is in vocab
        try:
          idx = vocab.index(word)
          vector[idx] = tf_value * idf[word]
        except ValueError:
          # print(f"Word '{word}' not in vocab for document {i}")
          continue
    tfidf_vectors.append(vector)

  # print(f"Computed TF-IDF vectors for {len(documents)} documents with vocabulary size {len(vocab)}")
  return tfidf_vectors, vocab


def cosine_similarity_manual(vec1, vec2):
  """Compute cosine similarity between two vectors."""
  dot_product = np.dot(vec1, vec2)
  norm1 = np.linalg.norm(vec1)
  norm2 = np.linalg.norm(vec2)
  if norm1 == 0 or norm2 == 0:
    return 0.0
  return dot_product / (norm1 * norm2)
