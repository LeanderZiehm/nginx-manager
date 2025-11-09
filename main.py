from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import re
import requests

app = FastAPI(title="Nginx Dashboard")

SITES_AVAILABLE = Path("/etc/nginx/sites-available")
SITES_ENABLED = Path("/etc/nginx/sites-enabled")
NGINX_LOG_DIR = Path("/var/log/nginx")

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/sites")
def list_sites():
    """
    List Nginx sites with server_name values.
    """
    sites = []
    for site_file in SITES_AVAILABLE.iterdir():
        if not site_file.is_file():
            continue

        active = (SITES_ENABLED / site_file.name).exists()
        server_names = set()

        try:
            content = site_file.read_text()
            # Extract server_name directives
            for sn in re.findall(r"server_name\s+([^;]+);", content):
                server_names.update(sn.strip().split())
        except Exception:
            server_names = set()

        sites.append({
            "name": site_file.name,
            "active": active,
            "server_names": sorted(server_names),
        })

    return {"sites": sites}


@app.get("/api/ping")
def ping_url(url: str = Query(..., description="Full URL to ping")):
    """
    Pings the real server_name URL and returns HTTP status.
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url  # default to http

    try:
        resp = requests.get(url, timeout=3)
        return {"url": url, "status_code": resp.status_code}
    except requests.RequestException as e:
        return JSONResponse({"url": url, "error": str(e)}, status_code=502)


@app.get("/api/logs")
def list_logs():
    logs = [p.name for p in NGINX_LOG_DIR.glob("*")]
    return {"logs": logs}


@app.get("/api/logs/{log_file}", response_class=PlainTextResponse)
def read_log(log_file: str, lines: int = 200):
    file_path = NGINX_LOG_DIR / log_file
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Log not found")

    with open(file_path, "r") as f:
        content = f.readlines()

    return "".join(content[-lines:])
