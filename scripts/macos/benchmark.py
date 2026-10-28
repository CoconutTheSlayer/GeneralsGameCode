#!/usr/bin/env python3
"""Repeatable native CPU/GPU battle benchmarks, JSON summaries and browser-readable reports."""
import argparse
import collections
import copy
import hashlib
import html
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
ROSTERS = {"armor": ("AmericaTankCrusader", "ChinaTankBattleMaster"),
           "infantry": ("AmericaInfantryRanger", "ChinaInfantryRedguard")}


def percentile(values, p):
    """Linear interpolation, including singleton samples; no rounded FPS averages."""
    values = sorted(values)
    if not values:
        return None
    index = (len(values) - 1) * p / 100
    lo, hi = math.floor(index), math.ceil(index)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def distribution(values):
    return dict(mean=statistics.mean(values), p50=percentile(values, 50),
                p95=percentile(values, 95), p99=percentile(values, 99), maximum=max(values)) if values else None


def load_events(path):
    events = []
    with Path(path).open() as source:
        for line_number, line in enumerate(source, 1):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"Incomplete profile at {path}:{line_number}") from error
    return events


def summarize(events, warmup, end):
    frames = [e for e in events if e["kind"] == "frame" and e["thread"] == "main" and warmup <= e["logic"] < end]
    if not frames:
        raise ValueError("No main frames in the requested simulation interval")
    by_id = {e["frame"]: e for e in frames}
    if len(by_id) != len(frames):
        raise ValueError("Duplicate frame IDs")
    selected = [e for e in events if e.get("frame") in by_id and e["kind"] in ("frame", "scope", "gpu", "counter")]
    scopes, gpu, counters = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    for e in selected:
        key = (e["thread"], e["name"])
        if e["kind"] == "scope":
            scopes[key].append(e)
        elif e["kind"] == "gpu":
            gpu[e["name"]].append(e)
        elif e["kind"] == "counter":
            counters[key].append(e)
    n = len(frames)
    def per_frame(rows, field):
        values = collections.defaultdict(float)
        for e in rows:
            values[e["frame"]] += e[field] / 1000
        return [values[i] for i in by_id]
    cpu = []
    for (thread, name), rows in scopes.items():
        cpu.append(dict(thread=thread, name=name, calls=len(rows),
                        wall_ms=distribution(per_frame(rows, "wall_us")),
                        cpu_ms=distribution(per_frame(rows, "cpu_us")),
                        self_cpu_ms=distribution(per_frame(rows, "self_cpu_us"))))
    cpu.sort(key=lambda e: e["self_cpu_ms"]["mean"], reverse=True)
    # GPU encoder intervals may overlap (vertex/fragment pipelining). Command-buffer times
    # are kept separate: adding pass times or CPU+GPU times is not a frame cost.
    pass_ids = {e["frame"] for e in selected if e["kind"] == "gpu" and e["name"].startswith("pass:")}
    gpu_rows = []
    for name, rows in gpu.items():
        values = collections.defaultdict(float)
        for e in rows: values[e["frame"]] += e["wall_us"] / 1000
        ids = pass_ids if name.startswith("pass:") else by_id
        gpu_rows.append(dict(name=name, calls=len(rows), measured_frames=len(ids),
                             per_frame_ms=distribution([values[i] for i in ids])))
    gpu_rows.sort(key=lambda e: e["per_frame_ms"]["mean"], reverse=True)
    gpu_ids = {e["frame"] for e in selected if e["kind"] == "gpu" and e["name"] == "command: render"}
    frames.sort(key=lambda e: e["frame"])
    # Start-to-start intervals include the recorder handoff and loop housekeeping.
    frame_ms = [(frames[i+1]["start_us"] - e["start_us"]) / 1000 if i+1 < n else e["wall_us"] / 1000
                for i,e in enumerate(frames)]
    if any(v <= 0 for v in frame_ms): raise ValueError("Non-monotonic frame timestamps")
    renderer = [e for e in selected if e["kind"] == "frame" and e["thread"] == "renderer"]
    issues = [e["name"] for e in events if e["kind"] == "info" and any(x in e["name"].lower() for x in ("failed", "error", "invalid", "unavailable"))]
    dropped = sum(e.get("dropped_events", 0) for e in events if e["kind"] == "footer")
    dropped += sum(e["wall_us"] for e in selected if e["kind"] == "counter" and e["name"] in ("dropped_events", "gpu_pass_overflow"))
    if dropped:
        issues.append(f"Dropped events / overflow: {dropped}")
    if not any(e["kind"] == "footer" for e in events):
        issues.append("Missing shutdown footer: capture may be incomplete")
    if frames[0]["logic"] > warmup or frames[-1]["logic"] < end - 1:
        issues.append("Requested simulation window is not fully captured")
    if any(e.get("write_error") for e in events if e["kind"] == "footer"):
        issues.append("Profile file write error")
    if any(frames[i+1]["frame"] != e["frame"] + 1 for i,e in enumerate(frames[:-1])):
        issues.append("Missing main frame records inside the measurement interval")
    presentation = next((e["name"].split(": ",1)[1] for e in events if e["kind"] == "info" and e["name"].startswith("presentation: ")), "unknown")
    result = dict(presentation=presentation, frames=n, logic_interval=[warmup, end], frame_ms=distribution(frame_ms),
                  average_fps=1000 / statistics.mean(frame_ms),
                  p99_equivalent_fps=1000 / percentile(frame_ms, 99),
                  main_cpu_ms=distribution([e["cpu_us"] / 1000 for e in frames]),
                  renderer_cpu_ms=distribution([e["cpu_us"] / 1000 for e in renderer]),
                  gpu_frame_coverage=len(gpu_ids) / n, gpu_pass_sampled_frames=len(pass_ids), cpu_scopes=cpu, gpu=gpu_rows,
                  counters=[dict(thread=thread, name=name, mean_per_frame=sum(e["wall_us"] for e in rows)/n,
                                 maximum=max(e["wall_us"] for e in rows)) for (thread, name), rows in counters.items()],
                  metadata=[e for e in events if e["kind"] in ("metadata", "info")], issues=sorted(set(issues)))
    return result, selected


def write_report(out, result, selected):
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    origin = min(e["start_us"] for e in selected if e["kind"] == "frame")
    trace = []
    for e in selected:
        kind = e["kind"]
        if kind in ("frame", "scope", "gpu"):
            # Place GPU command buffers on a separate lane from encoder intervals.
            lane = "GPU commands" if kind == "gpu" and e["name"].startswith("command:") else e["thread"]
            if kind == "frame": lane += " frames"
            trace.append(dict(name=e["name"], cat=kind, ph="X", pid=1, tid=lane,
                              ts=e["start_us"]-origin, dur=e["wall_us"],
                              args=dict(frame=e["frame"], logic=e["logic"], cpu_us=e["cpu_us"])))
        elif kind == "counter":
            trace.append(dict(name=e["name"], ph="C", pid=1, tid=e["thread"], ts=e["start_us"]-origin,
                              args={"value": e["wall_us"]}))
    (out / "trace.json").write_text(json.dumps({"traceEvents": trace}))
    def table(headers, rows):
        return '<table><thead><tr>' + ''.join(f'<th>{html.escape(h)}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join(f'<td>{html.escape(str(x))}</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
    cpu = table(["Thread / scope", "Self CPU ms/frame", "Inclusive CPU ms/frame", "Wall ms/frame", "Calls"],
                [(f'{e["thread"]} / {e["name"]}', f'{e["self_cpu_ms"]["mean"]:.3f}', f'{e["cpu_ms"]["mean"]:.3f}', f'{e["wall_ms"]["mean"]:.3f}', e["calls"]) for e in result["cpu_scopes"]])
    gpu = table(["GPU command / pass", "Mean ms/frame", "P95 ms/frame", "Calls"],
                [(e["name"], f'{e["per_frame_ms"]["mean"]:.3f}', f'{e["per_frame_ms"]["p95"]:.3f}', e["calls"]) for e in result["gpu"]])
    counters = table(["Thread / counter", "Mean/frame", "Maximum"], [(f'{e["thread"]} / {e["name"]}', f'{e["mean_per_frame"]:.1f}', f'{e["maximum"]:.0f}') for e in result["counters"]])
    summary = table(["Metric", "Value"], [("Offscreen throughput (frames/s)" if "offscreen" in result["presentation"] else "Average engine FPS", f'{result["average_fps"]:.1f}'),
        ("Frame time median / p95 / p99 (ms)", ' / '.join(f'{result["frame_ms"][p]:.2f}' for p in ("p50", "p95", "p99"))),
        ("Main thread CPU (ms/frame)", f'{result["main_cpu_ms"]["mean"]:.3f}'),
        ("Renderer thread CPU (ms/frame)", f'{result["renderer_cpu_ms"]["mean"]:.3f}' if result["renderer_cpu_ms"] else "inline / unavailable"),
        ("GPU frame coverage", f'{result["gpu_frame_coverage"]*100:.1f}%'), ("Recorded frames", result["frames"])])
    notes = ' '.join(html.escape(x) for x in result["issues"]) or "No recording errors reported."
    doc = f'''<!doctype html><meta charset="utf-8"><title>Generals battle benchmark</title>
<style>body{{background:#101821;color:#e7edf5;font:16px system-ui;max-width:1250px;margin:40px auto;padding:0 24px}}h1,h2{{color:#7fd6dd}}table{{border-collapse:collapse;width:100%;margin:24px 0}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #324354}}th{{color:#9ac0d3}}a{{color:#7fd6dd}}p{{line-height:1.55}}td:first-child{{overflow-wrap:anywhere;max-width:500px}}</style>
<h1>Generals battle benchmark</h1><p>{html.escape(result["presentation"])}. Simulation frames {result["logic_interval"][0]}–{result["logic_interval"][1]-1}. {notes}</p>{summary}
<p><a href="summary.json">Raw summary</a> · <a href="trace.json">Timeline (Chrome trace / Perfetto)</a> · <a href="run.json">Run settings</a></p>
<p>CPU self time excludes instrumented children. Uninstrumented work remains inside its parent. CPU, renderer and GPU overlap; do not add their times. GPU pass intervals also overlap. Pass averages use sampled frames only; command-buffer averages use all frames. “passes” mode splits encoders for attribution and changes the workload; use “frames” mode for performance comparisons. Engine FPS measures submitted frames, not physical screen refresh.</p>
<h2>CPU scopes</h2>{cpu}<h2>GPU timings</h2>{gpu}<h2>Work counters</h2>{counters}'''
    (out / "report.html").write_text(doc)


def analyze(path, warmup, end):
    result, selected = summarize(load_events(path), warmup, end)
    metadata_path = Path(path).parent / "run.json"
    if metadata_path.exists():
        run_metadata = json.loads(metadata_path.read_text())
        result["issues"].extend(run_metadata.get("environment_warnings", []))
    write_report(Path(path).parent, result, selected)
    return result


def system_snapshot():
    snapshot = dict(load_average=list(os.getloadavg()), logical_cpus=os.cpu_count())
    try:
        output = subprocess.check_output(["top", "-l", "2", "-s", "1", "-n", "0"], text=True, stderr=subprocess.STDOUT, timeout=15)
        idle = re.findall(r"CPU usage:.*?([\d.]+)% idle", output)
        snapshot["cpu_idle_percent"] = float(idle[-1]) if idle else None
        memory = re.findall(r"PhysMem: (.*)", output)
        snapshot["memory"] = memory[-1] if memory else None
    except (OSError, subprocess.SubprocessError) as error:
        snapshot["sampling_error"] = str(error)
    return snapshot


def environment_warnings(before, after):
    warnings = []
    for label, snapshot in (("before", before), ("after", after)):
        idle = snapshot.get("cpu_idle_percent")
        if idle is not None and idle < 20:
            warnings.append(f"Heavy system CPU load {label} run: {100-idle:.1f}% busy")
        cores = snapshot.get("logical_cpus")
        if cores and snapshot["load_average"][0] > cores:
            warnings.append(f"System load {label} run exceeds logical CPU count")
        if snapshot.get("sampling_error"):
            warnings.append(f"System-load sampling unavailable {label} run")
    return warnings


def run(args, units, mode, repeat):
    out = args.output / f"{args.label}-{args.roster}-{units*2}-{mode}-{repeat}"
    out.mkdir(parents=True, exist_ok=False)
    battle = out / "battle.txt"
    battle.write_text(f"map Tournament Desert\ncash 10000\nseed {args.seed}\nsuperweapons 0\n"
                      "player human FactionAmerica 0 0\nplayer easy FactionChina 1 2\n")
    env = {k:v for k,v in os.environ.items() if not k.startswith(("GENERALS_", "D3D8METAL_"))}
    env.update(GENERALS_ZH_PATH=str(args.game_data), GENERALS_PATH=str(args.base_data),
               GENERALS_NO_MESSAGEBOX="1", GENERALS_FPS_LOG="1", GENERALS_CRC_LOG="1", GENERALS_BENCH_UNCAPPED="1",
               GENERALS_BATTLE_TEST=":".join((*ROSTERS[args.roster], str(units))),
               GENERALS_LOOKAT=f"0.5,0.5,{args.camera_height}",
               D3D8METAL_VSYNC="1" if args.vsync else "0", SDL_MAC_BACKGROUND_APP="1", SDL_WINDOW_ACTIVATE_WHEN_SHOWN="0")
    if args.offscreen:
        env["D3D8METAL_BENCH_OFFSCREEN"] = "1"
    if mode != "off":
        env.update(GENERALS_PROFILE=str(out / "profile.jsonl"), GENERALS_PROFILE_MODE=mode,
                   GENERALS_PROFILE_START_LOGIC=str(args.warmup), GENERALS_PROFILE_END_LOGIC=str(args.frames))
    if args.detail:
        env["GENERALS_PROFILE_DETAIL"] = "1"
    for assignment in args.env:
        key, sep, value = assignment.partition("=")
        if not sep or not key.startswith(("GENERALS_", "D3D8METAL_")):
            raise ValueError("--env expects GENERALS_NAME=value or D3D8METAL_NAME=value")
        env[key] = value
    command = [str(args.binary), "-win", "-xres", str(args.width), "-yres", str(args.height),
               "-noaudio", "-noFPSLimit", "-battle", str(battle)]
    before = system_snapshot()
    metadata = dict(system_before=before, command=command, settings={k:v for k,v in env.items() if k.startswith(("GENERALS_", "D3D8METAL_", "SDL_"))},
                    host=platform.platform(), hardware=subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip(),
                    binary_sha256=hashlib.sha256(args.binary.read_bytes()).hexdigest(),
                    scenario=dict(seed=args.seed, roster=args.roster, units_per_side=units, width=args.width, height=args.height,
                                  camera_height=args.camera_height, warmup=args.warmup, end=args.frames, offscreen=args.offscreen, vsync=args.vsync),
                    label=args.label, units_per_side=units, mode=mode, repeat=repeat,
                    diagnostic=args.sample or args.detail or mode == "passes" or
                    any(k.startswith("GENERALS_VERIFY_") for k in env) or "D3D8METAL_SCREENSHOT" in env)
    (out / "run.json").write_text(json.dumps(metadata, indent=2))
    log = out / "native.log"
    started, complete, sample_process = time.monotonic(), False, None
    with log.open("w") as stream:
        process = subprocess.Popen(command, cwd=args.game_data, env=env, stdout=stream, stderr=stream)
        try:
            while process.poll() is None and time.monotonic() - started < args.timeout:
                text = log.read_text(errors="replace")
                logic = re.findall(r"FPS .*logic frame (\d+)", text)
                current = int(logic[-1]) if logic else 0
                if args.sample and current >= args.warmup and sample_process is None:
                    sample_process = subprocess.Popen(["sample", str(process.pid), "5", "1", "-file", str(out / "cpu-stacks.txt")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if current >= args.frames + 30 and (sample_process is None or sample_process.poll() is not None):
                    complete = True
                    break
                time.sleep(0.25)
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            if sample_process is not None and sample_process.poll() is None:
                sample_process.terminate(); sample_process.wait()
    text = log.read_text(errors="replace")
    after = system_snapshot()
    metadata.update(system_after=after, environment_warnings=environment_warnings(before, after), sample_exit_code=sample_process.returncode if sample_process else None,
                    reached_end=complete, exit_code=process.returncode,
                    audio_disabled="Audio disabled (-noaudio)" in text,
                    spawned=re.findall(r"BATTLE_TEST spawned (\d+) .* vs (\d+) ", text),
                    crc={f:c for f,c in re.findall(r"CRC_LOG frame (\d+) crc ([A-F0-9]+)", text)},
                    fps_samples=[dict(fps=float(fps), cpu_ms=float(cpu), logic=int(logic)) for fps,logic,cpu in re.findall(r"FPS ([\d.]+).*logic frame (\d+) cpu ([\d.]+) ms",text) if args.warmup <= int(logic) < args.frames])
    (out / "run.json").write_text(json.dumps(metadata, indent=2))
    if not metadata["audio_disabled"]:
        raise RuntimeError(f"Audio-off confirmation missing; use a native build that supports -noaudio in release: {log}")
    if args.sample and (sample_process is None or sample_process.returncode != 0 or not (out / "cpu-stacks.txt").is_file()):
        raise RuntimeError(f"Native call-stack sampling failed: {out}")
    if not complete or process.returncode != 0 or metadata["spawned"] != [(str(units), str(units))]:
        raise RuntimeError(f"Incomplete battle: {log}")
    if mode == "off":
        result = dict(average_fps=statistics.mean(e["fps"] for e in metadata["fps_samples"]), frame_ms=None)
    else:
        result = analyze(out / "profile.jsonl", args.warmup, args.frames)
        if result["issues"]:
            print("Recording warnings:", result["issues"], flush=True)
    print(json.dumps(dict(run=str(out), fps=result["average_fps"], frame_ms=result["frame_ms"])), flush=True)
    return dict(path=str(out), metadata=metadata, summary=result)


def compare(path):
    runs = json.loads(path.read_text())
    groups = collections.defaultdict(dict)
    for run in runs:
        meta = run["metadata"]
        if meta["diagnostic"] or meta["mode"] != "frames":
            continue
        key = (meta["units_per_side"], meta["repeat"])
        groups[key]["candidate" if meta["label"].endswith("-candidate") else "baseline"] = run
    pairs = []
    for (units, repeat), pair in groups.items():
        if set(pair) != {"baseline", "candidate"}: continue
        a,b = pair["baseline"],pair["candidate"]
        if a["metadata"].get("audio_disabled") != b["metadata"].get("audio_disabled"):
            raise ValueError("Incomparable audio settings")
        if a["metadata"].get("scenario") != b["metadata"].get("scenario"):
            raise ValueError("Incomparable scenarios")
        for key in ("GENERALS_ZH_PATH", "GENERALS_PATH", "GENERALS_BENCH_UNCAPPED", "GENERALS_BATTLE_TEST", "GENERALS_LOOKAT", "D3D8METAL_VSYNC", "D3D8METAL_BENCH_OFFSCREEN"):
            if a["metadata"]["settings"].get(key) != b["metadata"]["settings"].get(key):
                raise ValueError(f"Incomparable settings: {key}")
        if a["metadata"]["command"][1:8] != b["metadata"]["command"][1:8]:
            raise ValueError("Incomparable render resolution / options")
        if a["summary"]["logic_interval"] != b["summary"]["logic_interval"]:
            raise ValueError("Incomparable simulation intervals")
        common = set(a["metadata"]["crc"]) & set(b["metadata"]["crc"])
        mismatches = sorted(f for f in common if a["metadata"]["crc"][f] != b["metadata"]["crc"][f])
        pairs.append(dict(units=units*2, repeat=repeat, baseline_fps=a["summary"]["average_fps"],
                          candidate_fps=b["summary"]["average_fps"],
                          fps_change_percent=(b["summary"]["average_fps"] / a["summary"]["average_fps"]-1)*100,
                          baseline_cpu_ms=a["summary"]["main_cpu_ms"]["mean"], candidate_cpu_ms=b["summary"]["main_cpu_ms"]["mean"],
                          baseline_p95_ms=a["summary"]["frame_ms"]["p95"], candidate_p95_ms=b["summary"]["frame_ms"]["p95"],
                          crc_checks=len(common), crc_mismatches=mismatches,
                          environment_warnings=a["metadata"].get("environment_warnings", []) + b["metadata"].get("environment_warnings", []),
                          recording_issues=a["summary"].get("issues", []) + b["summary"].get("issues", []),
                          baseline=a["path"], candidate=b["path"]))
    if not pairs: raise ValueError("No matched baseline/candidate frames-mode runs")
    for pair in pairs:
        pair["eligible"] = bool(pair["crc_checks"]) and not (pair["crc_mismatches"] or pair["recording_issues"] or pair["environment_warnings"])
    output = path.with_name(path.stem + "-comparison.json")
    output.write_text(json.dumps(pairs, indent=2) + "\n")
    for units in sorted({p["units"] for p in pairs}):
        rows=[p for p in pairs if p["units"] == units]
        eligible = [p for p in rows if p["eligible"]]
        print(json.dumps(dict(units=units, pairs=len(rows), eligible_pairs=len(eligible),
                              median_fps_change_percent=statistics.median(p["fps_change_percent"] for p in eligible) if eligible else None,
                              paired_changes=[p["fps_change_percent"] for p in rows],
                              crc_mismatches=[p["crc_mismatches"] for p in rows],
                              noisy_pairs=sum(bool(p["environment_warnings"]) for p in rows))), flush=True)
    rows = []
    for p in pairs:
        status = "Eligible" if p["eligible"] else "Unreliable: " + "; ".join(p["recording_issues"] + p["environment_warnings"] + (["CRC mismatch or no CRC samples"] if p["crc_mismatches"] or not p["crc_checks"] else []))
        links = []
        for label in ("baseline", "candidate"):
            relative = os.path.relpath(Path(p[label]) / "report.html", path.parent)
            links.append(f'<a href="{html.escape(relative, quote=True)}">{label}</a>')
        rows.append(f'<tr><td>{p["units"]}</td><td>{p["repeat"]+1}</td><td>{p["baseline_fps"]:.1f}</td><td>{p["candidate_fps"]:.1f}</td><td>{p["fps_change_percent"]:+.1f}%</td><td>{html.escape(status)}</td><td>{" / ".join(links)}</td></tr>')
    presentation = runs[0]["summary"].get("presentation", "See run settings")
    output.with_suffix(".html").write_text('<!doctype html><meta charset="utf-8"><title>Battle benchmark comparison</title><style>body{font:16px system-ui;background:#101821;color:#e7edf5;max-width:1200px;margin:40px auto;padding:24px}td,th{padding:12px;text-align:left;border-bottom:1px solid #324354}a{color:#7fd6dd}table{border-collapse:collapse}p{line-height:1.5}</style><h1>Battle benchmark comparison</h1><p>' + html.escape(presentation) + '. Rates are engine frames/s; offscreen throughput is not on-screen gameplay FPS. Ineligible pairs are excluded from aggregate speedup statistics. CPU and GPU overlap.</p><table><tr><th>Units</th><th>Pair</th><th>Before</th><th>After</th><th>Change</th><th>Status</th><th>Reports</th></tr>' + ''.join(rows) + '</table>')
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("results", type=Path)
    analyze_parser = sub.add_parser("analyze")
    analyze_parser.add_argument("profile", type=Path)
    analyze_parser.add_argument("--warmup", type=int, default=180)
    analyze_parser.add_argument("--frames", type=int, default=600)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--binary", type=Path, default=ROOT / "build/macos/GeneralsMD/generalszh")
    run_parser.add_argument("--game-data", type=Path, required=True)
    run_parser.add_argument("--base-data", type=Path, required=True)
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--label", default="baseline")
    run_parser.add_argument("--units", type=int, nargs="+", default=[150, 300])
    run_parser.add_argument("--modes", nargs="+", choices=["off", "frames", "cpu", "gpu", "passes"], default=["frames", "gpu"])
    run_parser.add_argument("--rounds", type=int, default=3)
    run_parser.add_argument("--roster", choices=ROSTERS, default="armor")
    run_parser.add_argument("--seed", type=int, default=5)
    run_parser.add_argument("--warmup", type=int, default=180)
    run_parser.add_argument("--frames", type=int, default=600)
    run_parser.add_argument("--timeout", type=int, default=120)
    run_parser.add_argument("--width", type=int, default=1280)
    run_parser.add_argument("--height", type=int, default=800)
    run_parser.add_argument("--camera-height", type=int, default=1000)
    run_parser.add_argument("--offscreen", action="store_true", help="same render/presentation shaders into a texture; isolates throughput from the window compositor, not playable FPS")
    run_parser.add_argument("--vsync", action="store_true")
    run_parser.add_argument("--sample", action="store_true", help="separate diagnostic run: collect 5 seconds of native CPU call stacks")
    run_parser.add_argument("--detail", action="store_true", help="expensive per-draw CPU tracing; diagnostic only")
    run_parser.add_argument("--compare-binary", type=Path, help="alternate with a candidate binary built from the proposed change")
    run_parser.add_argument("--compare-env", action="append", default=[], help="alternate baseline and candidate, overriding this setting in the candidate")
    run_parser.add_argument("--env", action="append", default=[], help="explicit GENERALS_/D3D8METAL_ override; recorded in run.json")
    args = parser.parse_args()
    if args.action == "compare":
        compare(args.results)
        return
    if args.action == "analyze":
        result = analyze(args.profile, args.warmup, args.frames)
        print(json.dumps({k:v for k,v in result.items() if k not in ("metadata", "cpu_scopes", "gpu", "counters")}))
        return
    for key in ("binary", "game_data", "base_data", "output"):
        setattr(args, key, getattr(args, key).resolve())
    if args.rounds < 1 or args.warmup < 90 or args.frames <= args.warmup + 60 or any(not 1 <= n <= 1000 for n in args.units):
        parser.error("Use 1..1000 units/army, warmup >=90, frames > warmup+60 and rounds >=1")
    if not re.fullmatch(r"[\w-]+", args.label):
        parser.error("label must contain only letters, digits, underscores or hyphens")
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for units in args.units:
        for repeat in range(args.rounds):
            for mode in (args.modes if repeat % 2 == 0 else list(reversed(args.modes))):
                variants = [args]
                if args.compare_env or args.compare_binary:
                    candidate = copy.copy(args)
                    candidate.env = args.env + args.compare_env
                    if args.compare_binary: candidate.binary = args.compare_binary.resolve()
                    candidate.label = args.label + "-candidate"
                    variants.append(candidate)
                    if repeat % 2: variants.reverse()
                for variant in variants:
                    results.append(run(variant, units, mode, repeat))
                (args.output / f"{args.label}-results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
