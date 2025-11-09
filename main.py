from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import re
import httpx

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
    Lists nginx sites and extracts both listen ports and proxy_pass targets.
    """
    sites = []

    for site_file in SITES_AVAILABLE.iterdir():
        if not site_file.is_file():
            continue

        active = (SITES_ENABLED / site_file.name).exists()
        ports, backends = set(), set()

        try:
            content = site_file.read_text()

            # Parse listen ports
            for m in re.findall(r"listen\s+([^;]+);", content):
                port_match = re.search(r"(\d+)", m)
                if port_match:
                    ports.add(port_match.group(1))

            # Parse proxy_pass destinations
            for p in re.findall(r"proxy_pass\s+([^;]+);", content):
                backends.add(p.strip())

        except Exception:
            ports, backends = {"Error parsing file"}, set()

        sites.append({
            "name": site_file.name,
            "active": active,
            "ports": sorted(ports),
            "backends": sorted(backends),
        })

    return {"sites": sites}


@app.get("/api/ping")
async def ping_target(url: str = Query(..., description="Full URL to test")):
    """
    Backend proxy to check HTTP status of a URL.
    The frontend calls this since browsers can't reach arbitrary internal ports.
    """
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    try:
        async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
            resp = await client.get(url)
        return {"url": url, "status_code": resp.status_code}
    except Exception as e:
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
