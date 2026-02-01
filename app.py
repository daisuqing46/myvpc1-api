from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import pymysql
from dotenv import load_dotenv

# 1) 读取 .env（默认读取当前目录下的 .env）
#    你也可以把 env 文件放到 /etc/task-api/env，然后改成 load_dotenv("/etc/task-api/env")
load_dotenv()

app = FastAPI()


# ---------- DB ----------
def get_conn():
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    dbname = os.getenv("DB_NAME")
    port = int(os.getenv("DB_PORT", "3306"))

    # 环境变量不全时，直接给出清晰错误
    missing = [k for k, v in {
        "DB_HOST": host,
        "DB_USER": user,
        "DB_PASSWORD": password,
        "DB_NAME": dbname,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=dbname,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def ensure_table():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    done TINYINT(1) NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
    finally:
        conn.close()


@app.on_event("startup")
def on_startup():
    # 服务启动时自动建表
    ensure_table()


# ---------- Schemas ----------
class TaskCreate(BaseModel):
    title: str


class TaskUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


# ---------- Routes ----------
@app.get("/health")
def health():
    # 能连上 DB 就返回 ok
    try:
        conn = get_conn()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks")
def list_tasks():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, done, created_at FROM tasks ORDER BY id DESC;")
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


@app.post("/tasks")
def create_task(payload: TaskCreate):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tasks (title) VALUES (%s);", (payload.title,))
            task_id = cur.lastrowid
            cur.execute("SELECT id, title, done, created_at FROM tasks WHERE id=%s;", (task_id,))
            return cur.fetchone()
    finally:
        conn.close()


@app.patch("/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tasks WHERE id=%s;", (task_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Task not found")

            fields = []
            values = []
            if payload.title is not None:
                fields.append("title=%s")
                values.append(payload.title)
            if payload.done is not None:
                fields.append("done=%s")
                values.append(1 if payload.done else 0)

            if not fields:
                raise HTTPException(status_code=400, detail="No fields to update")

            values.append(task_id)
            sql = f"UPDATE tasks SET {', '.join(fields)} WHERE id=%s;"
            cur.execute(sql, tuple(values))

            cur.execute("SELECT id, title, done, created_at FROM tasks WHERE id=%s;", (task_id,))
            return cur.fetchone()
    finally:
        conn.close()


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id=%s;", (task_id,))
            return {"deleted": cur.rowcount}
    finally:
        conn.close()


