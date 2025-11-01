from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pathlib import Path
import glob

app = FastAPI(title="Nginx Dashboard API")

# Paths to Nginx configs and logs
SITES_AVAILABLE = Path("/etc/nginx/sites-available")
SITES_ENABLED = Path("/etc/nginx/sites-enabled")
NGINX_LOG_DIR = Path("/var/log/nginx")

@app.get("/sites")
def list_sites():
    """List all Nginx sites and indicate if they are active."""
    sites = []
    for site_file in SITES_AVAILABLE.iterdir():
        if site_file.is_file():
            active = (SITES_ENABLED / site_file.name).exists()
            sites.append({"name": site_file.name, "active": active})
    return {"sites": sites}

@app.get("/logs/{log_file_name}", response_class=PlainTextResponse)
def read_log(log_file_name: str, lines: int = 100):
    """Read the last N lines from a log file."""
    log_file_path = NGINX_LOG_DIR / log_file_name
    if not log_file_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
    
    try:
        with open(log_file_path, "r") as f:
            all_lines = f.readlines()
        return "".join(all_lines[-lines:])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs")
def list_logs():
    """List all available Nginx log files."""
    logs = [p.name for p in NGINX_LOG_DIR.glob("*")]
    return {"logs": logs}
