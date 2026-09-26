import sqlite3
from pathlib import Path

db_path=Path(__file__).parent / "sqlite_intro.db"
connection = sqlite3.connect(db_path)
cursor = connection.cursor()

cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_runs (
        run_id INTEGER PRIMARY KEY,
        status TEXT NOT NULL,
        total_cases INTEGER NOT NULL
    )
    """)

cursor.execute("""  INSERT INTO agent_runs (status, total_cases)
    VALUES (?, ?)
    """, ("completed", 8))

connection.commit()

cursor.execute("""
    UPDATE agent_runs
    SET status = ?
    WHERE run_id = ?
""", ("reviewed", 5))
cursor.execute("""
    DELETE FROM agent_runs
    WHERE run_id = ?
""", (5,))

connection.commit()

cursor.execute("""
    SELECT run_id, status, total_cases
    FROM agent_runs
    WHERE total_cases >= ?
    ORDER BY run_id DESC
""", (6,))

rows = cursor.fetchall()
for row in rows:
    print(row)

connection.close()