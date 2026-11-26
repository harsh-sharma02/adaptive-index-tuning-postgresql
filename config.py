
from pathlib import Path


# ==================================================
# PROJECT DIRECTORIES
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parent

DATABASE_DIR = PROJECT_ROOT / "database"

WORKLOAD_DIR = PROJECT_ROOT / "workload"

RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"


# ==================================================
# POSTGRESQL CONFIGURATION
# ==================================================

DB_HOST = "localhost"

DB_PORT = 5432

DB_NAME = "index_tuning"

DB_USER = "postgres"

DB_PASSWORD = "password"


# ==================================================
# INDEX OPTIMIZATION CONSTRAINTS
# ==================================================

# Maximum available index storage in MB
STORAGE_BUDGET_MB = 500

# Maximum number of columns in a composite index
MAX_INDEX_COLUMNS = 3


# ==================================================
# WORKLOAD CONFIGURATION
# ==================================================

INITIAL_WORKLOAD = WORKLOAD_DIR / "workload_1.sql"

NEW_WORKLOAD = WORKLOAD_DIR / "workload_2.sql"


# ==================================================
# CANDIDATE GENERATION CONFIGURATION
# ==================================================

# Maximum number of candidate indexes to evaluate
MAX_CANDIDATES = 100

# Minimum query frequency for considering a pattern
MIN_QUERY_FREQUENCY = 1


# ==================================================
# OPTIMIZATION CONFIGURATION
# ==================================================

# Solver time limit in seconds.
# The solver will report whether optimality was proven.
SOLVER_TIME_LIMIT = 300

# Cost weights (to be calibrated during experiments)
READ_COST_WEIGHT = 1.0

WRITE_COST_WEIGHT = 1.0

STORAGE_COST_WEIGHT = 1.0

RECONFIGURATION_COST_WEIGHT = 1.0
