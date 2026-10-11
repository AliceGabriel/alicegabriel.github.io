#!/usr/bin/env python3
"""Copy pictures and PDFs from the old Jimdo site into this repository.

Run once, from the top folder of the repository:

    python3 tools/import_from_jimdo.py

What it does
  1. Saves a copy of each page of the Jimdo site in tools/jimdo-snapshot/pages/.
  2. Downloads every PDF that the pages link to on Jimdo's file storage into
     assets/papers/ (the CV goes to assets/files/) and points the links in the
     Markdown pages at the local copies.
  3. Downloads every picture into assets/img/<page>/. Where the number of
     pictures found on a page equals the number of picture slots in that page
     (written as IMPORT:page-01, IMPORT:page-02, ...), it fills the slots in order.
     Where the numbers differ it changes nothing on that page and says so.
  4. Lists the YouTube videos it finds on each page.
  5. Compares the text and the link targets of each Jimdo page with the new page
     and writes the differences to tools/jimdo-snapshot/text-check.txt.

Nothing is deleted. Running it twice is safe: finished downloads are skipped.
It needs Python 3.8 or newer and no extra packages.
"""

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

SITE = "https://www.alicegabriel.com"

# page name, address on the Jimdo site, Markdown file in this repository
PAGES = [
    ("home", "/", "index.md"),
    ("team", "/team/", "team.md"),
    ("publications", "/publications/", "publications.md"),
    ("projects", "/projects/", "projects.md"),
    ("about-me", "/about-me/", "about-me.md"),
    ("in-the-media", "/in-the-media/", "in-the-media.md"),
    ("codes-and-hpc-training", "/codes-and-hpc-training/", "codes-and-hpc-training.md"),
    ("teaching", "/teaching/", "teaching.md"),
]

# How a request introduces itself. Jimdo's servers turn some combinations away
# (HTTP 403), so each host is tried with the next one until one is accepted.
SCRIPT_AGENT = "alicegabriel-site-migration/1.0 (+https://github.com/AliceGabriel/alicegabriel.github.io)"
BROWSER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
REQUEST_STYLES = [
    ("python", SCRIPT_AGENT),
    ("python, browser name", BROWSER_AGENT),
    ("curl", SCRIPT_AGENT),
    ("curl, browser name", BROWSER_AGENT),
]
REFUSED = (403, 406, 429, 503)   # answers that mean "not for you", as opposed to "not there"
accepted_style = {}              # host -> position in REQUEST_STYLES that worked last
refusals_logged = {}             # host -> number of refusals already written to the log
strikes = {}                     # host -> requests in a row that failed in every style
GIVE_UP_AFTER = 4                # stop asking a host that keeps turning everything away
GITHUB_FILE_LIMIT = 95 * 1024 * 1024  # GitHub refuses files of 100 MB and more

FILE_URL = re.compile(r"https://storage\.e\.jimdo\.com/file/[0-9a-fA-F-]{36}/[^\s\"'<>\\]+")
MARKDOWN_FILE_LINK = re.compile(
    r"\]\((https://storage\.e\.jimdo\.com/file/[0-9a-fA-F-]{36}/(?:[^()\s]|\([^()\s]*\))+)\)"
)
# A picture on Jimdo's storage is identified by a site number and a file id.
IMAGE_ID = re.compile(r"/image/(\d+)/([0-9a-fA-F-]{36})\.([A-Za-z0-9]{2,5})")
IMAGE_URL = re.compile(r"https://storage\.e\.jimdo\.com/[^\s\"'<>\\]*?/image/\d+/[0-9a-fA-F-]{36}\.[A-Za-z0-9]{2,5}")
YOUTUBE_ID = re.compile(
    r"(?:youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=|v/)|youtu\.be/|ytimg\.com/vi/|[\"']videoId[\"']\s*:\s*[\"'])"
    r"([A-Za-z0-9_-]{11})"
)
CONTENT_TYPES = {
    "image/jpeg": "jpg", "image/png": "png", "image/gif": "gif",
    "image/webp": "webp", "image/svg+xml": "svg", "image/avif": "avif",
}


def log(message=""):
    print(message, flush=True)


class Refused(Exception):
    """The server answered, but turned the request away."""

    def __init__(self, url, code, detail=""):
        super().__init__(f"HTTP {code}{' (' + detail + ')' if detail else ''}")
        self.url, self.code, self.detail = url, code, detail


def describe_answer(headers, body):
    """The few response details that tell a missing page from a blocked request."""
    parts = []
    for name in ("Server", "cf-mitigated", "cf-ray", "x-amzn-waf-action", "x-cache", "Retry-After"):
        value = headers.get(name) if headers else None
        if value:
            parts.append(f"{name}: {value}")
    text = re.sub(r"\s+", " ", re.sub(rb"<[^>]+>", b" ", body or b"").decode("utf-8", errors="replace")).strip()
    if text:
        parts.append("page says: " + text[:160])
    return "; ".join(parts)


def get_with_python(url, agent, accept):
    request = urllib.request.Request(url, headers={
        "User-Agent": agent, "Accept": accept, "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = response.read()
            kind = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            return data, kind
    except urllib.error.HTTPError as error:
        body = b""
        try:
            body = error.read(4000)
        except Exception:  # noqa: BLE001 - the body is only used for the log
            pass
        raise Refused(url, error.code, describe_answer(error.headers, body)) from None


def get_with_curl(url, agent, accept):
    """The same request sent by the curl program, which some servers accept where Python is refused."""
    if not shutil.which("curl"):
        raise Refused(url, 0, "curl is not installed")
    with tempfile.TemporaryDirectory() as folder:
        body_file, head_file = os.path.join(folder, "body"), os.path.join(folder, "head")
        done = subprocess.run(
            ["curl", "--silent", "--show-error", "--location", "--compressed", "--max-time", "120",
             "--user-agent", agent, "--header", f"Accept: {accept}", "--header", "Accept-Language: en-US,en;q=0.9",
             "--output", body_file, "--dump-header", head_file, "--write-out", "%{http_code}\n%{content_type}", url],
            capture_output=True, text=True, check=False,
        )
        if done.returncode != 0:
            raise OSError(f"curl: {done.stderr.strip()[:200] or 'error ' + str(done.returncode)}")
        code_text, _, kind = done.stdout.partition("\n")
        code = int(code_text) if code_text.strip().isdigit() else 0
        data = Path(body_file).read_bytes() if os.path.exists(body_file) else b""
        if code >= 400 or code == 0:
            headers = {}
            if os.path.exists(head_file):
                for line in Path(head_file).read_text(encoding="latin-1").splitlines():
                    name, colon, value = line.partition(":")
                    if colon:
                        headers[name.strip()] = value.strip()
            lookup = {k.lower(): v for k, v in headers.items()}
            raise Refused(url, code, describe_answer({n: lookup.get(n.lower()) for n in
                                                      ("Server", "cf-mitigated", "cf-ray", "x-amzn-waf-action", "x-cache", "Retry-After")}, data[:4000]))
        return data, kind.split(";")[0].strip().lower()


def fetch(url, accept="*/*", tries=3, pause=0.3):
    """Return (bytes, content type). Raises the last error after a few tries.

    A request that the server turns away (HTTP 403 and similar) is repeated in the
    next request style. The style that works for a host is remembered.
    """
    host = urllib.parse.urlsplit(url).netloc
    if strikes.get(host, 0) >= GIVE_UP_AFTER:
        raise Refused(url, 0, f"{host} turned away {GIVE_UP_AFTER} requests in a row in every request style; not asking again")
    first = accepted_style.get(host, 0)
    order = list(range(first, len(REQUEST_STYLES))) + list(range(0, first))
    last = None
    for position in order:
        style, agent = REQUEST_STYLES[position]
        getter = get_with_curl if style.startswith("curl") else get_with_python
        for attempt in range(tries):
            try:
                data, kind = getter(url, agent, accept)
                if accepted_style.get(host) != position:
                    accepted_style[host] = position
                    if position:
                        log(f"    ({host} accepts requests sent as: {style})")
                strikes[host] = 0
                time.sleep(pause)
                return data, kind
            except Refused as error:
                last = error
                if error.code not in REFUSED:
                    if error.code in (400, 401, 404, 410):
                        strikes[host] = 0      # the server answers us; this one file is not there
                        raise
                    break                      # curl missing, or an answer no retry will change
                if refusals_logged.get(host, 0) < len(REQUEST_STYLES) * 2:
                    refusals_logged[host] = refusals_logged.get(host, 0) + 1
                    log(f"    refused [{style}] {url[:110]}\n            {error}")
                if error.code in (429, 503) and attempt + 1 < tries:
                    time.sleep(4 * (attempt + 1))
                    continue
                break                          # try the next request style
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
                last = error
                time.sleep(1.5 * (attempt + 1))
    strikes[host] = strikes.get(host, 0) + 1
    raise last


def unescape_markup(text):
    """Addresses inside page source can be HTML-escaped or JSON-escaped."""
    text = html.unescape(text)
    return text.replace("\\/", "/").replace("\\u002F", "/").replace("\\u0026", "&")


def clean_file_name(url):
    name = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1])
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-.")
    name = re.sub(r"-+\.", ".", name)
    return name or "file"


def unique_path(folder, name, taken):
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    candidate, n = name, 2
    while candidate.lower() in taken:
        candidate = f"{stem}-{n}{dot}{ext}"
        n += 1
    taken.add(candidate.lower())
    return folder / candidate


# ---------------------------------------------------------------- pages

def save_pages(site, snapshot, offline):
    pages_dir = snapshot / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, address, _ in PAGES:
        target = pages_dir / f"{name}.html"
        if offline:
            if target.exists():
                result[name] = target.read_text(encoding="utf-8", errors="replace")
            continue
        try:
            data, _ = fetch(site + address, accept="text/html,*/*;q=0.8")
        except Exception as error:  # noqa: BLE001 - report and carry on with the other pages
            if target.exists() and target.stat().st_size > 2000:
                # A copy saved earlier, for example with the browser's "Save Page As".
                result[name] = target.read_text(encoding="utf-8", errors="replace")
                log(f"  using the saved copy of {address} ({target.stat().st_size / 1024:.0f} KB); "
                    f"the site did not answer from here: {str(error)[:60]}")
            else:
                log(f"  could not read {site + address}: {error}")
            continue
        target.write_bytes(data)
        result[name] = data.decode("utf-8", errors="replace")
        log(f"  saved {address:28s} {len(data) / 1024:7.0f} KB")
    return result


def body_of(page_source):
    start = page_source.lower().find("<body")
    return page_source[start:] if start >= 0 else page_source


# ---------------------------------------------------------------- PDFs and other files

def import_files(repo, page_sources, manifest, dry_run, earlier):
    wanted = {}  # address on Jimdo -> set of Markdown files that link to it
    for _, _, md_name in PAGES:
        md_path = repo / md_name
        if md_path.exists():
            for url in MARKDOWN_FILE_LINK.findall(md_path.read_text(encoding="utf-8")):
                wanted.setdefault(url, set()).add(md_name)
    in_markdown = set(wanted)
    for source in page_sources.values():
        for url in FILE_URL.findall(unescape_markup(body_of(source))):
            wanted.setdefault(url, set())

    taken = {"papers": set(), "files": set()}
    for folder in taken:
        directory = repo / "assets" / folder
        if directory.exists():
            taken[folder] = {p.name.lower() for p in directory.iterdir()}

    total = 0
    for url in sorted(set(wanted) | set(earlier)):
        if url in earlier and (repo / earlier[url]["to"].lstrip("/")).exists():
            manifest["files"].append(earlier[url])   # copied by an earlier run
            total += earlier[url].get("bytes", 0)
            if not dry_run:
                for md_name in wanted.get(url, ()):  # a link that was put back by hand
                    md_path = repo / md_name
                    md_path.write_text(md_path.read_text(encoding="utf-8").replace(url, earlier[url]["to"]), encoding="utf-8")
            continue
        if url not in wanted:
            continue
        folder = "files" if wanted[url] == {"about-me.md"} else "papers"
        directory = repo / "assets" / folder
        entry = {"from": url, "linked_in": sorted(wanted[url])}
        manifest["files"].append(entry)
        try:
            data, kind = fetch(url, accept="application/pdf,*/*;q=0.8")
        except Exception as error:  # noqa: BLE001
            entry["status"] = f"failed: {error}"
            log(f"  FAILED  {url}\n          {error}")
            continue
        entry["bytes"] = len(data)
        if not data:
            entry["status"] = "failed: empty file"
            log(f"  FAILED  {url} (empty file)")
            continue
        if url.lower().endswith(".pdf") and not data.lstrip()[:5].startswith(b"%PDF"):
            entry["status"] = f"failed: not a PDF (server sent {kind or 'unknown type'})"
            log(f"  FAILED  {url} (the server did not send a PDF)")
            continue
        if len(data) > GITHUB_FILE_LIMIT:
            entry["status"] = "too large for GitHub (over 95 MB); link left unchanged"
            log(f"  TOO BIG {url} ({len(data) / 1e6:.0f} MB). Link left pointing at Jimdo.")
            continue
        target = unique_path(directory, clean_file_name(url), taken[folder])
        local = "/" + target.relative_to(repo).as_posix()
        entry.update(status="ok", to=local)
        total += len(data)
        log(f"  ok {len(data) / 1e6:6.1f} MB  {local}")
        if dry_run:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        for md_name in wanted[url]:
            md_path = repo / md_name
            text = md_path.read_text(encoding="utf-8")
            md_path.write_text(text.replace(url, local), encoding="utf-8")
    not_linked = sorted(u for u in wanted if u not in in_markdown and u not in earlier)
    if not_linked:
        log(f"  Note: {len(not_linked)} file(s) are on the Jimdo pages but not linked in the new pages:")
        for url in not_linked:
            log(f"        {url}")
    manifest["files_total_bytes"] = total
    return total


# ---------------------------------------------------------------- pictures

def pictures_in_order(page_source):
    """Pictures of one page in the order they appear, one entry per picture.

    A picture usually occurs several times in a row in the page source (one
    address per screen size). Repeats that follow each other count as one.
    """
    body = unescape_markup(body_of(page_source))
    runs = []
    for match in IMAGE_URL.finditer(body):
        ident = IMAGE_ID.search(match.group(0))
        key = (ident.group(1), ident.group(2).lower(), ident.group(3).lower())
        if runs and runs[-1]["key"] == key:
            runs[-1]["seen"].append(match.group(0))
        else:
            runs.append({"key": key, "seen": [match.group(0)], "at": match.start()})
    return runs


def width_hint(url):
    found = re.search(r"width=(\d+)", url)
    return int(found.group(1)) if found else 0


PICTURE_BOX = 1600           # longest side of a stored picture, in pixels
HEAVY_PNG = 400 * 1024       # a PNG above this size is also requested as WebP
PICTURE_ACCEPT = "image/png,image/jpeg,image/gif,image/svg+xml,image/*;q=0.8"


def picture_address(run, options):
    site_no, file_id, ext = run["key"]
    return f"https://storage.e.jimdo.com/cdn-cgi/image/{options}/image/{site_no}/{file_id}.{ext}"


def jimdo_frame(run):
    """How Jimdo shows the picture: the crop ("trim", in pixels of the original:
    top;right;bottom;left) and the frame it is fitted into."""
    found = re.search(r"cdn-cgi/image/([^/]+)/image/", max(run["seen"], key=width_hint))
    frame = {}
    if found:
        for part in found.group(1).split(","):
            name, _, value = part.partition("=")
            if name in ("trim", "width", "height", "fit"):
                frame[name] = value
    return frame


def download_picture(run):
    """Return (bytes, file extension, address used).

    The picture is taken whole (not cropped) and scaled down to fit PICTURE_BOX,
    in its own format. Jimdo shows many pictures cropped to a frame. That crop is
    written to the manifest and left to the page design, so no part of a picture
    is lost. The full-size original is only used when nothing else works.
    """
    site_no, file_id, ext = run["key"]
    plain = f"https://storage.e.jimdo.com/image/{site_no}/{file_id}.{ext}"
    box = f"fit=scale-down,width={PICTURE_BOX},height={PICTURE_BOX}"
    sized = picture_address(run, "quality=85," + box)
    biggest_seen = max(run["seen"], key=width_hint)
    order = (plain, sized, biggest_seen) if ext in ("gif", "svg") else (sized, biggest_seen, plain)
    errors = []
    for url in order:
        try:
            data, kind = fetch(url, accept=PICTURE_ACCEPT)
        except Exception as error:  # noqa: BLE001
            errors.append(f"{url}: {error}")
            continue
        if not (kind.startswith("image/") and len(data) > 200):
            errors.append(f"{url}: not a picture ({kind or 'unknown type'}, {len(data)} bytes)")
            continue
        if kind == "image/png" and len(data) > HEAVY_PNG and url == sized:
            # A heavy PNG is usually a photo or a screenshot. WebP shows the same at a fraction of the size.
            lighter = picture_address(run, "quality=88,format=webp," + box)
            try:
                data_webp, kind_webp = fetch(lighter, accept="image/webp,image/*;q=0.5")
                if kind_webp == "image/webp" and 200 < len(data_webp) < 0.6 * len(data):
                    return data_webp, "webp", lighter
            except Exception:  # noqa: BLE001 - the PNG is kept
                pass
        return data, CONTENT_TYPES.get(kind, ext), url
    raise RuntimeError("; ".join(errors))


ICON_LINK = re.compile(r"<link\b[^>]*\brel=[\"'](?:shortcut )?icon[\"'][^>]*>", re.I)


def import_site_icon(repo, page_sources, manifest, dry_run):
    """The small picture browsers show in the tab (favicon), if the Jimdo site has its own."""
    for source in page_sources.values():
        for tag in ICON_LINK.findall(source[: source.lower().find("<body")] if "<body" in source.lower() else source):
            ident = IMAGE_ID.search(unescape_markup(tag))
            if not ident:
                continue
            run = {"key": (ident.group(1), ident.group(2).lower(), ident.group(3).lower()), "seen": []}
            url = picture_address(run, "quality=90,fit=cover,width=192,height=192")
            target_stem = repo / "assets" / "img" / "site-icon"
            existing = sorted(target_stem.parent.glob("site-icon.*")) if target_stem.parent.exists() else []
            if existing:
                manifest["site_icon"] = {"status": "already there", "to": "/" + existing[0].relative_to(repo).as_posix()}
                return
            try:
                data, kind = fetch(url, accept=PICTURE_ACCEPT)
            except Exception as error:  # noqa: BLE001
                manifest["site_icon"] = {"status": f"failed: {error}", "from": url}
                log(f"  site icon: FAILED {error}")
                return
            ext = CONTENT_TYPES.get(kind)
            if not ext or len(data) < 100:
                manifest["site_icon"] = {"status": f"failed: not a picture ({kind})", "from": url}
                return
            target = target_stem.with_suffix("." + ext)
            manifest["site_icon"] = {"status": "ok", "to": "/" + target.relative_to(repo).as_posix(), "from": url, "bytes": len(data)}
            log(f"  site icon saved as /{target.relative_to(repo).as_posix()} ({len(data) / 1024:.0f} KB)")
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            return


def import_pictures(repo, page_sources, manifest, dry_run):
    all_runs = {name: pictures_in_order(source) for name, source in page_sources.items()}
    # A picture that sits on every page (a logo in the page frame) is not page content.
    with_pictures = [name for name, runs in all_runs.items() if runs]
    site_wide = set()
    if len(page_sources) >= 4 and len(with_pictures) == len(page_sources):
        site_wide = set.intersection(*({run["key"] for run in all_runs[name]} for name in with_pictures))
    if site_wide:
        manifest["pictures_on_every_page"] = sorted("/".join(key[:2]) + "." + key[2] for key in site_wide)
        log(f"  left out {len(site_wide)} picture(s) that appear on every page (page frame, not content)")
    for name, _, md_name in PAGES:
        source = page_sources.get(name)
        md_path = repo / md_name
        if source is None or not md_path.exists():
            continue
        text = md_path.read_text(encoding="utf-8")
        slots = sorted(set(re.findall(r"IMPORT:" + re.escape(name) + r"-(\d{2})\b", text)))
        runs = [run for run in all_runs[name] if run["key"] not in site_wide]
        record = {"page": name, "slots_in_new_page": len(slots), "pictures_on_jimdo_page": len(runs), "pictures": []}
        manifest["pictures"].append(record)
        if not runs and not slots:
            continue
        directory = repo / "assets" / "img" / name
        saved = []
        for number, run in enumerate(runs, start=1):
            item = {"order": number, "id": "/".join(run["key"][:2]) + "." + run["key"][2], "jimdo_frame": jimdo_frame(run)}
            record["pictures"].append(item)
            existing = sorted(directory.glob(f"{number:02d}-{run['key'][1][:8]}.*")) if directory.exists() else []
            if existing:
                saved.append(existing[0])
                item.update(status="already there", to="/" + existing[0].relative_to(repo).as_posix())
                continue
            try:
                data, ext, used = download_picture(run)
            except Exception as error:  # noqa: BLE001
                item["status"] = f"failed: {error}"
                saved.append(None)
                log(f"  FAILED  picture {number} of page '{name}': {error}")
                continue
            target = directory / f"{number:02d}-{run['key'][1][:8]}.{ext}"
            item.update(status="ok", to="/" + target.relative_to(repo).as_posix(), bytes=len(data), fetched=used)
            saved.append(target)
            if not dry_run:
                directory.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        got = sum(1 for s in saved if s is not None)
        if len(runs) == len(slots) and got == len(runs) and slots == [f"{i:02d}" for i in range(1, len(runs) + 1)]:
            if not dry_run:
                for number, target in enumerate(saved, start=1):
                    token = f"IMPORT:{name}-{number:02d}"
                    text = text.replace(token, "/" + target.relative_to(repo).as_posix())
                md_path.write_text(text, encoding="utf-8")
            record["placed"] = True
            log(f"  {name:24s} {got:2d} pictures downloaded and placed")
        else:
            record["placed"] = False
            if slots:
                log(f"  {name:24s} {got:2d} of {len(runs)} pictures downloaded, NOT placed: "
                    f"the new page has {len(slots)} picture slots. Nothing changed on this page.")
            else:
                log(f"  {name:24s} {got:2d} of {len(runs)} pictures downloaded (the new page has no open slots)")


# ---------------------------------------------------------------- videos

def list_videos(page_sources, manifest):
    for name, _, _ in PAGES:
        source = page_sources.get(name)
        if source is None:
            continue
        body = unescape_markup(body_of(source))
        seen, ordered = set(), []
        for match in YOUTUBE_ID.finditer(body):
            video = match.group(1)
            if video not in seen:
                seen.add(video)
                around = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body[max(0, match.start() - 300): match.end() + 300]))
                ordered.append({"id": video, "near": around.strip()[:220]})
        manifest["videos"].append({"page": name, "videos": ordered})
        if ordered:
            log(f"  {name:24s} " + ", ".join(v["id"] for v in ordered))


# ---------------------------------------------------------------- text comparison

SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head", "nav", "header", "footer"}
BLOCK_TAGS = {
    "p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "section", "article", "br", "tr", "td", "th",
    "figcaption", "blockquote", "ul", "ol", "figure", "main", "aside", "button",
}
BOILERPLATE = (
    "content from youtube can t be displayed", "consent show", "cookie settings", "privacy policy",
    "imprint", "withdraw contract", "changed your mind", "read more",
)


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.current, self.skip = [], [], 0

    def flush(self):
        text = " ".join("".join(self.current).split())
        if text:
            self.blocks.append(text)
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
        if tag in BLOCK_TAGS:
            self.flush()

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1
        if tag in BLOCK_TAGS:
            self.flush()

    def handle_data(self, data):
        if not self.skip:
            self.current.append(data)


def words(text):
    """Lower-case words only: punctuation, quote style and spacing are ignored."""
    text = unicodedata.normalize("NFC", text).replace("­", "").lower()
    return re.findall(r"[^\W_]+", text, re.UNICODE)


def markdown_words(md_text):
    text = re.sub(r"\A---\n.*?\n---\n", "", md_text, flags=re.S)       # settings block
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)                  # notes
    text = re.sub(r"\{%.*?%\}", " ", text, flags=re.S)                   # video lines
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r" \1 ", text)              # pictures
    text = re.sub(r"\]\((?:[^()]|\([^()]*\))*\)", "] ", text)            # link targets
    text = re.sub(r"<(https?://[^>]+)>", r" \1 ", text)                  # bare links are visible text
    text = re.sub(r"<[^>]+>", " ", text)
    return words(text)


def front_matter_words(md_text):
    found = re.match(r"\A---\n(.*?)\n---\n", md_text, flags=re.S)
    if not found:
        return []
    values = re.findall(r"^\s*(?:-\s*)?(?:caption|role|place|label|title):\s*\"?(.*?)\"?\s*$", found.group(1), flags=re.M)
    return words(" ".join(values))


class LinkTargets(HTMLParser):
    """Addresses of the links in the page content (menu, header and footer left out)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.targets, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
        if tag == "a" and not self.skip:
            href = (dict(attrs).get("href") or "").strip()
            if href and not href.startswith(("#", "mailto:", "javascript:", "tel:")):
                self.targets.append(href)

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1


EXPIRED_LINK_HOSTS = ("watermark.silverchair.com", "watermark02.silverchair.com", "pdf.sciencedirectassets.com")


def missing_links(site, page_source, md_text, copied):
    """Link targets on the Jimdo page that the new page does not contain."""
    parser = LinkTargets()
    parser.feed(body_of(page_source))
    host = urllib.parse.urlsplit(site).netloc
    missing, expired = [], 0
    for href in dict.fromkeys(parser.targets):
        parts = urllib.parse.urlsplit(href)
        wrapped = re.search(r"urldefense\.com/v3/__(.+?)__;", href)
        if parts.netloc in EXPIRED_LINK_HOSTS:
            expired += 1                      # temporary download links, left out on purpose
            continue
        candidates = [href]
        if wrapped:
            candidates = [wrapped.group(1)]   # the address inside a mail-filter wrapper
        elif parts.netloc in ("", host):
            candidates = [parts.path or "/"]  # a link to another page of the site
        elif href in copied:
            candidates.append(copied[href])   # a PDF that now lives in this repository
        if not any(c in md_text for c in candidates):
            missing.append(href)
    return missing, expired


def compare_text(repo, page_sources, snapshot, site, copied):
    lines, problems = [], 0
    for name, address, md_name in PAGES:
        source = page_sources.get(name)
        md_path = repo / md_name
        if source is None or not md_path.exists():
            continue
        parser = VisibleText()
        parser.feed(body_of(source))
        parser.flush()
        md_text = md_path.read_text(encoding="utf-8")
        new_words = front_matter_words(md_text) + markdown_words(md_text)
        haystack = " " + " ".join(new_words) + " "
        missing = []
        for block in parser.blocks:
            block_words = words(block)
            joined = " ".join(block_words)
            if len(block_words) < 3 or any(joined.startswith(b) or joined == b for b in BOILERPLATE):
                continue
            if " " + joined + " " in haystack:
                continue
            # Not found as one piece: say how much of it is there, in runs of five words.
            grams = [" ".join(block_words[i:i + 5]) for i in range(max(1, len(block_words) - 4))]
            hit = sum(1 for g in grams if " " + g + " " in haystack)
            missing.append((hit / len(grams), block))
        lines.append(f"== {address}  ({len(parser.blocks)} text blocks on the Jimdo page, {len(missing)} not found word for word)")
        for share, block in missing:
            problems += 1
            lines.append(f"   [{share:4.0%} of it found]  {block[:400]}")
        lost_links, expired = missing_links(site, source, md_text, copied)
        lines.append(f"   link targets missing from the new page: {len(lost_links)}"
                     + (f"  (plus {expired} expired download links left out on purpose)" if expired else ""))
        for href in lost_links:
            problems += 1
            lines.append(f"   [link] {href[:300]}")
        lines.append("")
    report = snapshot / "text-check.txt"
    header = (
        "Text of each Jimdo page that does not appear word for word in the new page.\n"
        "Punctuation, quote style, upper and lower case, and link addresses are ignored.\n"
        "Menu and cookie-notice text is left out. A high share found usually means a repaired\n"
        "line break or hyphen. A low share means text is missing from the new page.\n"
        "Lines marked [link] are link addresses on the Jimdo page that the new page does not have.\n\n"
    )
    report.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return problems, report


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Copy pictures and PDFs from the Jimdo site into this repository.")
    parser.add_argument("--site", default=SITE, help="address of the Jimdo site (default: %(default)s)")
    parser.add_argument("--dry-run", action="store_true", help="download and report, but do not write into the site")
    parser.add_argument("--offline", action="store_true", help="reuse the saved page copies instead of reading the site again")
    parser.add_argument("--skip", default="", help="comma-separated steps to leave out: files, pictures, videos, text")
    args = parser.parse_args()
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}

    repo = Path(__file__).resolve().parent.parent
    if not (repo / "_config.yml").exists():
        sys.exit("Run this from the website repository (the folder that contains _config.yml).")
    snapshot = repo / "tools" / "jimdo-snapshot"
    snapshot.mkdir(parents=True, exist_ok=True)
    manifest = {"site": args.site, "files": [], "pictures": [], "videos": []}
    earlier = {}
    if (snapshot / "manifest.json").exists():
        try:
            previous = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
            earlier = {f["from"]: f for f in previous.get("files", []) if f.get("status") == "ok" and f.get("to")}
        except (ValueError, KeyError, TypeError):
            earlier = {}

    log(f"Import from {args.site}, {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}, Python {sys.version.split()[0]}"
        + (", on GitHub" if os.environ.get("GITHUB_ACTIONS") else ""))
    log("1. Saving a copy of each Jimdo page")
    page_sources = save_pages(args.site.rstrip("/"), snapshot, args.offline)
    if not page_sources:
        # Jimdo's servers turn away some networks (GitHub's among them). The PDFs sit on a
        # different server and their addresses are in the Markdown pages, so they can
        # still be copied. Pictures, videos and the text check need the page copies.
        log("\nNo page could be read from here, and no saved copies are in tools/jimdo-snapshot/pages/.")
        log("Continuing with the PDFs only. Pictures, videos and the text check are left out.")
        skip |= {"pictures", "videos", "text"}

    if "files" not in skip:
        log("\n2. PDFs and other files")
        total = import_files(repo, page_sources, manifest, args.dry_run, earlier)
        log(f"  total {total / 1e6:.0f} MB")
    if "pictures" not in skip:
        log("\n3. Pictures")
        import_pictures(repo, page_sources, manifest, args.dry_run)
        import_site_icon(repo, page_sources, manifest, args.dry_run)
    if "videos" not in skip:
        log("\n4. YouTube videos found on each page (for the open video slots)")
        list_videos(page_sources, manifest)
    if "text" not in skip:
        log("\n5. Comparing the text of the old and new pages")
        copied = {f["from"]: f["to"] for f in manifest["files"] if f.get("status") == "ok" and f.get("to")}
        problems, report = compare_text(repo, page_sources, snapshot, args.site.rstrip("/"), copied)
        log(f"  {problems} difference(s) in text or link targets. Details: {report.relative_to(repo)}")

    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    failed = [f for f in manifest["files"] if not str(f.get("status", "")).startswith("ok")]
    unplaced = [p["page"] for p in manifest["pictures"] if p.get("placed") is False and p["slots_in_new_page"]]
    log("\nDone.")
    log(f"  files copied:   {len(manifest['files']) - len(failed)} of {len(manifest['files'])}")
    log(f"  pictures:       " + ", ".join(f"{p['page']} {len(p['pictures'])}" for p in manifest["pictures"] if p["pictures"]))
    if failed:
        log(f"  {len(failed)} file(s) could not be copied. Their links still point at Jimdo.")
    if unplaced:
        log("  pictures downloaded but not placed on: " + ", ".join(unplaced))
    remaining = []
    for _, _, md_name in PAGES:
        md_path = repo / md_name
        if md_path.exists():
            remaining += re.findall(r"IMPORT:[A-Za-z0-9-]+", md_path.read_text(encoding="utf-8"))
    if remaining:
        log(f"  open slots left: {len(remaining)} ({', '.join(sorted(set(remaining))[:8])}{' ...' if len(set(remaining)) > 8 else ''})")
    log("  A full record is in tools/jimdo-snapshot/manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
