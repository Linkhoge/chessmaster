import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(BASE, "hf_token.txt")

def load_hf_token():
    """Read an optional Hugging Face token from hf_token.txt and export it as HF_TOKEN.

    An HF_TOKEN already set in the environment wins. Lines starting with # are ignored.
    Returns True if a token is active.
    """
    if os.environ.get("HF_TOKEN"):
        return True
    try:
        with open(TOKEN_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    os.environ["HF_TOKEN"] = line
                    return True
    except OSError:
        pass
    return False
