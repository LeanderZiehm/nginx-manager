from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import re

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
    sites = []

    for site_file in SITES_AVAILABLE.iterdir():
        if site_file.is_file():
            active = (SITES_ENABLED / site_file.name).exists()

            # Read the nginx config and parse listen directives
            ports = []
            try:
                content = site_file.read_text()
                # Matches things like:
                # listen 80;
                # listen 443 ssl;
                # listen [::]:8080;
                # listen 127.0.0.1:9000 default_server;
                matches = re.findall(r"listen\s+([^;]+);", content)
                for m in matches:
                    # Clean and normalize ports
                    port_part = re.search(r"(\d+)", m)
                    if port_part:
                        ports.append(port_part.group(1))
            except Exception:
                ports = ["Error parsing file"]

            sites.append({
                "name": site_file.name,
                "active": active,
                "ports": sorted(set(ports))
            })

    return {"sites": sites}


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
