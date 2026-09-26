import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "sqlite_crud.db"

def init_db():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_runs (
            run_id INTEGER PRIMARY KEY,
            status TEXT NOT NULL,
            total_cases INTEGER NOT NULL
        )
    """)

    connection.commit()
    connection.close()


def create_run(status: str, total_cases: int):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO agent_runs (status, total_cases)
        VALUES (?, ?)
    """, (status, total_cases))

    connection.commit()

    new_run_id = cursor.lastrowid
    connection.close()

    return new_run_id

def get_all_runs():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    cursor.execute("""
        SELECT run_id, status, total_cases
        FROM agent_runs
        ORDER BY run_id DESC
    """)
    rows = cursor.fetchall()
    connection.close()
    return rows

def get_runs_by_status(status: str):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    cursor.execute("""
        SELECT run_id, status, total_cases
        FROM agent_runs
        WHERE status = ?
        ORDER BY run_id DESC
    """, (status,))
    rows = cursor.fetchall()
    connection.close()
    return rows

init_db()

normal_status = "completed"
normal_runs = get_runs_by_status(normal_status)
print("正常查询结果：", normal_runs)

malicious_status = "completed' OR 1=1 --"
malicious_runs = get_runs_by_status(malicious_status)
print("恶意输入查询结果：", malicious_runs)