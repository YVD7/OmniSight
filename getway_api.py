import os
from dotenv import load_dotenv
from fastapi import FastAPI
from sqlalchemy import create_engine, text

load_dotenv()

# create engine for PostgreSQL database
db_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
engine = create_engine(db_url)
conn = engine.connect()


app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the OmniSight API!"}

# webhook build endpoint
@app.post("/webhook/build")
def webhook_build(payload: dict):
    # execute query to insert build data into the database
    query = text("INSERT INTO builds (build_id, status, timestamp) VALUES (:build_id, :status, :timestamp)")
    conn.execute(query, payload)
    return {"message": "Build data received and stored."}

# PR request endpoint
@app.get("/prs")
def get_prs():
    # execute query and convert result rows to JSON-serializable dicts
    query = text("SELECT * FROM pull_requests")
    result = conn.execute(query)
    rows = [dict(row) for row in result.fetchall()]
    return {"prs": rows}

# PR approval endpoint
@app.post("/prs/{pr_id}/approve")
def approve_pr(pr_id: int):
    # execute query to update the status of the pull request to 'approved'
    query = text("UPDATE pull_requests SET status='approved' WHERE id=:pr_id")
    conn.execute(query, {"pr_id": pr_id})
    return {"message": f"Pull request {pr_id} approved."}

# PR rejection endpoint
@app.post("/prs/{pr_id}/reject")
def reject_pr(pr_id: int):
    # execute query to update the status of the pull request to 'rejected'
    query = text("UPDATE pull_requests SET status='rejected' WHERE id=:pr_id")
    conn.execute(query, {"pr_id": pr_id})
    return {"message": f"Pull request {pr_id} rejected."}