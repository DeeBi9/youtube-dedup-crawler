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
    """In-memory store of previously seen perceptual hashes."""

    def __init__(self):
        self._hashes = []

    def add(self, phash):
        self._hashes.append(phash)

    def __iter__(self):
        return iter(self._hashes)

    def __len__(self):
        return len(self._hashes)


def check_duplicate(new_hash, cache, threshold):
    """Compare new_hash against every hash in cache.

    Returns (is_duplicate, matched_hash, hamming_distance).
    matched_hash and distance are None when is_duplicate is False.
    On a match, only the first hash within threshold is returned.
    """
    for stored_hash in cache:
        dist = hamming_distance(new_hash, stored_hash)
        if dist <= threshold:
            return True, stored_hash, dist
    return False, None, None
