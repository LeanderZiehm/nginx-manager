from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import re
import requests

app = FastAPI(title="Nginx Dashboard")

# Paths for Nginx configs and logs
SITES_AVAILABLE = Path("/etc/nginx/sites-available")
SITES_ENABLED = Path("/etc/nginx/sites-enabled")
NGINX_LOG_DIR = Path("/var/log/nginx")

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """
    Serves the dashboard HTML page.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/sites")
def list_sites():
    """
    Lists sites with:
      - site (public URL)
      - active status
      - internal port (from proxy_pass)
    """
    sites = []

    for site_file in SITES_AVAILABLE.iterdir():
        if not site_file.is_file():
            continue

        active = (SITES_ENABLED / site_file.name).exists()
        server_names = set()
        internal_ports = set()

        try:
            content = site_file.read_text()

            # Extract server_name (public URL)
            for sn in re.findall(r"server_name\s+([^;]+);", content):
                server_names.update(sn.strip().split())

            # Extract proxy_pass URLs (internal backend)
            for pp in re.findall(r"proxy_pass\s+([^;]+);", content):
                # Extract port if present
                m = re.search(r":(\d+)", pp)
                if m:
                    internal_ports.add(m.group(1))
                else:
                    internal_ports.add("80")  # default if no port
        except Exception:
            server_names = set()
            internal_ports = set()

        # Use first internal port if multiple
        port = sorted(internal_ports)[0] if internal_ports else "N/A"

        for sn in sorted(server_names):
            sites.append({
                "site": sn,
                "active": active,
                "internal_port": port
            })

    return {"sites": sites}


@app.get("/api/ping")
def ping_url(url: str = Query(..., description="Full URL to ping")):
    """
    Ping the public site URL and return HTTP status code.
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url  # default to HTTP

    try:
        resp = requests.get(url, timeout=3)
        return {"url": url, "status_code": resp.status_code}
    except requests.RequestException as e:
        return JSONResponse({"url": url, "error": str(e)}, status_code=502)


@app.get("/api/logs")
def list_logs():
    """
    Lists all Nginx log files.
    """
    logs = [p.name for p in NGINX_LOG_DIR.glob("*")]
    return {"logs": logs}


@app.get("/api/logs/{log_file}", response_class=PlainTextResponse)
def read_log(log_file: str, lines: int = 200):
    """
    Returns the last 'lines' lines of a log file.
    """
    file_path = NGINX_LOG_DIR / log_file
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Log not found")

    with open(file_path, "r") as f:
        content = f.readlines()

    return "".join(content[-lines:])
