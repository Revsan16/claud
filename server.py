"""
Local web server for the Tamil transcriber.

Standard library only - no Flask, no npm. Runs one job at a time on a single
background worker, because a medium Whisper model on an 8GB Mac has no room
to run two at once.
"""

import json
import mimetypes
import queue
import re
import shutil
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import pipeline
from pipeline import DATA, Job

BASE = Path(__file__).resolve().parent
WEB = BASE / "web"
PORT = 8756

_jobs = {}           # id -> Job, for jobs created this session
_queue = queue.Queue()
_lock = threading.Lock()

YOUTUBE_RE = re.compile(
    r"^https?://(www\.|m\.|music\.)?(youtube\.com/(watch\?|shorts/|live/|embed/)|youtu\.be/)",
    re.I,
)


def worker():
    while True:
        job = _queue.get()
        try:
            job.run()
        except Exception as exc:
            job.set(status="error", stage="Stopped", error=str(exc))
        finally:
            _queue.task_done()


def read_meta(job_id):
    """Read a job from disk, so history survives a restart."""
    path = DATA / job_id / "meta.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def all_jobs():
    out = []
    for d in DATA.iterdir():
        if not d.is_dir():
            continue
        meta = read_meta(d.name)
        if meta:
            out.append(meta)
    out.sort(key=lambda m: m.get("created", ""), reverse=True)
    return out


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # keep the terminal readable

    # ---- helpers -------------------------------------------------------

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, data, ctype, filename=None):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if filename:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{filename}"'
            )
        self.end_headers()
        self.wfile.write(data)

    def body_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    # ---- routes --------------------------------------------------------

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            return self.serve_file(WEB / "index.html")

        if path.startswith("/web/"):
            name = unquote(path[len("/web/"):])
            target = (WEB / name).resolve()
            if WEB.resolve() not in target.parents:
                return self.send_json({"error": "Not found"}, 404)
            return self.serve_file(target)

        if path == "/api/jobs":
            return self.send_json({"jobs": all_jobs()})

        m = re.fullmatch(r"/api/jobs/([0-9a-f]{6,32})", path)
        if m:
            meta = read_meta(m.group(1))
            if not meta:
                return self.send_json({"error": "Not found"}, 404)
            return self.send_json(meta)

        m = re.fullmatch(r"/api/jobs/([0-9a-f]{6,32})/text/([\w.\-]+)", path)
        if m:
            return self.serve_job_file(m.group(1), m.group(2), download=False)

        m = re.fullmatch(r"/api/jobs/([0-9a-f]{6,32})/download/([\w.\-]+)", path)
        if m:
            return self.serve_job_file(m.group(1), m.group(2), download=True)

        return self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/jobs":
            data = self.body_json()
            url = (data.get("url") or "").strip()
            if not url:
                return self.send_json({"error": "Paste a YouTube link first."}, 400)
            if not YOUTUBE_RE.match(url):
                return self.send_json(
                    {"error": "That does not look like a YouTube link."}, 400
                )
            job = Job(
                url,
                model=data.get("model") or pipeline.DEFAULT_MODEL,
                do_english=bool(data.get("english", True)),
                do_summary=bool(data.get("summary", True)),
                tamil_mode=data.get("tamil_mode") or "fluent",
            )
            with _lock:
                _jobs[job.id] = job
            _queue.put(job)
            return self.send_json(job.meta, 201)

        return self.send_json({"error": "Not found"}, 404)

    def do_DELETE(self):
        m = re.fullmatch(r"/api/jobs/([0-9a-f]{6,32})", urlparse(self.path).path)
        if not m:
            return self.send_json({"error": "Not found"}, 404)
        job_id = m.group(1)
        meta = read_meta(job_id)
        if not meta:
            return self.send_json({"error": "Not found"}, 404)
        if meta.get("status") in ("queued", "running"):
            return self.send_json(
                {"error": "That one is still running. Wait for it to finish."}, 409
            )
        target = (DATA / job_id).resolve()
        if DATA.resolve() in target.parents:
            shutil.rmtree(target, ignore_errors=True)
        with _lock:
            _jobs.pop(job_id, None)
        return self.send_json({"ok": True})

    # ---- file serving --------------------------------------------------

    def serve_file(self, path):
        if not path.exists() or not path.is_file():
            return self.send_json({"error": "Not found"}, 404)
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/javascript":
            ctype += "; charset=utf-8"
        return self.send_bytes(path.read_bytes(), ctype)

    def serve_job_file(self, job_id, name, download):
        target = (DATA / job_id / name).resolve()
        job_dir = (DATA / job_id).resolve()
        if job_dir not in target.parents or not target.exists():
            return self.send_json({"error": "Not found"}, 404)
        data = target.read_bytes()
        if download:
            meta = read_meta(job_id) or {}
            slug = re.sub(r"[^\w\- ]", "", meta.get("title", "") or "transcript")[:60]
            slug = (slug.strip() or "transcript").replace(" ", "-")
            return self.send_bytes(
                data, "application/octet-stream", f"{slug}-{name}"
            )
        return self.send_bytes(data, "text/plain; charset=utf-8")


def reap_stale():
    """A job that was mid-flight when the app was last closed is not coming
    back. Mark it stopped, or the UI shows a progress bar that never moves."""
    for meta in all_jobs():
        if meta.get("status") not in ("running", "queued"):
            continue
        meta["status"] = "error"
        meta["stage"] = "Stopped"
        meta["error"] = "The app was closed while this was still running. Try it again."
        path = DATA / meta["id"] / "meta.json"
        try:
            path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
        # The audio file for an abandoned job is dead weight.
        for leftover in (DATA / meta["id"]).glob("audio.*"):
            try:
                leftover.unlink()
            except OSError:
                pass


def main():
    reap_stale()
    threading.Thread(target=worker, daemon=True).start()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as exc:
        if exc.errno in (48, 98):  # address already in use
            print("\n  The transcriber is already running in another window.")
            print(f"  Just open:  http://127.0.0.1:{PORT}/")
            print("  (Or close that window and start this one again.)\n")
            return
        raise
    url = f"http://127.0.0.1:{PORT}/"
    print("\n  Tamil transcriber is running.")
    print(f"  Open:  {url}")
    print("  Press Control-C in this window to stop it.\n")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.\n")


if __name__ == "__main__":
    main()
