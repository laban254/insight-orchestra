#!/usr/bin/env python3
"""Record the Insight Orchestra agent pipeline as a demo video.

Drives a real browser against a running instance and captures the whole run --
picking a demo dataset, the four agents streaming their progress, and the charts
landing on the canvas -- then post-processes the capture into an MP4 for the web
and a GIF for the README.

The pipeline needs a working LLM provider. Check before recording:

    curl -s localhost:8000/config | python3 -m json.tool

If every entry under "ready" is false the run will fail fast rather than record
a video of an error banner.

Usage:
    ./scripts/record_demo.py                          # Sales dataset, ~30s
    ./scripts/record_demo.py --dataset Customers
    ./scripts/record_demo.py --target-seconds 25
    ./scripts/record_demo.py --headed --no-post       # watch it, skip ffmpeg
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - dependency hint
    sys.exit("playwright is not installed. Run: pip install playwright && playwright install chromium")


REPO_ROOT = Path(__file__).resolve().parent.parent

# A soft pointer drawn into the page, since Playwright's recorder does not
# capture the real cursor -- without it clicks look like they happen by magic.
CURSOR_SCRIPT = """
() => {
  const dot = document.createElement('div');
  dot.id = '__demo_cursor';
  Object.assign(dot.style, {
    position: 'fixed', top: '0', left: '0', width: '22px', height: '22px',
    borderRadius: '50%', pointerEvents: 'none', zIndex: '2147483647',
    background: 'radial-gradient(circle at 35% 35%, rgba(255,255,255,.95), rgba(120,220,255,.55) 45%, rgba(120,220,255,0) 70%)',
    boxShadow: '0 0 14px 4px rgba(120,220,255,.45)',
    transform: 'translate(-50%,-50%) scale(1)',
    transition: 'transform .12s ease-out, opacity .2s linear',
    opacity: '0',
  });
  document.body.appendChild(dot);
  window.__demoCursor = {
    move(x, y) { dot.style.opacity = '1'; dot.style.left = x + 'px'; dot.style.top = y + 'px'; },
    press() { dot.style.transform = 'translate(-50%,-50%) scale(.6)'; },
    release() { dot.style.transform = 'translate(-50%,-50%) scale(1)'; },
    hide() { dot.style.opacity = '0'; },
  };
}
"""


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def preflight(api_url: str, allow_degraded: bool = False) -> None:
    """Fail before recording if no LLM provider can serve the pipeline."""
    try:
        with urllib.request.urlopen(f"{api_url}/config", timeout=5) as resp:
            cfg = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        sys.exit(f"Could not reach the backend at {api_url}: {exc}")

    ready = cfg.get("ready", {})
    provider = cfg.get("provider")
    if not ready.get(provider, False):
        usable = [name for name, ok in ready.items() if ok]
        hint = (
            f"Other providers are ready: {', '.join(usable)}. Switch with POST /config."
            if usable
            else "No provider is ready -- add an API key to .env, or run `ollama serve` "
            "and `ollama pull <model>` for a local one, then restart the backend."
        )
        if not allow_degraded:
            sys.exit(f"Provider '{provider}' is not ready, so the pipeline cannot run.\n{hint}")
        log(f"WARNING: provider '{provider}' is not ready -- recording a preview only.")
        return

    log(f"provider ready: {provider} ({cfg.get('model')})")


def click_with_cursor(page, locator) -> None:
    """Click, but move the on-screen cursor there first so the video reads."""
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    if box:
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        page.evaluate("([x, y]) => window.__demoCursor?.move(x, y)", [cx, cy])
        page.mouse.move(cx, cy)
        page.wait_for_timeout(450)
        page.evaluate("() => window.__demoCursor?.press()")
        page.wait_for_timeout(120)
    locator.click()
    page.evaluate("() => window.__demoCursor?.release()")


# Plotly mounts its container a beat before it paints any geometry, and the app
# fades the canvas in on top of that. Waiting only for `.js-plotly-plot` lands
# the camera on an empty grey box, so wait for a drawn trace in every chart.
CHARTS_PAINTED = """
() => {
  const plots = [...document.querySelectorAll('.js-plotly-plot')];
  if (!plots.length) return false;
  return plots.every((p) => p.querySelector('.main-svg') && p.querySelectorAll('.trace').length > 0);
}
"""


def wait_for_pipeline(page, timeout_s: int, allow_degraded: bool = False) -> None:
    """Block until the charts have actually painted, or bail out on error."""
    chart = page.locator(".js-plotly-plot")
    error = page.get_by_text("Could not complete analysis", exact=False)
    degraded = page.get_by_text("these results were not interpreted", exact=False)
    started = time.monotonic()
    deadline = started + timeout_s
    warned = False

    while time.monotonic() < deadline:
        if error.count() > 0:
            detail = error.first.inner_text().strip()
            sys.exit(f"The pipeline failed, so there is nothing worth recording:\n  {detail}")
        if degraded.count() > 0:
            if not allow_degraded:
                sys.exit(
                    "The pipeline fell back to statistics only -- the LLM call was refused or\n"
                    "  unreachable, so confidence and business-value scores read 'not assessed'.\n"
                    "  That is not a demo worth shipping. Fix the provider and re-run."
                )
            if not warned:
                log("WARNING: degraded run -- charts are real, insight text is not interpreted.")
                warned = True
        if chart.count() > 0:
            break
        page.wait_for_timeout(500)
    else:
        sys.exit(f"No chart appeared within {timeout_s}s. Re-run with --headed to watch what happened.")

    page.wait_for_function(CHARTS_PAINTED, timeout=30_000)
    log(f"charts painted after {time.monotonic() - started:.0f}s")


def wait_for_settle(page, max_s: int = 30) -> None:
    """Let the streaming narrative finish.

    The summariser keeps typing after the first chart paints, and later charts
    mount as skeletons while it does. Scrolling during that window films
    half-drawn placeholders, so hold until the page stops changing.
    """
    last, stable = None, 0
    deadline = time.monotonic() + max_s
    while time.monotonic() < deadline:
        size = page.evaluate("() => document.body.innerText.length")
        if size == last:
            stable += 1
            if stable >= 3:
                log("narrative settled")
                return
        else:
            stable, last = 0, size
        page.wait_for_timeout(700)
    log("narrative still streaming; continuing anyway")


def record(args) -> Path:
    raw_dir = Path(tempfile.mkdtemp(prefix="io-demo-"))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        context = browser.new_context(
            viewport={"width": args.width, "height": args.height},
            record_video_dir=str(raw_dir),
            record_video_size={"width": args.width, "height": args.height},
            # A fresh context means no restored workspace from a previous run.
            storage_state=None,
        )
        page = context.new_page()

        log(f"opening {args.url}")
        page.goto(args.url, wait_until="networkidle", timeout=60_000)
        page.evaluate(CURSOR_SCRIPT)

        picker = page.get_by_role("button", name="Select a demo dataset")
        picker.wait_for(state="visible", timeout=30_000)
        page.wait_for_timeout(1_200)  # let the opening frame breathe

        log("opening the dataset picker")
        click_with_cursor(page, picker)

        options = page.locator("#demo-dataset-list [role='option']")
        options.first.wait_for(state="visible", timeout=10_000)

        target = page.locator(
            f"#demo-dataset-list [role='option']:has-text('{args.dataset}')"
        ).first
        if target.count() == 0:
            log(f"no dataset matching {args.dataset!r}; using the first one")
            target = options.first

        page.wait_for_timeout(700)
        log(f"selecting dataset: {target.inner_text().splitlines()[0]}")
        click_with_cursor(page, target)

        page.evaluate("() => window.__demoCursor?.hide()")
        log("pipeline running -- capturing agent stream")
        wait_for_pipeline(page, args.pipeline_timeout, getattr(args, "allow_degraded", False))

        # Let everything finish drawing, then frame the charts and end there --
        # they are the payoff, so the last thing on screen should not be a table.
        wait_for_settle(page)
        page.wait_for_function(CHARTS_PAINTED, timeout=30_000)
        page.wait_for_timeout(2_000)

        charts = page.locator(".js-plotly-plot")
        charts.first.scroll_into_view_if_needed()
        page.wait_for_timeout(3_000)
        for _ in range(3):
            page.mouse.wheel(0, 200)
            page.wait_for_timeout(900)
        page.wait_for_timeout(2_500)

        video = page.video
        context.close()  # finalizes the file
        browser.close()

        if video is None:
            sys.exit("Playwright produced no video.")
        return Path(video.path())


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def post_process(raw: Path, out_dir: Path, target_s: float, gif_width: int) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4 = out_dir / "demo.mp4"
    gif = out_dir / "demo.gif"

    duration = probe_duration(raw)
    # Compress dead time, but never so much that the pipeline is a blur.
    speed = max(1.0, min(duration / target_s, 4.0))
    log(f"raw capture {duration:.1f}s -> {duration / speed:.1f}s (speed x{speed:.2f})")

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
         "-vf", f"setpts=PTS/{speed:.4f},scale=1280:-2:flags=lanczos",
         "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "23",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)],
        check=True,
    )

    # 12fps at 128 colours keeps a 30s capture near 6MB; GitHub gets slow past ~10MB.
    palette = out_dir / "_palette.png"
    gif_filters = f"setpts=PTS/{speed:.4f},fps=12,scale={gif_width}:-1:flags=lanczos"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
         "-vf", f"{gif_filters},palettegen=stats_mode=diff:max_colors=128", str(palette)],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-i", str(palette),
         "-lavfi", f"{gif_filters}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
         str(gif)],
        check=True,
    )
    palette.unlink(missing_ok=True)
    return mp4, gif


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://localhost:8501", help="running frontend")
    p.add_argument("--api-url", default="http://localhost:8000", help="running backend")
    p.add_argument("--dataset", default="Sales", help="demo dataset to pick, by visible name")
    p.add_argument("--out", default=str(REPO_ROOT / "docs" / "assets"), help="output directory")
    p.add_argument("--target-seconds", type=float, default=30.0, help="desired final length")
    p.add_argument("--pipeline-timeout", type=int, default=300, help="seconds to wait for charts")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=800)
    p.add_argument("--gif-width", type=int, default=800)
    p.add_argument("--headed", action="store_true", help="show the browser while recording")
    p.add_argument("--no-post", action="store_true", help="keep the raw webm, skip ffmpeg")
    p.add_argument(
        "--allow-degraded",
        action="store_true",
        help="record even with no working LLM. Framing and pacing are representative, "
        "but the insight text is not interpreted -- preview use only, never ship it.",
    )
    args = p.parse_args()

    if not args.no_post and not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is required for post-processing (or pass --no-post).")

    print("Insight Orchestra -- demo recorder")
    preflight(args.api_url, args.allow_degraded)

    raw = record(args)
    log(f"raw capture: {raw}")

    if args.no_post:
        print(f"\nDone. Raw video: {raw}")
        return

    mp4, gif = post_process(raw, Path(args.out), args.target_seconds, args.gif_width)
    shutil.rmtree(raw.parent, ignore_errors=True)

    print("\nDone.")
    print(f"  MP4 (site):   {mp4}  ({mp4.stat().st_size / 1e6:.1f} MB)")
    print(f"  GIF (README): {gif}  ({gif.stat().st_size / 1e6:.1f} MB)")
    if gif.stat().st_size > 10e6:
        print("  Note: GitHub renders GIFs over ~10MB slowly -- consider --gif-width 800.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nInterrupted.")
    except (PlaywrightTimeout, PlaywrightError) as exc:
        sys.exit(f"Browser automation failed: {exc}")
