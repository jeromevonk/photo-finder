import os

# Database
DATABASE_PATH = "database.db"

# Face comparison threshold (euclidean distance)
FACE_DISTANCE_THRESHOLD = 1.15

# Image resizing
MAX_IMAGE_WIDTH = 1600
RESIZE_WIDTH = 1000

# Valid extensions
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png")

# Threads
MAX_WORKERS = max(1, (os.cpu_count() or 4) - 1)

# Results directory
RESULTS_DIR = "results"
