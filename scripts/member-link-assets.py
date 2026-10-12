#!/usr/bin/env python3
"""member-links.html의 PROJECTS에서 서비스 주소를 읽어 미리보기와 파비콘을 갱신한다.

사용법: python3 scripts/member-link-assets.py [code ...]
  - 인자가 없으면 모든 프로젝트를 갱신한다.
  - 미리보기: assets/member-links/previews/<code>.jpg (Chrome 헤드리스 스크린샷, 로그인 없는 상태)
  - 파비콘: assets/member-links/favicons/<code>.<ext>
  - GitHub 주소만 있는 프로젝트는 미리보기를 만들지 않는다.
"""

import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "member-links.html"
PREVIEW_DIR = ROOT / "assets/member-links/previews"
FAVICON_DIR = ROOT / "assets/member-links/favicons"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def read_projects():
    source = PAGE.read_text(encoding="utf-8")
    pattern = re.compile(r'code:\s*"([^"]+)".*?service:\s*"([^"]+)"', re.S)
    return pattern.findall(source)


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.geturl(), response.headers.get_content_type(), response.read()


class IconParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.icons = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        rel = (attrs.get("rel") or "").lower()
        if tag == "link" and "icon" in rel and attrs.get("href"):
            self.icons.append((rel, attrs.get("type") or "", attrs["href"]))


def favicon_candidates(service):
    try:
        final_url, _, body = fetch(service)
    except Exception:
        # 비공개 GitHub 저장소처럼 페이지를 못 읽으면 도메인 기본 파비콘만 시도한다.
        return [urllib.parse.urljoin(service, "/favicon.ico")]
    parser = IconParser()
    parser.feed(body.decode("utf-8", "ignore"))
    # svg > png > 기타 순으로 시도하고, 마지막에 /favicon.ico
    order = {"svg": 0, "png": 1}
    icons = sorted(parser.icons, key=lambda icon: min(
        [rank for kind, rank in order.items() if kind in icon[1] or icon[2].split("?")[0].endswith(kind)] or [2]
    ))
    urls = [urllib.parse.urljoin(final_url, href) for _, _, href in icons]
    urls.append(urllib.parse.urljoin(final_url, "/favicon.ico"))
    return urls


EXTENSIONS = {
    "image/svg+xml": "svg",
    "image/png": "png",
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}


def save_favicon(code, service):
    for url in favicon_candidates(service):
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


def save_preview(code, service):
    target = PREVIEW_DIR / f"{code}.jpg"
    with tempfile.TemporaryDirectory() as tmp:
        shot = Path(tmp) / "shot.png"
        # macOS 헤드리스 Chrome은 스크린샷을 저장한 뒤에도 종료되지 않아서, 파일이 생기면 직접 끝낸다.
        chrome = subprocess.Popen(
            [
                CHROME,
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                "--no-first-run",
                "--force-device-scale-factor=1",
                "--window-size=1280,800",
                "--virtual-time-budget=6000",
                f"--user-data-dir={tmp}/profile",
                f"--screenshot={shot}",
                service,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(120):
                if shot.exists() and shot.stat().st_size > 0:
                    time.sleep(0.5)
                    break
                time.sleep(0.5)
        finally:
            chrome.kill()
            chrome.wait()
        if not shot.exists():
            return None
        subprocess.run(
            ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "72", "--resampleWidth", "640", str(shot), "--out", str(target)],
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
        favicon = save_favicon(code, service)
        preview = None if "github.com" in service else save_preview(code, service)
        print(f"{code:10} favicon={favicon.name if favicon else '-'} preview={preview.name if preview else '-'}")


if __name__ == "__main__":
    main()
