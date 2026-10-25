"""Download every pending entry in jobs/*.json to media/<path>, then mark the job done and drop its links.

A job file: {"id": "...", "files": [{"url": "https://...", "path": "lion/vo_a_1.mp3"}]}
Only https links on known media hosts are fetched, and paths stay inside media/.
"""
import hashlib, json, pathlib, time, urllib.parse, urllib.request

ALLOWED = ("storage.googleapis.com", "googleapis.com", "elevenlabs.io", "cloudfront.net", "higgsfield.ai")
ROOT = pathlib.Path("media").resolve()

def allowed(url):
    u = urllib.parse.urlparse(url)
    return u.scheme == "https" and any(u.hostname == h or u.hostname.endswith("." + h) for h in ALLOWED)

def fetch(url, dest):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "media-courier/1"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if not data:
                raise IOError("empty response")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return len(data), hashlib.sha256(data).hexdigest()
        except Exception as e:  # retry transient errors
            print(f"  attempt {attempt + 1} failed: {e}")
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"could not fetch {dest}")

for job in sorted(pathlib.Path("jobs").glob("*.json")):
    spec = json.loads(job.read_text())
    if spec.get("status") == "done":
        continue
    print(f"job {job.name}")
    results = []
    for f in spec.get("files", []):
        dest = (ROOT / f["path"]).resolve()
        if ROOT not in dest.parents:
            raise SystemExit(f"bad path {f['path']}")
        if not allowed(f["url"]):
            raise SystemExit(f"host not allowed for {f['path']}")
        size, sha = fetch(f["url"], dest)
        print(f"  {f['path']}: {size} bytes")
        results.append({"path": f["path"], "bytes": size, "sha256": sha})
    # links are dropped from the job once fetched; the files now live in media/
    job.write_text(json.dumps({"id": spec.get("id"), "status": "done", "fetched": results}, indent=1))
