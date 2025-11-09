from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pathlib import Path
import re
import requests

app = FastAPI(title="Nginx Dashboard")

SITES_AVAILABLE = Path("/etc/nginx/sites-available")
SITES_ENABLED = Path("/etc/nginx/sites-enabled")


@app.get("/api/sites")
def list_sites():
    """
    Lists sites with:
      - public URL (server_name)
      - internal port (from proxy_pass)
      - active status
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

            # server_name directive (public URL)
            for sn in re.findall(r"server_name\s+([^;]+);", content):
                server_names.update(sn.strip().split())

            # proxy_pass directive (internal backend URL)
            for pp in re.findall(r"proxy_pass\s+([^;]+);", content):
                # Extract port if available
                m = re.search(r":(\d+)", pp)
                if m:
                    internal_ports.add(m.group(1))
                else:
                    internal_ports.add("80")  # default if no port

        except Exception:
            server_names = set()
            internal_ports = set()

        # Combine each server_name with its internal port (simplify: first port if multiple)
        port = sorted(internal_ports)[0] if internal_ports else "N/A"
        for sn in sorted(server_names):
            sites.append({
                "site": sn,
                "active": active,
                "internal_port": port
            })

    return {"sites": sites}


@app.get("/api/ping")
def ping_url(url: str = Query(...)):
    """
    Ping the public site URL and return HTTP status code.
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url

    try:
        resp = requests.get(url, timeout=3)
        return {"url": url, "status_code": resp.status_code}
    except requests.RequestException as e:
        return {"url": url, "error": str(e)}, 502
