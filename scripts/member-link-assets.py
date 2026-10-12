#!/usr/bin/env python3
"""member-links.html의 PROJECTS에서 서비스 주소를 읽어 링크 미리보기 이미지와 파비콘을 갱신한다.

사용법: python3 scripts/member-link-assets.py [code ...]
  - 인자가 없으면 모든 프로젝트를 갱신한다.
  - 미리보기: assets/member-links/previews/<code>.jpg (사이트의 og:image, 링크 공유 시 보이는 이미지)
  - 파비콘: assets/member-links/favicons/<code>.<ext>
  - og:image가 없는 사이트는 미리보기를 지우고, 카드에서 파비콘으로 대신한다.
  - 사이트의 og:description(없으면 description)을 함께 출력하니 PROJECTS의 description에 옮겨 적는다.
"""

import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "member-links.html"
PREVIEW_DIR = ROOT / "assets/member-links/previews"
FAVICON_DIR = ROOT / "assets/member-links/favicons"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def read_projects():
    source = PAGE.read_text(encoding="utf-8")
    pattern = re.compile(r'code:\s*"([^"]+)".*?service:\s*"([^"]+)"', re.S)
    return pattern.findall(source)


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.geturl(), response.headers.get_content_type(), response.read()


class HeadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.icons = []
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        rel = (attrs.get("rel") or "").lower()
        if tag == "link" and "icon" in rel and attrs.get("href"):
            self.icons.append((attrs.get("type") or "", attrs["href"]))
        key = attrs.get("property") or attrs.get("name")
        if tag == "meta" and key and attrs.get("content"):
            self.meta.setdefault(key.lower(), attrs["content"])


def read_head(service):
    try:
        final_url, _, body = fetch(service)
    except Exception:
        # 비공개 GitHub 저장소처럼 페이지를 못 읽으면 도메인 기본 파비콘만 시도한다.
        return service, HeadParser()
    parser = HeadParser()
    parser.feed(body.decode("utf-8", "ignore"))
    return final_url, parser


EXTENSIONS = {
    "image/svg+xml": "svg",
    "image/png": "png",
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}


def save_favicon(code, base_url, head):
    # svg > png > 기타 순으로 시도하고, 마지막에 /favicon.ico
    order = {"svg": 0, "png": 1}
    icons = sorted(head.icons, key=lambda icon: min(
        [rank for kind, rank in order.items() if kind in icon[0] or icon[1].split("?")[0].endswith(kind)] or [2]
    ))
    urls = [urllib.parse.urljoin(base_url, href) for _, href in icons]
    urls.append(urllib.parse.urljoin(base_url, "/favicon.ico"))
    for url in urls:
        try:
            _, content_type, data = fetch(url)
        except Exception:
            continue
        extension = EXTENSIONS.get(content_type) or url.split("?")[0].rsplit(".", 1)[-1].lower()
        if extension not in EXTENSIONS.values() or not data:
            continue
        for old in FAVICON_DIR.glob(f"{code}.*"):
            old.unlink()
        target = FAVICON_DIR / f"{code}.{extension}"
        target.write_bytes(data)
        return target
    return None


def save_preview(code, base_url, head):
    target = PREVIEW_DIR / f"{code}.jpg"
    image = head.meta.get("og:image") or head.meta.get("twitter:image")
    try:
        _, content_type, data = fetch(urllib.parse.urljoin(base_url, image)) if image else (None, "", b"")
    except Exception:
        content_type, data = "", b""
    if not content_type.startswith("image/"):
        # og:image가 없거나 깨진 주소면 링크 공유 때도 이미지가 안 보이므로 미리보기를 두지 않는다.
        target.unlink(missing_ok=True)
        return None
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "og"
        source.write_bytes(data)
        subprocess.run(
            ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "80", "--resampleWidth", "800", str(source), "--out", str(target)],
            check=True,
            capture_output=True,
        )
    return target


def main():
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    FAVICON_DIR.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])
    for code, service in read_projects():
        if only and code not in only:
            continue
        base_url, head = read_head(service)
        favicon = save_favicon(code, base_url, head)
        preview = save_preview(code, base_url, head)
        description = head.meta.get("og:description") or head.meta.get("description") or ""
        print(f"{code:10} favicon={favicon.name if favicon else '-'} preview={preview.name if preview else '-'}")
        print(f"{'':10} description={description}")


if __name__ == "__main__":
    main()
