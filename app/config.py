import os
from dotenv import load_dotenv


def load_config():
    load_dotenv()
    return {
        "YT_API_KEY": os.getenv("YT_API_KEY", ""),
        "KEYWORD": os.getenv("KEYWORD", "test keyword"),
        "INTERVAL_MIN": int(os.getenv("INTERVAL_MIN", "5")),
        "PHASH_THRESHOLD": int(os.getenv("PHASH_THRESHOLD", "5")),
    }
