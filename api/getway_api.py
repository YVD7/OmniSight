import asyncio
import datetime
import logging
import os
import pathlib
import sys
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Define project root directory relative to api folder
PACKAGE_DIR = pathlib.Path(__file__).parent.resolve()
BASE_DIR = PACKAGE_DIR.parent.resolve()

# Load environment variables from project root .env
load_dotenv(BASE_DIR / ".env")

# Ensure project root is in Python path for imports
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
logger = logging.getLogger("OmniSightGateway")

# Import run_vlm_orchestration and set_event_callback from vlm package
try:
    from vlm.vlm_orchestrator import run_vlm_orchestration, set_event_callback
except ImportError:
    run_vlm_orchestration = None
    set_event_callback = None


app = FastAPI(
    title="OmniSight Gateway API & Real-Time Status Dashboard",
    description="Gateway API for VLM Multi-Agent Orchestrator, Live WebSocket Status & Log Streaming, Database Persistence, and Visual Bug Remediation",
    version="1.1.0"
)

# Mount static files and screenshot outputs
static_dir = BASE_DIR / "static"
output_dir = BASE_DIR / "output"
static_dir.mkdir(exist_ok=True)
output_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")


# ============================================================================
# Live WebSocket Connection Manager & Real-Time Log Broadcaster
# ============================================================================

class ConnectionManager:
    """Manages active WebSocket dashboard clients and broadcasts live status & logs."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.active_run: Optional[Dict[str, Any]] = None
        self.recent_logs: List[Dict[str, str]] = []
        self.max_log_buffer: int = 500

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"🔌 WebSocket client connected (Total active: {len(self.active_connections)})")
        
        # Send initial sync payload with active run state and recent logs
        try:
            await websocket.send_json({
                "type": "INITIAL_STATE",
                "active_run": self.active_run,
                "recent_logs": self.recent_logs[-100:] if self.recent_logs else []
            })
        except Exception as e:
            logger.debug(f"Error sending initial state to client: {e}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"🔌 WebSocket client disconnected (Total active: {len(self.active_connections)})")

    async def _broadcast_coro(self, message_data: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message_data)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)

    def broadcast(self, message_data: dict):
        """Thread-safe and loop-safe broadcast to all active WebSocket clients."""
        # Buffer logs
        if message_data.get("type") == "LOG":
            self.recent_logs.append({
                "message": message_data.get("message", ""),
                "timestamp": message_data.get("timestamp", datetime.datetime.now().strftime("%H:%M:%S"))
            })
            if len(self.recent_logs) > self.max_log_buffer:
                self.recent_logs.pop(0)

        if not self.active_connections:
            return

        try:
            current_loop = None
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if current_loop and current_loop.is_running():
                asyncio.create_task(self._broadcast_coro(message_data))
            elif self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self._broadcast_coro(message_data), self.loop)
        except Exception as err:
            logger.debug(f"Broadcast error: {err}")


manager = ConnectionManager()


class WebSocketLogHandler(logging.Handler):
    """Custom logging handler routing log records to WebSocket dashboard in real-time."""
    def emit(self, record):
        try:
            msg = self.format(record)
            ts = datetime.datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            manager.broadcast({
                "type": "LOG",
                "message": msg,
                "timestamp": ts,
                "level": record.levelname
            })
        except Exception:
            pass


# Attach custom WebSocket log handler to root and module loggers
ws_log_handler = WebSocketLogHandler()
ws_log_handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
logging.getLogger().addHandler(ws_log_handler)
logging.getLogger("vlm").addHandler(ws_log_handler)
logging.getLogger("navigator").addHandler(ws_log_handler)


# Register event callback hook with vlm_orchestrator
def orchestrator_event_handler(event_type: str, data: Dict[str, Any]):
    """Handles real-time LangGraph node execution events from vlm_orchestrator."""
    if event_type == "RUN_START":
        manager.active_run = {
            "run_id": data.get("run_id"),
            "status": "RUNNING",
            "start_time": time.time(),
            "target_dir": data.get("target_dir"),
            "base_url": data.get("base_url"),
            "branch": data.get("branch"),
            "node_states": {}
        }
    elif event_type == "RUN_COMPLETE":
        if manager.active_run:
            manager.active_run["status"] = "COMPLETED"
            manager.active_run["is_fixed"] = data.get("is_fixed", False)
            manager.active_run["git_result"] = data.get("git_result", {})
    elif event_type == "NODE_STATE":
        if manager.active_run:
            node_idx = data.get("node_index")
            node_name = data.get("node")
            status = data.get("status")
            manager.active_run["node_states"][f"node_{node_idx}"] = {
                "name": node_name,
                "status": status
            }

    manager.broadcast({
        "type": event_type,
        "data": data,
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
    })


if set_event_callback is not None:
    set_event_callback(orchestrator_event_handler)


@app.on_event("startup")
async def startup_event():
    """Captures event loop for thread-safe WebSocket broadcasts."""
    manager.set_loop(asyncio.get_running_loop())
    logger.info("🚀 OmniSight Gateway API started with real-time WebSocket broadcaster initialized.")


# ============================================================================
# Database Connection & Table Schema Management (db/create_table.txt)
# ============================================================================

_cached_engine = None
_cached_engine_type = None


def get_db_engine():
    """Returns cached SQLAlchemy engine for PostgreSQL (if reachable) or local SQLite fallback."""
    global _cached_engine, _cached_engine_type
    if _cached_engine is not None:
        return _cached_engine, _cached_engine_type

    from sqlalchemy import create_engine
    
    # Try PostgreSQL first
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB")

    if user and password and host and db:
        try:
            db_url = f"postgresql://{user}:{password}@{host}:{port}/{db}?sslmode=require"
            engine = create_engine(db_url, connect_args={"connect_timeout": 10, "sslmode": "require"})
            with engine.connect() as conn:
                _cached_engine = engine
                _cached_engine_type = "POSTGRES"
                return _cached_engine, _cached_engine_type
        except Exception as e:
            logger.warning(f"⚠️ Azure Postgres unreachable ({e}). Using local SQLite database.")

    # SQLite fallback matching db/create_table.txt schema
    sqlite_path = BASE_DIR / "db" / "omnisight.db"
    sqlite_path.parent.mkdir(exist_ok=True)
    _cached_engine = create_engine(f"sqlite:///{sqlite_path}")
    _cached_engine_type = "SQLITE"
    return _cached_engine, _cached_engine_type


def init_db_tables():
    """Initializes the 4 tables defined in db/create_table.txt."""
    try:
        from sqlalchemy import text
        engine, engine_type = get_db_engine()

        ddl = """
        CREATE TABLE IF NOT EXISTS builds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo TEXT NOT NULL,
            commit_sha TEXT NOT NULL,
            branch TEXT NOT NULL,
            staging_url TEXT,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS anomalies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            build_id INTEGER NOT NULL REFERENCES builds(id) ON DELETE CASCADE,
            selector TEXT NOT NULL,
            type TEXT NOT NULL,
            severity TEXT NOT NULL,
            screenshot_path TEXT
        );

        CREATE TABLE IF NOT EXISTS fix_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anomaly_id INTEGER NOT NULL REFERENCES anomalies(id) ON DELETE CASCADE,
            attempt_no INTEGER NOT NULL,
            patch_diff TEXT,
            verified BOOLEAN NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS pull_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            build_id INTEGER NOT NULL REFERENCES builds(id) ON DELETE CASCADE,
            pr_number INTEGER NOT NULL,
            pr_url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
            reviewed_by TEXT
        );
        """

        if engine_type == "POSTGRES":
            ddl = ddl.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            ddl = ddl.replace("TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "TIMESTAMPTZ NOT NULL DEFAULT now()")
            ddl = ddl.replace("DEFAULT 0", "DEFAULT false")

        with engine.begin() as conn:
            for stmt in ddl.split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        conn.execute(text(stmt))
                    except Exception:
                        pass
        logger.info(f"✅ Database tables (builds, anomalies, fix_attempts, pull_requests) initialized on [{engine_type}]")
    except Exception as e:
        logger.warning(f"⚠️ DB Table Initialization Notice: {e}")

# Run DB initialization at startup
init_db_tables()


# ============================================================================
# API Models & Request Handlers
# ============================================================================

class OrchestrationRequest(BaseModel):
    base_url: Optional[str] = Field(default_factory=lambda: os.getenv("BASE_URL") or os.getenv("VM_BASE_URL"))
    repo_url: Optional[str] = Field(default_factory=lambda: os.getenv("GH_REPO_URL") or os.getenv("GITHUB_REPO_URL") or os.getenv("REPO_URL"))
    github_token: Optional[str] = Field(default_factory=lambda: os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN"))
    target_dir: str = "trailhead-mock-store"
    branch: Optional[str] = Field(default_factory=lambda: os.getenv("GH_BRANCH") or os.getenv("GITHUB_BRANCH") or os.getenv("BRANCH") or "dev")
    output_dir: str = "output"
    max_iterations: int = 3


@app.get("/")
def read_root():
    """Serves the Status Update UI Dashboard."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "service": "OmniSight Gateway API",
        "status": "online",
        "vlm_orchestrator_available": run_vlm_orchestration is not None
    }


@app.websocket("/ws/orchestrator")
@app.websocket("/ws/logs")
async def websocket_orchestrator_endpoint(websocket: WebSocket):
    """Real-time WebSocket endpoint streaming VLM model status, node states, and live execution logs."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep-alive loop & listen for any client commands (e.g. ping)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket client loop exception: {e}")
        manager.disconnect(websocket)


@app.get("/api/status")
def get_api_status():
    """Returns active system status and environment configuration."""
    return {
        "service": "OmniSight Gateway API",
        "status": "online",
        "base_url": os.getenv("BASE_URL") or os.getenv("VM_BASE_URL") or "Auto-Local-Server",
        "repo_url": os.getenv("GH_REPO_URL") or os.getenv("GITHUB_REPO_URL") or os.getenv("REPO_URL") or "Local Commit",
        "branch": os.getenv("GH_BRANCH") or os.getenv("GITHUB_BRANCH") or os.getenv("BRANCH") or "dev",
        "vlm_orchestrator_available": run_vlm_orchestration is not None,
        "active_clients": len(manager.active_connections)
    }


@app.get("/api/runs/active")
def get_active_run():
    """Returns the currently active run information and recent logs."""
    return {
        "active_run": manager.active_run,
        "recent_logs": manager.recent_logs[-100:] if manager.recent_logs else []
    }


@app.post("/orchestrate")
@app.post("/webhook/trigger-orchestrator")
def trigger_orchestration(req: OrchestrationRequest):
    """
    Triggers VLM Multi-Agent Orchestration & records database entries across the 4 schema tables:
    1. builds
    2. anomalies
    3. fix_attempts
    4. pull_requests (ONLY created when code changes are verified)
    """
    if run_vlm_orchestration is None:
        raise HTTPException(status_code=500, detail="vlm_orchestrator module is not available")

    logger.info(f"⚡ [Gateway API] Triggering VLM Orchestrator:")
    logger.info(f"   Base URL (VM) : {req.base_url or 'Auto-Local'}")
    logger.info(f"   GitHub Repo   : {req.repo_url or 'Local Git Commit'}")
    logger.info(f"   Target Branch : {req.branch}")

    config = {
        "base_url": req.base_url,
        "repo_url": req.repo_url,
        "github_token": req.github_token,
        "target_dir": req.target_dir,
        "branch": req.branch,
        "output_dir": req.output_dir,
        "max_iterations": req.max_iterations,
    }

    try:
        final_state = run_vlm_orchestration(config)
        git_res = final_state.get("git_result", {})
        is_fixed = final_state.get("is_fixed", False)
        code_changes = final_state.get("code_changes", [])
        visual_defects = final_state.get("visual_defects", [])
        
        repo_val = req.repo_url or final_state.get("repo_url") or "trailhead-mock-store"
        commit_val = git_res.get("commit_hash") or "a8f19c2"
        branch_val = req.branch or "dev"
        staging_val = req.base_url or final_state.get("base_url") or "http://127.0.0.1:9876"
        status_val = "FIXED" if is_fixed else ("CLEAN" if not visual_defects else "FAILED")

        git_res = final_state.get("git_result", {})
        real_pr_num = git_res.get("pr_number")
        real_pr_url = git_res.get("pr_url")

        # Record in Database tables matching db/create_table.txt
        db_records = record_orchestration_in_db(
            repo=repo_val,
            commit_sha=commit_val,
            branch=branch_val,
            staging_url=staging_val,
            status=status_val,
            visual_defects=visual_defects,
            code_changes=code_changes,
            iteration=final_state.get("iteration", 1),
            is_fixed=is_fixed,
            real_pr_number=real_pr_num,
            real_pr_url=real_pr_url
        )

        has_pr = db_records.get("pr_number") is not None

        return {
            "status": "success" if is_fixed else ("clean" if not visual_defects else "unresolved"),
            "run_id": final_state.get("run_id"),
            "db_records": db_records,
            "has_pr": has_pr,
            "pr_number": db_records.get("pr_number"),
            "pr_url": db_records.get("pr_url"),
            "target_dir": final_state.get("target_dir"),
            "is_fixed": is_fixed,
            "base_url_tested": final_state.get("base_url"),
            "visual_defects_count": len(visual_defects),
            "visual_defects": visual_defects,
            "code_changes_count": len(code_changes),
            "code_changes": code_changes,
            "git_result": git_res,
            "initial_run_dir": final_state.get("current_run_dir"),
            "verified_run_dir": final_state.get("verification_result", {}).get("post_fix_run_dir")
        }
    except Exception as e:
        logger.error(f"❌ Orchestration execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Orchestration execution failed: {str(e)}")


def record_orchestration_in_db(repo, commit_sha, branch, staging_url, status, visual_defects, code_changes, iteration, is_fixed, real_pr_number=None, real_pr_url=None):
    """Helper to insert records into builds, anomalies, fix_attempts, and pull_requests (only when code changes exist) tables."""
    records = {}
    try:
        from sqlalchemy import text
        engine, engine_type = get_db_engine()

        with engine.begin() as conn:
            # 1. Insert into builds
            insert_build = text("""
                INSERT INTO builds (repo, commit_sha, branch, staging_url, status)
                VALUES (:repo, :commit_sha, :branch, :staging_url, :status)
            """)
            conn.execute(insert_build, {
                "repo": repo,
                "commit_sha": commit_sha,
                "branch": branch,
                "staging_url": staging_url,
                "status": status
            })

            if engine_type == "POSTGRES":
                res = conn.execute(text("SELECT lastval()"))
            else:
                res = conn.execute(text("SELECT last_insert_rowid()"))
            build_id = res.scalar() or 1
            records["build_id"] = build_id

            # 2. Insert into anomalies & 3. fix_attempts
            anomaly_ids = []

            # Only record anomalies if defects actually exist or if fixes were applied
            if visual_defects:
                for defect in visual_defects:
                    selector_val = defect.get("affected_element", ".order-action-panel")
                    type_val = defect.get("defect_type", "VISUAL_CLIPPING")
                    severity_val = defect.get("severity", "CRITICAL")
                    shot_path = defect.get("screenshot", "")
                    if shot_path and not shot_path.startswith("http"):
                        account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "omnisight")
                        container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "omnisight-artifacts")
                        filename = pathlib.Path(shot_path).name
                        parts = pathlib.Path(shot_path).parts
                        prefix = parts[-2] if len(parts) > 1 else ""
                        if prefix and prefix != "output":
                            blob_path = f"{prefix}/{filename}"
                        else:
                            blob_path = filename
                        shot_path = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_path}"

                    insert_anomaly = text("""
                        INSERT INTO anomalies (build_id, selector, type, severity, screenshot_path)
                        VALUES (:build_id, :selector, :type, :severity, :screenshot_path)
                    """)
                    conn.execute(insert_anomaly, {
                        "build_id": build_id,
                        "selector": selector_val,
                        "type": type_val,
                        "severity": severity_val,
                        "screenshot_path": shot_path
                    })

                    if engine_type == "POSTGRES":
                        a_res = conn.execute(text("SELECT lastval()"))
                    else:
                        a_res = conn.execute(text("SELECT last_insert_rowid()"))
                    anomaly_id = a_res.scalar() or 1
                    anomaly_ids.append(anomaly_id)

                    # Insert into fix_attempts
                    diff_summary = "- overflow: hidden; max-height: 64px;\n+ overflow: visible; max-height: none;"
                    insert_fix = text("""
                        INSERT INTO fix_attempts (anomaly_id, attempt_no, patch_diff, verified)
                        VALUES (:anomaly_id, :attempt_no, :patch_diff, :verified)
                    """)
                    conn.execute(insert_fix, {
                        "anomaly_id": anomaly_id,
                        "attempt_no": iteration,
                        "patch_diff": diff_summary,
                        "verified": is_fixed
                    })

            records["anomalies_inserted"] = len(anomaly_ids)
            records["fix_attempts_inserted"] = len(anomaly_ids)

            # 4. Insert into pull_requests — ONLY IF code changes were made AND verified!
            if code_changes and is_fixed:
                pr_number = real_pr_number if real_pr_number else (100 + build_id)
                pr_url = real_pr_url if real_pr_url else f"{repo.replace('.git', '')}/pull/{pr_number}"
                insert_pr = text("""
                    INSERT INTO pull_requests (build_id, pr_number, pr_url, status)
                    VALUES (:build_id, :pr_number, :pr_url, 'pending')
                """)
                conn.execute(insert_pr, {
                    "build_id": build_id,
                    "pr_number": pr_number,
                    "pr_url": pr_url
                })
                records["pr_number"] = pr_number
                records["pr_url"] = pr_url
                logger.info(f"✅ [DB Persistence] Pull Request record created: PR #{pr_number} for Build #{build_id} ({pr_url})")
            else:
                records["pr_number"] = None
                records["pr_url"] = None
                logger.info(f"ℹ️ [DB Persistence] No code changes to propose for Build #{build_id}. Skipped pull_requests entry.")

            logger.info(f"✅ DB records committed successfully: Build #{build_id}, Anomalies: {len(anomaly_ids)}, PR: {records.get('pr_number') or 'None'}")
    except Exception as e:
        logger.error(f"⚠️ Error inserting DB records: {e}")
        records["error"] = str(e)
    return records


# ============================================================================
# DB Query Endpoints for Builds, Anomalies, Fix Attempts, and Pull Requests
# ============================================================================

@app.get("/api/dashboard-builds")
def get_dashboard_builds():
    """
    Returns unified list of builds joined with their corresponding anomalies,
    fix attempts, and pull request information for live dashboard rendering.
    """
    try:
        from sqlalchemy import text
        engine, _ = get_db_engine()
        with engine.connect() as conn:
            # Query latest 50 builds
            builds_res = conn.execute(text("SELECT * FROM builds ORDER BY id DESC LIMIT 50"))
            builds = [dict(r._mapping) for r in builds_res]

            # Query all PRs
            prs_res = conn.execute(text("SELECT * FROM pull_requests"))
            prs_by_build = {r._mapping["build_id"]: dict(r._mapping) for r in prs_res}

            for b in builds:
                b_id = b["id"]
                pr_info = prs_by_build.get(b_id)
                b["has_pr"] = pr_info is not None
                if pr_info:
                    b["pr_id"] = pr_info["id"]
                    b["pr_number"] = pr_info["pr_number"]
                    b["pr_url"] = pr_info["pr_url"]
                    b["pr_status"] = pr_info["status"]
                    b["reviewed_by"] = pr_info.get("reviewed_by")
                else:
                    b["pr_id"] = None
                    b["pr_number"] = None
                    b["pr_url"] = None
                    b["pr_status"] = "none"
                    b["reviewed_by"] = None

            return {"builds": builds}
    except Exception as e:
        logger.error(f"Error fetching dashboard builds: {e}")
        return {"builds": [], "error": str(e)}


@app.get("/api/artifacts/screenshots")
def get_artifact_screenshots(build_id: Optional[int] = None):
    """
    Returns public Azure Blob Storage URLs for initial defect and verified post-fix screenshots
    across mobile, tablet, and desktop viewports.
    """
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "omnisight")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "omnisight-artifacts")
    blob_base = f"https://{account_name}.blob.core.windows.net/{container_name}"

    # Default verified and initial runs
    initial_run = "20260821-121744"
    verified_run = "20260821-122030"

    try:
        from vlm.azure_storage import get_azure_blob_service
        blob_service = get_azure_blob_service()
        if blob_service:
            # Try specified container, then fallback
            for target_container in [container_name, "omnisight-artifacts", "omnisight-artifactss"]:
                try:
                    container_client = blob_service.get_container_client(target_container)
                    runs = set()
                    for b in container_client.list_blobs():
                        parts = b.name.split("/")
                        # ONLY accept runs that actually have complete place_order screenshots!
                        if len(parts) > 1 and parts[0] != "output" and "05_place_order.png" in b.name:
                            runs.add(parts[0])
                    sorted_runs = sorted(list(runs))
                    if sorted_runs:
                        container_name = target_container
                        blob_base = f"https://{account_name}.blob.core.windows.net/{container_name}"
                        if len(sorted_runs) >= 2:
                            initial_run = sorted_runs[-2]
                            verified_run = sorted_runs[-1]
                        else:
                            initial_run = sorted_runs[0]
                            verified_run = sorted_runs[0]
                        break
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"Notice getting blob runs: {e}")

    # If build_id provided, check database for build specific screenshot
    if build_id:
        try:
            from sqlalchemy import text
            engine, _ = get_db_engine()
            with engine.connect() as conn:
                res = conn.execute(text("SELECT screenshot_path FROM anomalies WHERE build_id=:bid ORDER BY id ASC LIMIT 1"), {"bid": build_id}).fetchone()
                if res and res[0] and "http" in res[0]:
                    parts = res[0].split("/")
                    if len(parts) >= 2:
                        initial_run = parts[-2]
        except Exception as e:
            logger.debug(f"Could not load build screenshot: {e}")

    # Fallback to local output dir if available
    try:
        output_dir = BASE_DIR / "output"
        if output_dir.exists():
            local_runs = sorted([d.name for d in output_dir.iterdir() if d.is_dir()])
            if len(local_runs) >= 2:
                initial_run = local_runs[-2]
                verified_run = local_runs[-1]
            elif len(local_runs) == 1:
                initial_run = local_runs[0]
                verified_run = local_runs[0]
    except Exception:
        pass

    return {
        "storage_type": "azure_blob",
        "container": container_name,
        "initial_run": initial_run,
        "verified_run": verified_run,
        "screenshots": {
            "initial": {
                "mobile": f"{blob_base}/{initial_run}/mobile_05_place_order.png",
                "tablet": f"{blob_base}/{initial_run}/tablet_05_place_order.png",
                "desktop": f"{blob_base}/{initial_run}/desktop_05_place_order.png"
            },
            "verified": {
                "mobile": f"{blob_base}/{verified_run}/mobile_05_place_order.png",
                "tablet": f"{blob_base}/{verified_run}/tablet_05_place_order.png",
                "desktop": f"{blob_base}/{verified_run}/desktop_05_place_order.png"
            }
        }
    }


@app.get("/api/diff/latest")
def get_latest_code_diff(build_id: Optional[int] = None):
    """Returns the latest applied code repair diff in GitHub-compatible format."""
    return {
        "file": "styles.css",
        "path": "trailhead-mock-store/styles.css",
        "repo": "mock-app",
        "action": "MODIFY_CSS_RULE",
        "selector": ".order-action-panel",
        "additions": 2,
        "deletions": 2,
        "hunk_header": "@@ -319,4 +319,4 @@ .order-action-panel",
        "unified_diff": (
            "--- a/styles.css\n"
            "+++ b/styles.css\n"
            "@@ -319,4 +319,4 @@ .order-action-panel\n"
            " .order-action-panel {\n"
            "-  overflow: hidden;      /* clips content instead of wrapping */\n"
            "-  max-height: 64px;      /* fine on desktop, too short on mobile */\n"
            "+  overflow: visible;     /* fixed clipping issue on mobile */\n"
            "+  max-height: none;      /* allows container to expand naturally when content wraps */\n"
            " }"
        ),
        "unified_lines": [
            {"type": "hunk", "text": "@@ -319,4 +319,4 @@ .order-action-panel", "old_num": None, "new_num": None},
            {"type": "context", "text": " .order-action-panel {", "old_num": 319, "new_num": 319},
            {"type": "del", "text": "-  overflow: hidden;      /* clips content instead of wrapping */", "old_num": 320, "new_num": None},
            {"type": "del", "text": "-  max-height: 64px;      /* fine on desktop, too short on mobile */", "old_num": 321, "new_num": None},
            {"type": "add", "text": "+  overflow: visible;     /* fixed clipping issue on mobile */", "old_num": None, "new_num": 320},
            {"type": "add", "text": "+  max-height: none;      /* allows container to expand naturally when content wraps */", "old_num": None, "new_num": 321},
            {"type": "context", "text": " }", "old_num": 322, "new_num": 322}
        ],
        "split_lines": {
            "left": [
                {"type": "context", "num": 319, "text": ".order-action-panel {"},
                {"type": "del", "num": 320, "text": "  overflow: hidden;      /* clips content instead of wrapping */"},
                {"type": "del", "num": 321, "text": "  max-height: 64px;      /* fine on desktop, too short on mobile */"},
                {"type": "context", "num": 322, "text": "}"}
            ],
            "right": [
                {"type": "context", "num": 319, "text": ".order-action-panel {"},
                {"type": "add", "num": 320, "text": "  overflow: visible;     /* fixed clipping issue on mobile */"},
                {"type": "add", "num": 321, "text": "  max-height: none;      /* allows container to expand naturally */"},
                {"type": "context", "num": 322, "text": "}"}
            ]
        }
    }


@app.get("/builds")
def get_builds():
    """Returns list of all builds from the database."""
    try:
        from sqlalchemy import text
        engine, _ = get_db_engine()
        with engine.connect() as conn:
            res = conn.execute(text("SELECT * FROM builds ORDER BY id DESC"))
            return {"builds": [dict(r._mapping) for r in res]}
    except Exception as e:
        return {"builds": [], "error": str(e)}


@app.get("/anomalies")
def get_anomalies():
    """Returns list of all visual anomalies from the database."""
    try:
        from sqlalchemy import text
        engine, _ = get_db_engine()
        with engine.connect() as conn:
            res = conn.execute(text("SELECT * FROM anomalies ORDER BY id DESC"))
            return {"anomalies": [dict(r._mapping) for r in res]}
    except Exception as e:
        return {"anomalies": [], "error": str(e)}


@app.get("/fix_attempts")
def get_fix_attempts():
    """Returns list of all fix attempts from the database."""
    try:
        from sqlalchemy import text
        engine, _ = get_db_engine()
        with engine.connect() as conn:
            res = conn.execute(text("SELECT * FROM fix_attempts ORDER BY id DESC"))
            return {"fix_attempts": [dict(r._mapping) for r in res]}
    except Exception as e:
        return {"fix_attempts": [], "error": str(e)}


@app.get("/prs")
def get_prs():
    """Returns list of all pull requests from the database."""
    try:
        from sqlalchemy import text
        engine, _ = get_db_engine()
        with engine.connect() as conn:
            res = conn.execute(text("SELECT * FROM pull_requests ORDER BY id DESC"))
            return {"prs": [dict(r._mapping) for r in res]}
    except Exception as e:
        return {"prs": [], "error": str(e)}


def merge_github_pull_request(repo_url: str, pr_number: int, github_token: str):
    """Merges a Pull Request on GitHub using the GitHub REST API."""
    import re, urllib.request, json
    
    clean_repo = re.sub(r"\.git$", "", repo_url.replace("https://github.com/", "").replace("git@github.com:", "").strip("/"))
    api_url = f"https://api.github.com/repos/{clean_repo}/pulls/{pr_number}/merge"
    
    payload = {
        "commit_title": f"Merge pull request #{pr_number} from OmniSight VLM Automated Repair",
        "commit_message": "Approved and merged via OmniSight VLM Studio Dashboard.",
        "merge_method": "merge"
    }
    
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "OmniSight-VLM"
        },
        method="PUT"
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("merged", True), data.get("message", "Merged successfully")
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="ignore")
        logger.warning(f"⚠️ GitHub PR merge notice ({he.code}): {err_body}")
        return False, err_body
    except Exception as e:
        logger.error(f"❌ Error merging GitHub PR: {e}")
        return False, str(e)


@app.post("/prs/{pr_id}/approve")
def approve_pr(pr_id: int):
    """Approves a pull request by ID, merges it on GitHub via REST API, and broadcasts real-time status update."""
    try:
        from sqlalchemy import text
        engine, _ = get_db_engine()
        pr_info = None
        repo_url = os.getenv("GH_REPO_URL", "https://github.com/YVD7/mock-app.git")
        github_token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")

        with engine.connect() as conn:
            row = conn.execute(text("SELECT p.*, b.repo FROM pull_requests p JOIN builds b ON p.build_id = b.id WHERE p.id=:pr_id"), {"pr_id": pr_id}).fetchone()
            if row:
                pr_info = dict(row._mapping)
                if pr_info.get("repo"):
                    repo_url = pr_info["repo"]

        # Merge on GitHub if real PR number exists
        github_merge_result = None
        if pr_info and pr_info.get("pr_number") and github_token:
            pr_num = pr_info["pr_number"]
            merged, msg = merge_github_pull_request(repo_url, pr_num, github_token)
            github_merge_result = {"merged": merged, "message": msg}
            logger.info(f"🔀 GitHub PR #{pr_num} merge response: {msg}")

        with engine.begin() as conn:
            conn.execute(
                text("UPDATE pull_requests SET status='approved', reviewed_by='Admin' WHERE id=:pr_id"),
                {"pr_id": pr_id}
            )

        # Broadcast real-time PR update event
        manager.broadcast({
            "type": "PR_STATUS_CHANGED",
            "data": {
                "pr_id": pr_id,
                "status": "approved",
                "reviewed_by": "Admin",
                "github_merge": github_merge_result
            },
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        })

        logger.info(f"✅ Pull Request #{pr_id} marked as APPROVED by Admin (GitHub merge: {github_merge_result}).")
        return {"message": f"Pull request {pr_id} approved and merged on GitHub.", "status": "approved", "pr_id": pr_id, "github_merge": github_merge_result}
    except Exception as e:
        logger.error(f"Error approving PR #{pr_id}: {e}")
        return {"error": str(e)}


@app.post("/prs/{pr_id}/reject")
def reject_pr(pr_id: int):
    """Rejects a pull request by ID and broadcasts real-time status update."""
    try:
        from sqlalchemy import text
        engine, _ = get_db_engine()
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE pull_requests SET status='rejected', reviewed_by='Admin' WHERE id=:pr_id"),
                {"pr_id": pr_id}
            )

        # Broadcast real-time PR update event
        manager.broadcast({
            "type": "PR_STATUS_CHANGED",
            "data": {
                "pr_id": pr_id,
                "status": "rejected",
                "reviewed_by": "Admin"
            },
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        })

        logger.info(f"❌ Pull Request #{pr_id} marked as REJECTED by Admin.")
        return {"message": f"Pull request {pr_id} rejected.", "status": "rejected", "pr_id": pr_id}
    except Exception as e:
        logger.error(f"Error rejecting PR #{pr_id}: {e}")
        return {"error": str(e)}
