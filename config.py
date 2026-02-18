import os

# Banco
DATABASE_PATH = "database.db"

# Threshold para comparação facial (distância euclidiana)
FACE_DISTANCE_THRESHOLD = 1.15

# Redimensionamento
MAX_IMAGE_WIDTH = 1600
RESIZE_WIDTH = 1000

# Extensões válidas
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png")

# Threads
MAX_WORKERS = max(1, (os.cpu_count() or 4) - 1)

# Pasta de resultados
RESULTS_DIR = "results"
