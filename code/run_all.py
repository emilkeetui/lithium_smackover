"""run_all.py — Run the seven Smackover pipeline scripts in order, with timing
and fail-fast logging.

Usage:
    "Z:/ek559/nys_algal_bloom/NYS algal bloom/code2/Scripts/python.exe" code/run_all.py
    ... code/run_all.py --from 05       # resume at step 05
    ... code/run_all.py --only 06 07    # run only steps 06 and 07
    ... code/run_all.py --dry-run       # print plan, don't execute

Each step is invoked with sys.executable, so launching this driver with the
project venv (see notes/implementation_plan.md §0) propagates it to every
step — never `python`/`python3`/`py`.

If a step fails (non-zero exit), the driver stops immediately. Per the
implementer rules in notes/implementation_plan.md: do not paper over
validation failures downstream (e.g. the tonnage-conservation or
raster/fishnet-alignment asserts in 01 and 06).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# (step_id, script filename, human description)
STEPS: list[tuple[str, str, str]] = [
    ("01", "01_load_lithium.py",      "Grid Li grade/thickness onto the fishnet; per-cell in-place tonnage"),
    ("02", "02_load_huc12.py",        "Clip national WBD HUC12 to study area; cache national TOHUC table"),
    ("03", "03_intake_hucs.py",       "SDWIS x SDWA CWS join -> I_sw / I_gw HUC12 sets"),
    ("04", "04_upstream_hucs.py",     "National TOHUC flow graph; U_sw + steps_to_sw_intake; W"),
    ("05", "05_population_by_huc.py", "LandScan population per HUC12 (exactextract)"),
    ("06", "06_impact_dataset.py",    "Overlay cells x HUC12; apportion tonnage; classify impact tier"),
    ("07", "07_summary_and_map.py",   "Headline summary tables + map figures"),
    ("08", "08_concentration_bivariate.py", "HUC12 Li concentration (p5/p50/p95 × median/mean) × CWS pop served bivariate maps"),
    ("09", "09_violation_utility_tables.py", "SDWA violation / utility comparison tables"),
    ("10", "10_private_wells.py",     "Private-well population per HUC12 (outside CWS service areas) + Li bivariate map"),
    ("11", "11_density_bivariate.py", "HUC12 Li concentration × LandScan population density bivariate maps"),
]


def _fmt_seconds(s: float) -> str:
    if s < 60:
        return f"{s:.1f}s"
    m, sec = divmod(s, 60)
    return f"{int(m)}m{sec:04.1f}s"


def _select(args: argparse.Namespace) -> list[tuple[str, str, str]]:
    if args.only:
        ids = set(args.only)
        chosen = [s for s in STEPS if s[0] in ids]
        missing = ids - {s[0] for s in chosen}
        if missing:
            sys.exit(f"Unknown step id(s): {sorted(missing)}")
        return chosen
    if args.from_:
        try:
            i = next(idx for idx, s in enumerate(STEPS) if s[0] == args.from_)
        except StopIteration:
            sys.exit(f"Unknown --from step id: {args.from_}")
        return STEPS[i:]
    return list(STEPS)


def _run_step(step_id: str, script: str, desc: str, log_dir: Path) -> float:
    """Run one step; stream its output live AND tee to a log file. Returns
    elapsed seconds. Raises SystemExit on non-zero exit."""
    log_path = log_dir / f"step_{step_id}.log"
    cmd = [sys.executable, "-u", script]

    bar = "=" * 70
    print(f"\n{bar}\n[{step_id}] {desc}\n        cmd: {' '.join(cmd)}\n        log: {log_path}\n{bar}",
          flush=True)

    start = time.time()
    with open(log_path, "w", encoding="utf-8") as logf:
        logf.write(f"# step {step_id}: {desc}\n# cmd: {' '.join(cmd)}\n\n")
        logf.flush()
        proc = subprocess.Popen(
            cmd, cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            logf.write(line)
        rc = proc.wait()
    elapsed = time.time() - start

    if rc != 0:
        print(f"\n[{step_id}] FAILED (exit {rc}) after {_fmt_seconds(elapsed)}. "
              f"See {log_path}.", flush=True)
        sys.exit(rc)

    print(f"\n[{step_id}] OK in {_fmt_seconds(elapsed)}", flush=True)
    return elapsed


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from", dest="from_", metavar="STEP",
                    help="Resume from step id (e.g. 05).")
    p.add_argument("--only", nargs="+", metavar="STEP",
                    help="Run only the given step ids.")
    p.add_argument("--dry-run", action="store_true",
                    help="Print the planned steps and exit.")
    p.add_argument("--clean-logs", action="store_true",
                    help="Wipe outputs/logs/ before running.")
    args = p.parse_args()

    chosen = _select(args)
    log_dir = ROOT.parent / "outputs" / "logs"

    if args.dry_run:
        print("Planned steps:")
        for sid, script, desc in chosen:
            print(f"  [{sid}] {desc}  ->  {script}")
        print(f"\nLogs would go to: {log_dir}")
        return

    if args.clean_logs and log_dir.exists():
        shutil.rmtree(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    print(f"Repo root: {ROOT.parent}")
    print(f"Python: {sys.executable}")
    print(f"Running {len(chosen)} step(s); logs -> {log_dir}")

    overall_start = time.time()
    timings: list[tuple[str, float]] = []
    for sid, script, desc in chosen:
        timings.append((sid, _run_step(sid, script, desc, log_dir)))

    total = time.time() - overall_start
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for sid, secs in timings:
        print(f"  [{sid}] {_fmt_seconds(secs)}")
    print(f"  TOTAL: {_fmt_seconds(total)}")


if __name__ == "__main__":
    main()
