# Mapping Texts: Computational Text Analysis for the Social Sciences

## Book Overview

*Mapping Texts: Computational Text Analysis for the Social Sciences* by Dustin S. Stoltz and Marshall A. Taylor (Oxford University Press, 2024) provides a comprehensive introduction to computational text analysis methods tailored for social science research. Unlike traditional "text mining" approaches that emphasize extraction of hidden patterns, this book adopts a "mapping" metaphor—reducing text to representations that aid human interpretation rather than automating discovery away from researchers.

The book assumes no prior programming experience and integrates computational techniques with social scientific text analysis methodology. All examples use R, but this summary translates them to Python.

---

## Part I: Orientation

### The Mapping Metaphor

The central philosophical contribution of this book is the distinction between "mining" and "mapping" texts:

- **Mining metaphor**: Treats text as a repository of hidden patterns waiting to be extracted. The goal is discovery—finding something buried in the data.

- **Mapping metaphor**: Treats text as a landscape to be represented in ways that aid interpretation. The goal is reduction to facilitate human understanding.

This distinction shapes every methodological choice in the book. The authors argue that computational text analysis for social sciences should prioritize methods that maintain interpretive 联系 between researcher and text, even as we reduce text to numbers and visualizations.

### Four Propositions About Language

Theoretical grounding comes from four propositions about language:

1. **Pragmatic, not semantic**: Language is action, not description. Meaning is in use, not in words themselves.

2. **Not meaning, intentionality**: Language expresses intentions, not simply meanings. Speakers encode meaning into text; readers decode it.

3. **Habitual, not compositional**: Language use is largely habitual, following social patterns of who says what to whom.

4. **Relational, not categorical**: Words get meaning from their relationships to other words, not from categorical definitions.

5. **Unfinished, not complete**: Language is always incomplete and context-dependent; it requires interpretation.

6. **Field effects**: Language use varies by social position (field), not just individual preference.

### Five Propositions About Text

1. **Characters, not words**: Texts are strings of characters, not word containers. The unit of analysis matters.

2. **Re-presents, doesn't capture**: A text is a representation of something (speech event), not a capture of underlying reality.

3. **Language, not data**: Computational text analysis works with language, not information. It's fundamentally different from database queries.

4. **Durable and decay**: Texts persist but also degrade. They have material properties that change.

5. **Objects, not transparent windows**: Texts are objects to be studied, not transparent windows to social reality.

These propositions shape the methodological approach throughout the book.

---

## Part II: Prerequisites

*(Basic Python programming concepts, data structures, and math foundations—omitted for brevity)*

---

## Part III: Foundations

### Chapter 5: Acquiring Text

Getting text into your computer involves three primary approaches: APIs, Optical Character Recognition (OCR), and web scraping.

#### APIs

**What**: Application Programming Interfaces allow programmatic access to platform data.

**Why**: APIs provide structured, machine-readable access to texts stored on platforms (social media, news archives, etc.). Manual collection is impractical at scale.

**When**: Use when working with Twitter/X, Reddit, news outlets, or any platform with API access.

```python
import requests

def get_tweets(query, bearer_token, max_results=100):
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    params = {"query": query, "max_results": max_results}
    response = requests.get(url, headers=headers, params=params)
    return response.json()
```

Key considerations:
- Rate limits exist on all major APIs
- API terms of service matter for research ethics
- Developer accounts may be required

#### OCR

**What**: Optical Character Recognition converts images to text.

**Why**: Many historical documents exist only as images (scanned PDFs, photos, faxes). OCR makes them machine-readable.

**When**: Use with scanned documents, historical archives, or any image-based text.

```python
import pytesseract
from PIL import Image

def ocr_image(image_path):
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image)
    return text

from pdf2image import convert_from_path

def ocr_pdf(pdf_path):
    images = convert_from_path(pdf_path)
    text = ""
    for image in images:
        text += pytesseract.image_to_string(image)
    return text
```

Alternative tools: Amazon Textract, Google Cloud Vision, Azure Form Recognizer for professional-grade extraction.

#### Web Scraping

**What**: Extracting text directly from websites.

**Why**: Not all text is available via APIs. Scraping lets you collect text from any public webpage.

**When**: Use when APIs aren't available or when you need content not exposed via API.

```python
import requests
from bs4 import BeautifulSoup

def scrape_page(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    paragraphs = soup.find_all('p')
    text = ' '.join(p.get_text() for p in paragraphs)
    return text
```

Key considerations:
- robots.txt specifies what can be scraped
- Rate limiting respects server resources
- Some sites require JavaScript rendering (use Selenium or Playwright)

---

### Chapter 6: Converting Text to Numbers

The fundamental challenge: turning language into numbers computers can process.

#### Tokenization

**What**: Breaking text into discrete units (tokens), usually words.

**Why**: Computers process numbers, not raw text. Tokenization is the first step in converting text to a numerical representation. We can't count "words" if we haven't defined what a "word" is.

**When**: Always—the first step in any text analysis pipeline.

```python
import re

def tokenize(text):
    # Split on non-word characters
    tokens = re.findall(r'\b\w+\b', text.lower())
    return tokens

import nltk
from nltk.tokenize import word_tokenize

tokens = word_tokenize("The cat sat on the mat.")

import spacy
nlp = spacy.load("en_core_web_sm")
doc = nlp("The cat sat on the mat.")
tokens = [token.text for token in doc]
```

**Key decision**: Character n-grams (subword units) vs. word-level tokens vs. sentence-level. Each captures different patterns.

#### Document-Term Matrix (DTM)

**What**: A matrix where rows represent documents and columns represent terms, with cell values being term counts.

**Why**: Transforms a corpus into a format suitable for statistical analysis. This is the fundamental data structure for computational text analysis—documents as rows, words as columns.

**When**: Use for any method that operates on word frequencies (topic models, clustering, classification).

```python
from sklearn.feature_extraction.text import CountVectorizer

corpus = [ 
    "The cat sat on the mat.",
    "The dog played in the garden.",
    "Cats and dogs are popular pets."
]

vectorizer = CountVectorizer()
dtm = vectorizer.fit_transform(corpus)

dtm_dense = dtm.toarray()
feature_names = vectorizer.get_feature_names_out()
import pandas as pd
pd.DataFrame(dtm_dense, columns=feature_names)
```

The resulting matrix shows how often each word appears in each document.

#### TF-IDF

**What**: Term Frequency-Inverse Document Frequency—a weighting scheme that emphasizes distinctive terms.

**Why**: Raw counts favor common words. TF-IDF upweights terms that are frequent in a document but rare across the corpus—these are often more meaningful. Common words like "the" get downweighted.

**When**: Use when you want to find distinctive vocabulary or as input for similarity search.

```python
from sklearn.feature_extraction.text import TfidfVectorizer

tfidf_vectorizer = TfidfVectorizer()
tfidf_matrix = tfidf_vectorizer.fit_transform(corpus)
```

The intuition: Words that appear in every document don't help distinguish them. Words that appear in only one document do.

#### Word Embeddings

**What**: Dense vectors (typically 100-300 dimensions) representing word meaning.

**Why**: One-hot vectors (sparse, high-dimensional) treat all words as equally different. Embeddings capture semantic similarity—similar words have similar vectors. This addresses the "relational, not categorical" proposition.

**When**: Use for semantic similarity, analogy operations, or as features for downstream tasks.

```python
from gensim.models import Word2Vec

sentences = [
    ["the", "cat", "sat", "on", "the", "mat"],
    ["the", "dog", "played", "in", "the", "garden"],
    ["cats", "and", "dogs", "are", "popular", "pets"]
]

model = Word2Vec(sentences, vector_size=100, window=5, min_count=1)

vector = model.wv["cat"]
similar = model.wv.most_similar("cat")
```

Pre-trained embeddings capture knowledge from massive corpora:

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(["The cat sat on the mat", "A feline rested on a rug"])
```

---

## Part IV: Below the Document Level

### Chapter 7: Wrangling

Cleaning and normalizing text before analysis.

#### Basic Cleaning

**What**: Removing noise—URLs, mentions, special characters, extra whitespace.

**Why**: Raw text contains artifacts irrelevant to meaning. URLs and @mentions are formatting, not content. Extra whitespace causes counting errors.

**When**: Always, before analysis.

```python
import re

def clean_text(text):
    text = text.lower()
    text = re.sub(r'http\S+|www\S+', '', text)  # URLs
    text = re.sub(r'@\w+', '', text)  # Mentions
    text = re.sub(r'[^\w\s]', ' ', text)  # Special chars
    text = re.sub(r'\s+', ' ', text).strip()
    return text
```

#### Normalization

**What**: Reducing words to base forms—stemming or lemmatization.

**Why**: Language has morphological variation. "running," "runs," "ran" are all forms of "run." Without normalization, the computer treats them as different words. Lemmatization ("run" ← "running") is more accurate than stemming (truncation).

**When**: Use before building DTM or when counting word frequencies.

```python
from nltk.stem import PorterStemmer, WordNetLemmatizer
import spacy

nlp = spacy.load("en_core_web_sm")

# Stemming (crude but fast)
stemmer = PorterStemmer()
stemmed = stemmer.stem("running")

# Lemmatization (dictionary-based, accurate)
def lemmatize(text):
    doc = nlp(text)
    return " ".join([token.lemma_ for token in doc])

def normalize_text(text):
    doc = nlp(text)
    lemmas = []
    for token in doc:
        if token.is_stop or token.is_punct:
            continue
        lemmas.append(token.lemma_)
    return " ".join(lemmas)
```

#### Stopword Removal

**What**: Filtering common words (the, a, is, of, and).

**Why**: These words appear everywhere but carry little meaning. Including them creates noise and increases computational cost without adding signal.

**When**: Use when frequency-based methods dominate, but reconsider for semantic methods (embeddings already handle this).

```python
import nltk
from nltk.corpus import stopwords

stop_words = set(stopwords.words('english'))

def remove_stopwords(tokens):
    return [t for t in tokens if t not in stop_words]

def remove_stopwords_spacy(text):
    doc = nlp(text)
    return [token.text for token in doc if not token.is_stop]
```

---

### Chapter 8: Tagging Words

Adding linguistic annotations to tokens.

#### Part-of-Speech (POS) Tagging

**What**: Labeling each word with its grammatical category (noun, verb, adjective, etc.).

**Why**: Grammar relates to function in discourse. Verbs indicate action; adjectives indicate attributes. POS lets us filter by grammatical role—e.g., analyze only nouns.

**When**: Use when you want to analyze specific word classes or need grammatical information.

```python
import spacy
nlp = spacy.load("en_core_web_sm")

def pos_tag(text):
    doc = nlp(text)
    return [(token.text, token.pos_, token.tag_) for token in doc]

# [("The", "DET", "DT"), ("cat", "NOUN", "NN"), ...]
```

#### Named Entity Recognition (NER)

**What**: Identifying and categorizing real-world entities (people, organizations, locations).

**Why**: Entities are often the focus of social science questions—who is being discussed? Where? NER extracts this automatically.

**When**: Use when analyzing mentions of specific actors or places.

```python
def extract_entities(text):
    doc = nlp(text)
    return [(ent.text, ent.label_) for ent in doc.ents]

text = "Joe Biden visited Paris and Microsoft yesterday."
extract_entities(text)
# [("Joe Biden", "PERSON"), ("Paris", "GPE"), ("Microsoft", "ORG")]
```

#### Dependency Parsing

**What**: Analyzing grammatical relationships between words (subject → verb → object).

**Why**: Grammar encodes argument structure—who did what to whom. Dependency parsing reveals syntactic relationships.

**When**: Use for complex grammatical analysis or when extracting structured relations.

```python
def dependency_parse(text):
    doc = nlp(text)
    return [(token.text, token.dep_, token.head.text) for token in doc]
```

#### Dictionary Methods

**What**: Using predefined word lists to classify or tag texts.

**Why**: Sometimes we know what we're looking for. Dictionary methods apply human-developed categories systematically—this is deductive coding at scale.

**When**: Use when you have theoretical categories (e.g., sentiment, topics) defined in advance.

```python
def tag_with_dict(tokens, dictionary):
    tags = []
    for token in tokens:
        matched = False
        for category, words in dictionary.items():
            if token in words:
                tags.append(category)
                matched = True
                break
        if not matched:
            tags.append("OTHER")
    return tags

sentiment_dict = {
    "positive": ["good", "great", "excellent", "happy", "love"],
    "negative": ["bad", "terrible", "poor", "sad", "hate"]
}
```

For sophisticated dictionary methods, see LIWC (Linguistic Inquiry and Word Count).

---

## Part V: Document Level and Beyond

### Core Deductive Methods

#### Dictionary/Coding

**What**: Using predefined categories to classify entire documents.

**Why**: When theory specifies categories in advance, apply them systematically. This is human coding at scale.

**When**: Use when categories are well-defined theoretically (e.g., issue positions, frames).

```python
from sklearn.feature_extraction.text import TfidfVectorizer
import pandas as pd

categories = {
    "economic": ["market", "economy", "money", "financial", "trade", "GDP"],
    "political": ["government", "policy", "vote", "political", "congress", "law"],
    "social": ["community", "society", "people", "family", "social", "culture"]
}

def code_document(text, categories):
    text_lower = text.lower()
    scores = {}
    for category, words in categories.items():
        count = sum(text_lower.count(word) for word in words)
        scores[category] = count
    return scores

def code_corpus(corpus, categories):
    return pd.DataFrame([code_document(doc, categories) for doc in corpus])
```

#### Word Scores

**What**: Scoring documents on continuous dimensions (not just categories).

**Why**: Some concepts are continuous, not categorical. Sentiment isn't "positive" vs. "negative"—it's a scale.

**When**: Use for continuous concepts like sentiment, complexity, or intensity.

```python
def sentiment_score(text, positive_words, negative_words):
    text_lower = text.lower()
    pos_count = sum(text_lower.count(w) for w in positive_words)
    neg_count = sum(text_lower.count(w) for w in negative_words)
    return pos_count - neg_count

def normalized_sentiment(text, positive_words, negative_words):
    text_lower = text.lower()
    words = text_lower.split()
    if len(words) == 0:
        return 0
    pos_count = sum(words.count(w) for w in positive_words)
    neg_count = sum(words.count(w) for w in negative_words)
    return (pos_count - neg_count) / len(words)
```

---

### Core Inductive Methods

#### Topic Modeling (LDA)

**What**: Discover latent topics in a corpus without predefined categories.

**Why**: Sometimes we don't know what we're looking for. Topic modeling discovers word co-occurrence patterns and groups them into "topics."

**When**: Use for exploratory analysis or when categories are unknown.

```python
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer

vectorizer = CountVectorizer(max_df=0.95, min_df=2)
dtm = vectorizer.fit_transform(corpus)

n_topics = 5
lda = LatentDirichletAllocation(n_components=n_topics, random_state=42)
lda.fit(dtm)

feature_names = vectorizer.get_feature_names_out()

def print_topics(model, feature_names, n_top_words=10):
    for topic_idx, topic in enumerate(model.components_):
        top_words = [feature_names[i] for i in topic.argsort()[:-n_top_words - 1:-1]]
        print(f"Topic {topic_idx}: {', '.join(top_words)}")

print_topics(lda, feature_names)

doc_topics = lda.transform(dtm)
```

Alternative: BERTopic for neural topic modeling.

#### Cluster Analysis

**What**: Grouping similar documents without predefined categories.

**Why**: Documents cluster by similarity. If we don't know what topics exist, we can discover them through clustering.

**When**: Use when you want to find groups of similar documents.

```python
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score

vectorizer = TfidfVectorizer(max_df=0.95, min_df=2)
tfidf = vectorizer.fit_transform(corpus)

silhouette_scores = []
K_range = range(2, 10)
for k in K_range:
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(tfidf)
    score = silhouette_score(tfidf, labels)
    silhouette_scores.append(score)

optimal_k = K_range[silhouette_scores.index(max(silhouette_scores))]
print(f"Optimal number of clusters: {optimal_k}")
```

---

### Extended Deductive Methods

#### Sentiment Analysis

**What**: Automatically detecting positive/negative tone.

**Why**: Sentiment is a well-theorized concept with established dictionaries and methods.

**When**: Use for analyzing opinion, public response, or emotional tone.

```python
from textblob import TextBlob

def sentiment(text):
    blob = TextBlob(text)
    return blob.sentiment.polarity, blob.sentiment.subjectivity

from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
nltk.download('vader_lexicon')

sia = SentimentIntensityAnalyzer()

def vader_sentiment(text):
    scores = sia.polarity_scores(text)
    return scores['compound']
```

VADER is specifically tuned for social media text.

#### Discourse Analysis

**What**: Analyzing text for argumentative structure (cause-effect, contrast, addition).

**Why**: Discourse markers reveal logical structure—how arguments are connected, not just what is said.

**When**: Use for analyzing argument quality or rhetorical strategy.

```python
discourse_markers = {
    "causation": ["because", "therefore", "thus", "hence", "caused"],
    "contrast": ["but", "however", "although", "yet", "nevertheless"],
    "addition": ["and", "also", "moreover", "furthermore", "additionally"]
}

def discourse_analysis(text):
    text_lower = text.lower()
    counts = {}
    for category, markers in discourse_markers.items():
        counts[category] = sum(text_lower.count(m) for m in markers)
    return counts
```

---

### Extended Inductive Methods

#### Word Embeddings for Analysis

**What**: Using trained embeddings to analyze semantic relationships.

**Why**: Beyond similarity—embeddings capture complex relationships. Analogy operations (king - man + woman = queen) reveal structured knowledge.

**When**: Use for semantic analysis, analogy detection, or finding related terms.

```python
from gensim.models import Word2Vec

model = Word2Vec(sentences, vector_size=100, window=5, min_count=5, workers=4)

# model.wv.most_similar(positive=['king', 'woman'], negative=['man'])
# model.wv.similarity('cat', 'dog')
# model.wv.doesnt_match(['cat', 'dog', 'chair'])
```

#### Document Embeddings

**What**: Dense vectors representing entire documents.

**Why**: Bag-of-words loses word order and context. Document embeddings capture semantic content.

**When**: Use for document similarity, clustering, or as features.

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
doc_embeddings = model.encode(corpus)

from sklearn.manifold import TSNE

tsne = TSNE(n_components=2, random_state=42)
embeddings_2d = tsne.fit_transform(doc_embeddings)
```

#### Text Networks

**What**: Constructing networks from word co-occurrence.

**Why**: Words that appear together relate semantically. Network analysis reveals structure in vocabulary relationships.

**When**: Use for analyzing lexical structure or finding central terms.

```python
import networkx as nx
from collections import defaultdict

def build_cooccurrence_network(documents, window_size=5):
    G = nx.Graph()
    edge_weights = defaultdict(int)
    
    for doc in documents:
        words = doc.split()
        for i in range(len(words)):
            for j in range(i+1, min(i+window_size, len(words))):
                if words[i] != words[j]:
                    edge = tuple(sorted([words[i], words[j]]))
                    edge_weights[edge] += 1
    
    for (w1, w2), weight in edge_weights.items():
        if weight > 1:
            G.add_edge(w1, w2, weight=weight)
    
    return G

G = build_cooccurrence_network(corpus)

# nx.degree_centrality(G)
# nx.betweenness_centrality(G)
```

---

## Part VI: Project Workflow

### Research Design

1. **Define the question**: What textual evidence addresses your research question?
2. **Corpus selection**: Which texts contain relevant language?
3. **Operationalization**: How do you measure your theoretical concepts in text?
4. **Method selection**: Deductive (coding with categories) vs. inductive (discovery)

### Iteration

Computational text analysis is iterative:

1. Run initial analysis
2. Examine results
3. Refine approach
4. Repeat

```python
from sklearn.feature_extraction.text import TfidfVectorizer

def iterative_analysis(corpus, n_terms=50):
    vectorizer = TfidfVectorizer(max_features=n_terms, stop_words='english')
    tfidf = vectorizer.fit_transform(corpus)
    
    feature_names = vectorizer.get_feature_names_out()
    for i, doc in enumerate(tfidf.toarray()):
        top_indices = doc.argsort()[-5:][::-1]
        top_terms = [feature_names[j] for j in top_indices]
        print(f"Doc {i}: {top_terms}")
    
    return feature_names

top_terms = iterative_analysis(corpus)
```

---

## Key Takeaways

1. **Mapping over mining**: Choose methods that maintain interpretive 联系 between researcher and text.

2. **Theoretical groundedness**: Let social science theory guide your operationalization.

3. **Unit of analysis matters**: Characters, words, sentences, or documents��choose based on your question.

4. **Validation**: Compare computational results to human coding when possible.

5. **Iteration**: Treat analysis as an iterative process, not a single pass.

---

## Common Python Packages

| Task | Package |
|------|---------|
| Tokenization | NLTK, spaCy, textblob |
| Vectorization | sklearn, gensim |
| Topic Modeling | sklearn, BERTopic, tmtoolkit |
| Embeddings | gensim, sentence-transformers |
| Sentiment | textblob, vaderSentiment, transformers |
| Networks | networkx, graph-tool |
| Scraping | requests, beautifulsoup4, selenium |

---

## References

- Stoltz, D. S., & Taylor, M. A. (2024). *Mapping Texts: Computational Text Analysis for the Social Sciences*. Oxford University Press.
- Stoltz, D. S. (2020). Text As Data: A Short Introduction. *Sociological Methods & Research*.
- Grimmer, J., & Stewart, B. M. (2013). Text as Data: The Promise and Pitfalls of Automatic Content Analysis Methods for Political Texts. *Political Analysis*.