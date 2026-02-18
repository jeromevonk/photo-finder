import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import VALID_EXTENSIONS, MAX_WORKERS
from face_engine import FaceEngine


class PhotoScanner:
    def __init__(self, database):
        self.db = database
        self.engine = FaceEngine()
        self._cancel_requested = False

    def cancel(self):
        """Signal the ongoing scan to stop."""
        self._cancel_requested = True

    @property
    def is_cancelled(self):
        return self._cancel_requested

    def scan(self, root_path, progress_callback=None):
        """Scan root directory detecting new, moved, and removed photos.

        Args:
            root_path: Path to the root directory.
            progress_callback: Function(processed, total, errors, current_file)
                called after each photo is processed.

        Returns:
            dict with statistics: new, moved, removed, errors, cancelled.
        """
        self._cancel_requested = False
        stats = {"new": 0, "moved": 0, "removed": 0, "errors": 0, "cancelled": False, "faces_found": 0, "photos_with_faces": 0}

        # 1. List all photos on disk
        all_files = []
        for root, _, files in os.walk(root_path):
            if self._cancel_requested:
                stats["cancelled"] = True
                return stats
            for file in files:
                if file.lower().endswith(VALID_EXTENSIONS):
                    all_files.append(os.path.join(root, file))

        current_paths = set(all_files)

        # 2. Get already indexed photos
        existing = {path: (size, mtime) for path, size, mtime in self.db.get_all_photos()}
        existing_paths = set(existing.keys())

        # 3. Detect removed and moved photos
        missing_paths = existing_paths - current_paths
        candidate_new = current_paths - existing_paths

        # Build fingerprint index of "removed" photos to detect moved ones
        missing_fingerprints = {}
        for path in missing_paths:
            size, mtime = existing[path]
            key = (size, mtime)
            missing_fingerprints[key] = path

        # Try to match new with removed by fingerprint (size + mtime)
        truly_new = []
        moved_mappings = []  # (old_path, new_path)

        for new_path in candidate_new:
            if self._cancel_requested:
                stats["cancelled"] = True
                return stats
            try:
                size = os.path.getsize(new_path)
                mtime = int(os.path.getmtime(new_path))
                key = (size, mtime)
                if key in missing_fingerprints:
                    old_path = missing_fingerprints.pop(key)
                    moved_mappings.append((old_path, new_path))
                else:
                    truly_new.append(new_path)
            except OSError:
                truly_new.append(new_path)

        # 4. Apply move mappings
        for old_path, new_path in moved_mappings:
            self.db.update_photo_path(old_path, new_path)
            stats["moved"] += 1

        # 5. Remove photos that are truly gone (not moved)
        still_missing = set(missing_fingerprints.values())
        if still_missing:
            self.db.remove_missing_photos(current_paths)
            stats["removed"] = len(still_missing)

        # 6. Process new photos
        total = len(truly_new)
        processed = 0

        def process(path):
            """Process a single photo: extract metadata and embeddings."""
            try:
                size = os.path.getsize(path)
                mtime = int(os.path.getmtime(path))
                photo_id = self.db.add_photo(path, size, mtime)

                embeddings = self.engine.extract_embeddings(path)
                for emb in embeddings:
                    self.db.add_face(photo_id, emb)
                return len(embeddings)  # Number of faces found
            except Exception as e:
                return str(e)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process, path): path for path in truly_new}
            for future in as_completed(futures):
                if self._cancel_requested:
                    executor.shutdown(wait=False, cancel_futures=True)
                    stats["cancelled"] = True
                    return stats

                processed += 1
                result = future.result()
                if isinstance(result, int):
                    if result > 0:
                        stats["faces_found"] += result
                        stats["photos_with_faces"] += 1
                else:
                    stats["errors"] += 1

                if progress_callback:
                    current_file = futures[future]
                    progress_callback(processed, total, stats["errors"], current_file)

        stats["new"] = total - stats["errors"]
        return stats
