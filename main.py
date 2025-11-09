from fastapi import FastAPI, HTTPException, Request, Query
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
    Lists nginx sites and extracts both listen ports and server_name / proxy_pass targets.
    """
    sites = []

    for site_file in SITES_AVAILABLE.iterdir():
        if not site_file.is_file():
            continue

        active = (SITES_ENABLED / site_file.name).exists()
        ports, backends = set(), set()
        server_names = set()

        try:
            content = site_file.read_text()

            # Parse listen ports (optional, may not be useful)
            for m in re.findall(r"listen\s+([^;]+);", content):
                port_match = re.search(r"(\d+)", m)
                if port_match:
                    ports.add(port_match.group(1))

            # Parse server_name directives (for real URLs)
            for sn in re.findall(r"server_name\s+([^;]+);", content):
                server_names.update(sn.strip().split())

            # Optionally parse proxy_pass too
            for p in re.findall(r"proxy_pass\s+([^;]+);", content):
                backends.add(p.strip())

        except Exception:
            ports, backends, server_names = {"Error"}, set(), set()

        sites.append({
            "name": site_file.name,
            "active": active,
            "ports": sorted(ports),
            "server_names": sorted(server_names),
            "backends": sorted(backends),
        })

    return {"sites": sites}


@app.get("/api/ping")
def ping_url(url: str = Query(..., description="Full URL to ping")):
    """
    Pings a full URL and returns the HTTP status code.
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url  # default to http

    try:
        resp = requests.get(url, timeout=3)
        return {"url": url, "status_code": resp.status_code}
    except requests.RequestException as e:
        return {"url": url, "error": str(e)}


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
