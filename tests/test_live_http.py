"""One real TCP smoke test complements the in-process API/database cases."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def test_uvicorn_serves_authenticated_crud_over_real_http(settings, partner_payload):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "partner_catalog.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={
            **os.environ,
            "PARTNER_API_KEY": settings.api_key,
            "PARTNER_DATABASE_URL": settings.database_url,
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            assert process.poll() is None, "Uvicorn exited before becoming ready"
            try:
                with urllib.request.urlopen(base + "/health", timeout=0.5) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(0.05)
        else:
            raise AssertionError("Uvicorn readiness timeout")
        request = urllib.request.Request(
            base + "/v1/partners",
            data=json.dumps(partner_payload).encode(),
            headers={"X-API-Key": settings.api_key, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            assert response.status == 201
            created = json.load(response)
        query = urllib.request.Request(
            base + "/v1/partners/" + created["id"], headers={"X-API-Key": settings.api_key}
        )
        with urllib.request.urlopen(query, timeout=3) as response:
            assert json.load(response)["code"] == partner_payload["code"]
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
