from io import BytesIO

from PIL import Image
import imagehash


def compute_phash(image_bytes):
    """Return an ImageHash from raw image bytes."""
    img = Image.open(BytesIO(image_bytes))
    return imagehash.phash(img)


def hamming_distance(hash_a, hash_b):
    """Return integer Hamming distance between two ImageHash objects."""
    return hash_a - hash_b


class PhashCache:
    """In-memory store of previously seen perceptual hashes with video metadata."""

    def __init__(self):
        self._entries = []

    def add(self, phash, video_id, title, url):
        self._entries.append((phash, video_id, title, url))

    def __iter__(self):
        return iter(self._entries)

    def __len__(self):
        return len(self._entries)


def check_duplicate(new_hash, cache, threshold):
    """Compare new_hash against every entry in cache.

    Returns (is_duplicate, matched_phash, hamming_distance,
             matched_video_id, matched_title, matched_url).
    All matched fields are None when is_duplicate is False.
    On a match, only the first entry within threshold is returned.
    """
    for phash, video_id, title, url in cache:
        dist = hamming_distance(new_hash, phash)
        if dist <= threshold:
            return True, phash, dist, video_id, title, url
    return False, None, None, None, None, None
