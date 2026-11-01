"""Build standalone bot with embedded Mini App and offline geographic data."""
import base64
import json
from pathlib import Path
import zlib

import geonamescache
from game import Atlas

ROOT = Path(__file__).parent


def build():
    atlas = Atlas()
    raw = geonamescache.GeonamesCache().get_cities()
    known = {c.id: c for matches in atlas.by_name.values() for c in matches}
    payload = []
    for c in known.values():
        payload.append(dict(id=c.id, n=atlas.preferred.get(c.id, c.english_name), en=c.english_name,
                            country=c.country, cc=raw[c.id]["countrycode"], p=c.population,
                            lat=c.latitude, lon=c.longitude, a=list(c.aliases), bot=c.id in atlas.preferred))
    files = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "web").iterdir()
             if p.suffix in {".html", ".css", ".js"}}
    files["cities.json"] = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    web = ROOT / "docs"
    web.mkdir(exist_ok=True)
    for name, content in files.items():
        (web / name).write_text(content, encoding="utf-8")
    (web / ".nojekyll").write_text("", encoding="utf-8")
    packed = base64.b85encode(zlib.compress(json.dumps(files, ensure_ascii=False).encode(), 9)).decode()
    sources = []
    for name in ("game.py", "wiki.py", "bot.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        text = "\n".join(line for line in text.splitlines() if not line.startswith(("from game import", "from wiki import")))
        if name == "bot.py":
            text = text.rsplit('if __name__ == "__main__":', 1)[0]
        sources.append(text)
    loader = '''

def export_web(directory):
    import base64, json, zlib
    folder = Path(directory).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    files = json.loads(zlib.decompress(base64.b85decode(EMBEDDED_WEB)).decode())
    for name, content in files.items():
        (folder / name).write_text(content, encoding="utf-8")
    (folder / ".nojekyll").touch()
    print("Mini App exported to:", folder)
    return folder


def cli():
    import argparse
    parser = argparse.ArgumentParser(description="Cities: Telegram bot + Mini App, single Python file")
    parser.add_argument("--export-web", metavar="DIRECTORY", help="Export Mini App for HTTPS hosting")
    parser.add_argument("--serve", action="store_true", help="Preview Mini App on localhost")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if args.export_web or args.serve:
        folder = export_web(args.export_web or Path(__file__).with_name("miniapp"))
        if args.serve:
            from functools import partial
            from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
            print(f"Preview: http://127.0.0.1:{args.port}")
            try:
                ThreadingHTTPServer(("127.0.0.1", args.port), partial(SimpleHTTPRequestHandler, directory=str(folder))).serve_forever()
            except KeyboardInterrupt:
                pass
    else:
        main()


if __name__ == "__main__":
    cli()
'''
    result = '#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n# Install dependencies from requirements.txt; set TELEGRAM_BOT_TOKEN and MINI_APP_URL.\n'
    result += "\n\n".join(sources) + "\nEMBEDDED_WEB = " + repr(packed) + "\n" + loader
    (ROOT / "CitiesBot_AllInOne.py").write_text(result, encoding="utf-8")
    print(f"Built standalone bot, {len(payload)} cities, {len(atlas.cities)} bot answers; exported docs/.")


if __name__ == "__main__":
    build()
