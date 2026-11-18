"""Turn a sentence such as '2 ACs 8 hours, 4 fans, fridge' into appliances.

Steps: split into parts -> pull out quantity and hours -> clean the name with
our own code -> TF-IDF + cosine similarity against the appliance table.
"""
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

# Words that carry no meaning for matching. A set is right: we only ask "is it in there?"
STOP_WORDS = {"a", "an", "the", "of", "for", "my", "i", "have", "with",
              "about", "around", "approx", "x", "is", "are", "in", "at"}

# Different ways people write the same thing -> one standard form.
VARIANTS = [
    (r"\ba[/.]c\b", "ac"),
    (r"\bair[\s-]*condition(?:er|ing|ed)?s?\b", "ac"),
    (r"\bhorse\s*power\b", "hp"),
]

# Short words that end in "s" but whose "s" must be removed to make them singular.
SHORT_PLURALS = {"acs", "tvs", "pcs"}

HOURS_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b")
QUANTITY_PATTERN = re.compile(r"(?<![\d.])(\d+)(?!\.?\d)(?!\s*(?:ton|hp))")
WORD_QUANTITY_PATTERN = re.compile(
    r"\b(" + "|".join(NUMBER_WORDS) + r")\b(?!\s*ton)")


def singular(token):
    """Return a simple singular form: 'fans' -> 'fan', 'acs' -> 'ac'."""
    if token in SHORT_PLURALS:
        return token[:-1]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def clean_text(text, remove_stop_words=True):
    """Lowercase, standardise spellings, drop punctuation, make words singular.

    Dots are kept only inside numbers so '1.5 ton' stays one number.
    """
    text = text.lower()
    for pattern, replacement in VARIANTS:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"[^a-z0-9.\s]", " ", text)
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    tokens = [singular(token) for token in text.split()]
    if remove_stop_words:
        tokens = [token for token in tokens if token not in STOP_WORDS]
    return " ".join(tokens)


def split_parts(text):
    """Split a sentence into one part per appliance."""
    pieces = re.split(r"[,;\n+&]|\band\b", text.lower())
    return list(filter(None, map(str.strip, pieces)))


def extract_hours(part):
    """Return (hours or None, the text with the hours removed)."""
    match = HOURS_PATTERN.search(part)
    if match is None:
        return None, part
    return float(match.group(1)), part[:match.start()] + " " + part[match.end():]


def extract_quantity(part):
    """Return (quantity or None, the text with the quantity removed).

    A number followed by 'ton' or 'hp' belongs to the appliance, not the count.
    """
    match = QUANTITY_PATTERN.search(part)
    if match is not None:
        quantity = int(match.group(1))
    else:
        match = WORD_QUANTITY_PATTERN.search(part)
        if match is None:
            return None, part
        quantity = NUMBER_WORDS[match.group(1)]
    return quantity, part[:match.start()] + " " + part[match.end():]


class ApplianceMatcher:
    """Matches a cleaned phrase to the closest appliance in the table.

    Each appliance becomes one small 'document' (its name plus its aliases).
    TF-IDF turns documents and phrases into number vectors, and cosine
    similarity says which document is closest to the phrase. If the phrase is
    exactly a known name or alias, that appliance wins straight away (this is
    how a plain 'fan' means the ceiling fan); TF-IDF handles everything else.
    """

    def __init__(self, table, min_score=0.2):
        self._rows = list(table.values())
        documents = [clean_text(" ".join([row["name"]] + row["aliases"]))
                     for row in self._rows]
        self._exact = {}
        for row in self._rows:
            for label in [row["name"]] + row["aliases"]:
                self._exact.setdefault(clean_text(label), row)  # first row wins
        self._vectorizer = TfidfVectorizer(token_pattern=r"[a-z0-9.]+",
                                           ngram_range=(1, 2))
        self._matrix = self._vectorizer.fit_transform(documents)
        self.min_score = min_score

    def best_match(self, phrase):
        """Return (table row or None, similarity score)."""
        if not phrase:
            return None, 0.0
        if phrase in self._exact:
            return self._exact[phrase], 1.0
        scores = cosine_similarity(self._vectorizer.transform([phrase]),
                                   self._matrix)[0]
        best = max(range(len(scores)), key=lambda i: scores[i])
        if scores[best] < self.min_score:
            return None, float(scores[best])
        return self._rows[best], float(scores[best])


def parse_appliance_text(text, matcher):
    """Parse a sentence and return one dict per appliance mentioned.

    Each dict has: original, phrase, row (None if not recognised), score,
    quantity (default 1) and hours (None means 'use the typical hours').
    """
    results = []
    for part in split_parts(text):
        hours, rest = extract_hours(part)
        quantity, rest = extract_quantity(rest)
        phrase = clean_text(rest)
        row, score = matcher.best_match(phrase)
        results.append({"original": part, "phrase": phrase, "row": row,
                        "score": score, "quantity": quantity or 1,
                        "hours": hours})
    return results
