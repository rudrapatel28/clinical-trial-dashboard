import csv
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "cell_trial.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "cell-count.csv")

# Fall back to Downloads if CSV is not next to this script
if not os.path.exists(CSV_PATH):
    CSV_PATH = os.path.join(os.path.expanduser("~"), "Downloads", "cell-count.csv")


DDL = """
CREATE TABLE IF NOT EXISTS subjects (
    subject_id  TEXT    PRIMARY KEY,
    project     TEXT    NOT NULL,
    condition   TEXT    NOT NULL,
    age         INTEGER,
    sex         TEXT,
    treatment   TEXT,
    response    TEXT
);

CREATE TABLE IF NOT EXISTS samples (
    sample_id                   TEXT    PRIMARY KEY,
    subject_id                  TEXT    NOT NULL,
    sample_type                 TEXT    NOT NULL,
    time_from_treatment_start   INTEGER NOT NULL,
    FOREIGN KEY (subject_id) REFERENCES subjects (subject_id)
);

CREATE TABLE IF NOT EXISTS cell_counts (
    sample_id   TEXT    PRIMARY KEY,
    b_cell      INTEGER NOT NULL,
    cd8_t_cell  INTEGER NOT NULL,
    cd4_t_cell  INTEGER NOT NULL,
    nk_cell     INTEGER NOT NULL,
    monocyte    INTEGER NOT NULL,
    FOREIGN KEY (sample_id) REFERENCES samples (sample_id)
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    conn.commit()


def load_csv(conn: sqlite3.Connection, csv_path: str) -> int:
    subjects_seen: set[str] = set()
    rows_loaded = 0

    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            subject_id = row["subject"]

            # Insert subject once
            if subject_id not in subjects_seen:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO subjects
                        (subject_id, project, condition, age, sex, treatment, response)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        subject_id,
                        row["project"],
                        row["condition"],
                        int(row["age"]) if row["age"] else None,
                        row["sex"] or None,
                        row["treatment"] or None,
                        row["response"] or None,
                    ),
                )
                subjects_seen.add(subject_id)

            # Insert sample
            conn.execute(
                """
                INSERT OR IGNORE INTO samples
                    (sample_id, subject_id, sample_type, time_from_treatment_start)
                VALUES (?, ?, ?, ?)
                """,
                (
                    row["sample"],
                    subject_id,
                    row["sample_type"],
                    int(row["time_from_treatment_start"]),
                ),
            )

            # Insert cell counts
            conn.execute(
                """
                INSERT OR IGNORE INTO cell_counts
                    (sample_id, b_cell, cd8_t_cell, cd4_t_cell, nk_cell, monocyte)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["sample"],
                    int(row["b_cell"]),
                    int(row["cd8_t_cell"]),
                    int(row["cd4_t_cell"]),
                    int(row["nk_cell"]),
                    int(row["monocyte"]),
                ),
            )
            rows_loaded += 1

    conn.commit()
    return rows_loaded


def main() -> None:
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print(f"Removed existing database: {DB_PATH}")
        except PermissionError:
            print(f"Warning: Could not delete {DB_PATH} — it may be in use. Continuing anyway...")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    print("Initializing schema...")
    init_db(conn)

    print(f"Loading data from: {CSV_PATH}")
    n = load_csv(conn, CSV_PATH)

    # Verification counts
    n_subjects = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    n_samples  = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
    n_counts   = conn.execute("SELECT COUNT(*) FROM cell_counts").fetchone()[0]

    conn.close()

    print(f"\nDatabase created: {DB_PATH}")
    print(f"  CSV rows loaded : {n:,}")
    print(f"  Subjects        : {n_subjects:,}")
    print(f"  Samples         : {n_samples:,}")
    print(f"  Cell-count rows : {n_counts:,}")


if __name__ == "__main__":
    main()