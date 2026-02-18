import cv2
import numpy as np
from insightface.app import FaceAnalysis
from config import MAX_IMAGE_WIDTH, RESIZE_WIDTH


class FaceEngine:
    def __init__(self):
        self.app = FaceAnalysis(providers=['CPUExecutionProvider'])
        self.app.prepare(ctx_id=0)

    def _resize_if_needed(self, img):
        h, w = img.shape[:2]
        if w > MAX_IMAGE_WIDTH:
            scale = RESIZE_WIDTH / w
            img = cv2.resize(img, (0, 0), fx=scale, fy=scale)
        return img

    def extract_embeddings(self, image_path):
        """Extract face embeddings from an image.

        Returns an empty list if the image cannot be read or if any
        error occurs during detection (corrupted image, invalid format, etc).
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return []

            img = self._resize_if_needed(img)
            faces = self.app.get(img)

            embeddings = []
            for face in faces:
                emb = face.embedding.astype(np.float32)
                # Normalize to unit vector (essential for ArcFace)
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                embeddings.append(emb)

            return embeddings
        except Exception:
            # Corrupted image, invalid format, etc.
            return []

    def compare(self, query_embedding, database_embeddings):
        """Compare one embedding against a matrix of embeddings.

        Normalizes both sides before computing the Euclidean distance,
        ensuring values in the range [0, 2].
        """
        if len(database_embeddings) == 0:
            return np.array([])

        # Normalize query
        q_norm = np.linalg.norm(query_embedding)
        if q_norm > 0:
            query_embedding = query_embedding / q_norm

        # Normalize each database embedding
        norms = np.linalg.norm(database_embeddings, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)  # avoid division by zero
        database_embeddings = database_embeddings / norms

        distances = np.linalg.norm(database_embeddings - query_embedding, axis=1)
        return distances
