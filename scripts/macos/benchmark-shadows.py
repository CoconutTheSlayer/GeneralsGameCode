#!/usr/bin/env python3
"""Alternate old/new shadow uploads in seeded battles; keep screenshots out of timings."""
import argparse
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import time


def run(args, units, mode, repeat):
    out = args.output / f"{units * 2}-units-{mode}-{repeat}"
    out.mkdir(parents=True, exist_ok=True)
    battle = out / "battle.txt"
    battle.write_text("map Tournament Desert\ncash 10000\nseed 5\nsuperweapons 0\n"
                      "player human FactionAmerica 0 0\nplayer easy FactionChina 1 2\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GENERALS_", "D3D8METAL_"))}
    env.update(GENERALS_ZH_PATH=str(args.game_data), GENERALS_PATH=str(args.base_data),
               GENERALS_NO_MESSAGEBOX="1", GENERALS_FPS_LOG="1", GENERALS_SHADOW_STATS="1",
               GENERALS_DYNAMIC_SHADOW_STREAM="1" if mode == "reuse" else "0",
               GENERALS_BATTLE_TEST=f"AmericaTankCrusader:ChinaTankBattleMaster:{units}",
               GENERALS_LOOKAT="0.5,0.5,1000", SDL_MAC_BACKGROUND_APP="1",
               SDL_WINDOW_ACTIVATE_WHEN_SHOWN="0")
    if args.verify:
        env.update(GENERALS_CRC_LOG="1", D3D8METAL_SCREENSHOT=str(out / "frame"),
                   D3D8METAL_SCREENSHOT_EVERY="600")
        if mode == "reuse":
            env["GENERALS_VERIFY_SHADOW_STREAM"] = "1"
    log = out / "native.log"
    start = time.monotonic()
    reached_end = False
    with log.open("w") as output:
        process = subprocess.Popen([str(args.binary), "-win", "-xres", "1280", "-yres", "800",
                                    "-noaudio", "-noFPSLimit", "-battle", str(battle)],
                                   cwd=args.game_data, env=env, stdout=output, stderr=output)
        try:
            while process.poll() is None and time.monotonic() - start < args.timeout:
                text = log.read_text(errors="replace")
                frames = re.findall(r"FPS .*logic frame (\d+)", text)
                if frames and int(frames[-1]) >= args.frames:
                    reached_end = True
                    break
                time.sleep(0.25)
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    text = log.read_text(errors="replace")
    fps = [{"fps": float(a), "particles": int(b), "logic_frame": int(c), "cpu_ms": float(d)}
           for a, b, c, d in re.findall(r"FPS ([\d.]+) particles (\d+) logic frame (\d+) cpu ([\d.]+) ms", text)
           if 180 <= int(c) <= args.frames]
    shadows = [{"frames": int(a), "logic_frame": int(b), "cpu_ms": float(c),
                "uploads": int(d), "reused": int(e), "bytes": int(f), "verified": int(g), "errors": int(h)}
               for a, b, c, d, e, f, g, h in re.findall(
                   r"SHADOW_STATS frames (\d+) logic (\d+) cpu_ms ([\d.]+) uploads (\d+) reused (\d+) bytes (\d+) verified (\d+) errors (\d+)", text)
               if 180 <= int(b) <= args.frames]
    result = dict(units_per_side=units, mode=mode, repeat=repeat, reached_end=reached_end,
                  verification=args.verify, exit_code=process.returncode, fps_samples=fps, shadow_samples=shadows,
                  spawned=re.findall(r"BATTLE_TEST spawned (\d+) .* vs (\d+) ", text),
                  verification_failed="SHADOW_VERIFY mismatch" in text or any(s["errors"] for s in shadows))
    if fps and shadows:
        result.update(median_game_cpu_ms=statistics.median(x["cpu_ms"] for x in fps),
                      median_shadow_cpu_ms=statistics.median(x["cpu_ms"] for x in shadows),
                      median_fps=statistics.median(x["fps"] for x in fps))
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if not k.endswith("samples")}), flush=True)
    if not reached_end or not fps or not shadows or result["verification_failed"] or result["spawned"] != [(str(units), str(units))]:
        raise RuntimeError(f"Incomplete or failed battle test: {log}")
    return result


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=root / "build/macos/GeneralsMD/generalszh")
    parser.add_argument("--game-data", type=Path, required=True)
    parser.add_argument("--base-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--units", type=int, nargs="+", default=[150, 300], help="units per army")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--frames", type=int, default=600, help="simulation frame at which to stop")
    parser.add_argument("--timeout", type=int, default=120, help="maximum seconds per run")
    parser.add_argument("--verify", action="store_true", help="validate geometry and capture images; do not use these timings")
    args = parser.parse_args()
    for name in ("binary", "game_data", "base_data", "output"):
        setattr(args, name, getattr(args, name).resolve())
    if args.rounds < 1 or args.frames < 300 or any(n < 1 or n > 1000 for n in args.units):
        parser.error("Use at least one round, 300 frames, and 1..1000 units per army")
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for units in args.units:
        for repeat in range(args.rounds):
            for mode in (["legacy", "reuse"] if repeat % 2 == 0 else ["reuse", "legacy"]):
                results.append(run(args, units, mode, repeat))
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
