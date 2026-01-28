from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

def get_conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )

class TaskIn(BaseModel):
    title: str

@app.get("/health")
def health():
    return "ok"

@app.get("/tasks")
def list_tasks():
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, created_at FROM tasks ORDER BY id DESC")
            rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks")
def create_task(task: TaskIn):
    if not task.title.strip():
        raise HTTPException(status_code=400, detail="title 不能为空")
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tasks (title) VALUES (%s)", (task.title,))
            new_id = cur.lastrowid
        conn.close()
        return {"id": new_id, "message": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

