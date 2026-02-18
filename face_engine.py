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
        """Extrai embeddings faciais de uma imagem.

        Retorna lista vazia se a imagem não puder ser lida ou se ocorrer
        qualquer erro durante a detecção (imagem corrompida, formato
        inválido, etc).
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
                # Normalizar para vetor unitário (essencial para ArcFace)
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                embeddings.append(emb)

            return embeddings
        except Exception:
            # Imagem corrompida, formato inválido, etc.
            return []

    def compare(self, query_embedding, database_embeddings):
        """Compara um embedding contra uma matriz de embeddings.

        Normaliza ambos os lados antes de calcular a distância
        euclidiana, garantindo valores no intervalo [0, 2].
        """
        if len(database_embeddings) == 0:
            return np.array([])

        # Normalizar query
        q_norm = np.linalg.norm(query_embedding)
        if q_norm > 0:
            query_embedding = query_embedding / q_norm

        # Normalizar cada embedding do banco
        norms = np.linalg.norm(database_embeddings, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)  # evitar divisão por zero
        database_embeddings = database_embeddings / norms

        distances = np.linalg.norm(database_embeddings - query_embedding, axis=1)
        return distances
