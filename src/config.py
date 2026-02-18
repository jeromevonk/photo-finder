import os

# Database (located in project root)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")

# Face comparison threshold (euclidean distance)
FACE_DISTANCE_THRESHOLD = 1.15

# Image resizing
MAX_IMAGE_WIDTH = 1600
RESIZE_WIDTH = 1000

# Valid extensions
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png")

# Threads
MAX_WORKERS = max(1, (os.cpu_count() or 4) - 1)

# Results directory (in project root)
RESULTS_DIR = os.path.join(BASE_DIR, "results")
