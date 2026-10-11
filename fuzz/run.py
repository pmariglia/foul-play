"""
Fuzz foul-play's protocol parsing against a Pokemon Showdown checkout

    python -m fuzz.run --ps-dir ../pokemon-showdown --battles 50

See fuzz/README.md
"""

import argparse
import asyncio
import json
import logging
import os
import random
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict

from fuzz.detectors import (
    FAILING_SEVERITIES,
    Finding,
    Findings,
    FoulPlayLogCollector,
    ProtocolObserver,
    Severity,
)

SEVERITY_ORDER = list(Severity)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Self-play fuzzing of foul-play's protocol parsing against Pokemon Showdown"
    )
    parser.add_argument(
        "--ps-dir",
        default=os.environ.get("PS_DIR", "../pokemon-showdown"),
        help="Pokemon Showdown checkout, built with `node build` (default: $PS_DIR or ../pokemon-showdown)",
    )
    parser.add_argument(
        "--formats",
        default="gen9randombattle",
        help="Comma separated formats, battles are spread across them round-robin",
    )
    parser.add_argument("--battles", type=int, default=20)
    parser.add_argument(
        "--seed",
        default=None,
        help="Master seed that every battle seed is derived from (default: random)",
    )
    parser.add_argument(
        "--battle-seed",
        default=None,
        help="Run exactly one battle with this PS seed, e.g. from a failure artifact",
    )
    parser.add_argument("--jobs", type=int, default=1, help="Worker processes")
    parser.add_argument("--receive-timeout", type=float, default=30)
    parser.add_argument("--battle-timeout", type=float, default=600)
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Where to write report.json and failure artifacts (default: fuzz/out/<timestamp>)",
    )
    parser.add_argument(
        "--save-artifacts",
        action="store_true",
        help="Write a replayable artifact for every battle, not only the ones with errors",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Signatures file; protocol/request signatures not in it are reported as new-signature",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Add every signature seen in this run to --baseline",
    )
    parser.add_argument(
        "--log-level", default="CRITICAL", help="foul-play's own log level"
    )
    return parser.parse_args(argv)


def battle_plan(args) -> list[tuple[str, str]]:
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    if args.battle_seed:
        return [(formats[0], args.battle_seed)]

    from fuzz.harness import derived_seed

    return [
        (formats[i % len(formats)], derived_seed(args.seed, i))
        for i in range(args.battles)
    ]


async def _run_worker(args, plan, worker_id):
    from fuzz.harness import (
        PSDriver,
        configure_foulplay,
        prepare_format,
        run_one_battle,
    )

    configure_foulplay()
    observer = ProtocolObserver()
    # the collector needs every warning; what reaches the terminal is up to --log-level
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(args.log_level.upper())
    logging.basicConfig(level=logging.WARNING, handlers=[stream_handler], force=True)
    logging.getLogger().addHandler(FoulPlayLogCollector(observer))

    for pokemon_format in sorted({f for f, _ in plan}):
        prepare_format(pokemon_format)

    driver = PSDriver(args.ps_dir)
    await driver.start()
    results = []
    try:
        for i, (pokemon_format, seed) in enumerate(plan):
            result = await run_one_battle(
                driver,
                observer,
                pokemon_format,
                seed,
                battle_number=worker_id * 1_000_000 + i,
                receive_timeout=args.receive_timeout,
                battle_timeout=args.battle_timeout,
                out_dir=args.out_dir,
                save_artifact=args.save_artifacts,
            )
            results.append(asdict(result))
            status = "FAIL" if result.errors else "ok"
            print(
                "[{}] {} {} turns={} {}s {}".format(
                    status,
                    pokemon_format,
                    seed,
                    result.turns,
                    result.duration_s,
                    "; ".join(result.errors),
                ),
                file=sys.stderr,
                flush=True,
            )
    finally:
        await driver.close()

    return {
        "results": results,
        "findings": [asdict(f) for f in observer.findings],
        "message_counts": dict(observer.message_counts),
        "signatures": dict(observer.signatures),
    }


def run_worker(args, plan, worker_id):
    return asyncio.run(_run_worker(args, plan, worker_id))


def ps_version(ps_dir: str) -> str:
    def git(*cmd):
        return subprocess.run(
            ["git", "-C", ps_dir, *cmd], capture_output=True, text=True
        ).stdout.strip()

    commit = git("rev-parse", "HEAD") or "unknown"
    return commit + (" (dirty)" if git("status", "--porcelain") else "")


def apply_baseline(args, findings: Findings, signatures: Counter):
    baseline = set()
    if os.path.exists(args.baseline):
        with open(args.baseline) as f:
            baseline = set(json.load(f)["signatures"])
        for sig in sorted(set(signatures) - baseline):
            findings.add(
                Finding(
                    Severity.NEW_SIGNATURE,
                    "new-signature",
                    sig,
                    "seen {} times, not in {}".format(signatures[sig], args.baseline),
                    "",
                ),
                "",
            )
    elif not args.update_baseline:
        print(
            "baseline {} does not exist, skipping the comparison".format(args.baseline),
            file=sys.stderr,
        )

    if args.update_baseline:
        with open(args.baseline, "w") as f:
            json.dump(
                {
                    "ps_commit": ps_version(args.ps_dir),
                    "signatures": sorted(baseline | set(signatures)),
                },
                f,
                indent=2,
            )
            f.write("\n")


def print_summary(findings: list[Finding], results, out_dir):
    failed = [r for r in results if r["errors"]]
    print()
    print(
        "{} battles, {} with errors. Report: {}".format(
            len(results), len(failed), os.path.join(out_dir, "report.json")
        )
    )
    for severity in SEVERITY_ORDER:
        group = [f for f in findings if f.severity == severity]
        if not group:
            continue
        print()
        print("== {} ({}) ==".format(severity, len(group)))
        for f in sorted(group, key=lambda f: -f.count):
            print("  [{}] {} x{}".format(f.kind, f.key, f.count))
            if severity == Severity.KNOWN_GAP:
                continue
            if severity == Severity.INFO:
                print("      e.g. {}".format(f.example.splitlines()[0][:200]))
                continue
            if f.detail and f.detail != f.key:
                print("      {}".format(f.detail.splitlines()[0][:200]))
            if f.example:
                print("      e.g. {}".format(f.example.splitlines()[0][:200]))
            if f.first_battle:
                print("      first: {}".format(f.first_battle))
    if failed:
        print()
        print("Reproduce a failure with:")
        r = failed[0]
        print(
            "  python -m fuzz.run --ps-dir {} --formats {} --battle-seed {}".format(
                "<ps-dir>", r["pokemon_format"], r["seed"]
            )
        )


def main(argv=None):
    args = parse_args(argv)
    args.ps_dir = os.path.abspath(args.ps_dir)
    if not os.path.exists(os.path.join(args.ps_dir, "dist", "sim", "index.js")):
        sys.exit(
            "{} has no dist/sim/index.js: run `node build` in the PS checkout".format(
                args.ps_dir
            )
        )
    if args.seed is None:
        args.seed = str(random.randrange(2**32))
    if args.out_dir is None:
        args.out_dir = os.path.join(
            "fuzz", "out", time.strftime("%Y%m%d-%H%M%S") + "-" + args.seed
        )
    os.makedirs(args.out_dir, exist_ok=True)

    plan = battle_plan(args)
    jobs = max(1, min(args.jobs, len(plan)))
    print(
        "PS {} | {} battles | seed {} | {} jobs".format(
            ps_version(args.ps_dir), len(plan), args.seed, jobs
        ),
        file=sys.stderr,
    )

    if jobs == 1:
        outputs = [run_worker(args, plan, 0)]
    else:
        with ProcessPoolExecutor(jobs) as pool:
            futures = [
                pool.submit(run_worker, args, plan[i::jobs], i) for i in range(jobs)
            ]
            outputs = [f.result() for f in futures]

    findings = Findings()
    message_counts = Counter()
    signatures = Counter()
    results = []
    for out in outputs:
        results += out["results"]
        message_counts.update(out["message_counts"])
        signatures.update(out["signatures"])
        worker_findings = Findings()
        for f in out["findings"]:
            f = Finding(**f)
            f.severity = Severity(f.severity)
            worker_findings.by_id[f.id] = f
        findings.merge(worker_findings)

    if args.baseline:
        apply_baseline(args, findings, signatures)

    ordered = sorted(findings, key=lambda f: SEVERITY_ORDER.index(f.severity))
    with open(os.path.join(args.out_dir, "report.json"), "w") as f:
        json.dump(
            {
                "ps_commit": ps_version(args.ps_dir),
                "seed": args.seed,
                "formats": args.formats,
                "findings": [asdict(f) for f in ordered],
                "battles": results,
                "message_counts": dict(message_counts.most_common()),
                "signatures": dict(signatures.most_common()),
            },
            f,
            indent=2,
        )

    print_summary(ordered, results, args.out_dir)
    return 1 if any(f.severity in FAILING_SEVERITIES for f in ordered) else 0


if __name__ == "__main__":
    sys.exit(main())
