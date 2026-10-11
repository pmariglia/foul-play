"""
Fuzz foul-play's protocol parsing against a Pokemon Showdown checkout

    python -m fuzz.run --ps-dir ../pokemon-showdown --battles 50
    python -m fuzz.run --ps-dir ../pokemon-showdown --until-finding --time-limit 600

See fuzz/README.md
"""

import argparse
import asyncio
import itertools
import json
import logging
import multiprocessing
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

# new-signature findings come from comparing the whole run against --baseline at the end
STOPPABLE_SEVERITIES = [s for s in Severity if s != Severity.NEW_SIGNATURE]


def parse_severities(value: str) -> frozenset:
    severities = frozenset(Severity(s.strip()) for s in value.split(",") if s.strip())
    not_stoppable = severities - set(STOPPABLE_SEVERITIES)
    if not_stoppable:
        raise argparse.ArgumentTypeError(
            "cannot stop on {}, choose from {}".format(
                ",".join(sorted(not_stoppable)), ",".join(STOPPABLE_SEVERITIES)
            )
        )
    return severities


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
    parser.add_argument(
        "--battles",
        type=int,
        default=None,
        help="Number of battles to run (default: 20, or no limit with --until-finding)",
    )
    parser.add_argument(
        "--until-finding",
        action="store_true",
        help="Keep running battles until one has a --stop-on finding, then stop. "
        "Its artifact is always written so it can be replayed",
    )
    parser.add_argument(
        "--stop-on",
        type=parse_severities,
        default="error,drift,info",
        help="Comma separated severities that stop an --until-finding run (default: error,drift,info)",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=None,
        help="Stop starting new battles after this many seconds",
    )
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
    args = parser.parse_args(argv)
    if args.battles is None and not args.until_finding:
        args.battles = 20
    return args


def parse_formats(args) -> list[str]:
    return [f.strip() for f in args.formats.split(",") if f.strip()]


def battle_plan(args, worker_id=0, jobs=1):
    """
    The (format, seed) of every battle this worker runs. Battle `i` of the run always has the
    same seed, so `--battles N` and `--until-finding` play the same battles for the same --seed
    """
    formats = parse_formats(args)
    if args.battle_seed:
        if worker_id == 0:
            yield formats[0], args.battle_seed
        return

    from fuzz.harness import derived_seed

    if args.battles is None:
        indices = itertools.count(worker_id, jobs)
    else:
        indices = range(worker_id, args.battles, jobs)
    for i in indices:
        yield formats[i % len(formats)], derived_seed(args.seed, i)


def should_stop(args, stop_event) -> bool:
    if stop_event.is_set():
        return True
    return args.deadline is not None and time.time() >= args.deadline


async def _run_worker(args, worker_id, jobs, stop_event):
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

    for pokemon_format in sorted(set(parse_formats(args))):
        prepare_format(pokemon_format)

    driver = PSDriver(args.ps_dir)
    await driver.start()
    results = []
    try:
        for i, (pokemon_format, seed) in enumerate(battle_plan(args, worker_id, jobs)):
            if should_stop(args, stop_event):
                break
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
                stop_severities=args.stop_on if args.until_finding else frozenset(),
            )
            results.append(asdict(result))
            if result.errors:
                status = "FAIL"
            elif result.stop_findings:
                status = "FOUND"
            else:
                status = "ok"
            print(
                "[{}] {} {} turns={} {}s {}".format(
                    status,
                    pokemon_format,
                    seed,
                    result.turns,
                    result.duration_s,
                    "; ".join(result.errors or result.stop_findings),
                ),
                file=sys.stderr,
                flush=True,
            )
            if result.stop_findings:
                # the other workers finish the battle they are in and stop too
                stop_event.set()
                break
    finally:
        await driver.close()

    return {
        "results": results,
        "findings": [asdict(f) for f in observer.findings],
        "message_counts": dict(observer.message_counts),
        "signatures": dict(observer.signatures),
    }


def run_worker(args, worker_id, jobs, stop_event):
    return asyncio.run(_run_worker(args, worker_id, jobs, stop_event))


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


def print_found(found):
    print()
    print("Stopped on:")
    for r in found:
        print("  {}".format(r["battle_id"]))
        for finding in r["stop_findings"]:
            print("      {}".format(finding))
        # the finding may have come from either bot
        for side in ("p1", "p2"):
            print("    python -m fuzz.replay {} --side {}".format(r["artifact"], side))


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

    args.deadline = None if args.time_limit is None else time.time() + args.time_limit
    if args.battle_seed:
        jobs = 1
    elif args.battles is None:
        jobs = max(1, args.jobs)
    else:
        jobs = max(1, min(args.jobs, args.battles))

    if args.battle_seed:
        planned = "1 battle"
    elif args.battles is None:
        planned = "until a {} finding".format("/".join(sorted(args.stop_on)))
    else:
        planned = "{} battles".format(args.battles)
        if args.until_finding:
            planned += " or until a {} finding".format("/".join(sorted(args.stop_on)))
    if args.time_limit is not None:
        planned += ", at most {}s".format(args.time_limit)
    print(
        "PS {} | {} | seed {} | {} jobs".format(
            ps_version(args.ps_dir), planned, args.seed, jobs
        ),
        file=sys.stderr,
    )

    if jobs == 1:
        outputs = [run_worker(args, 0, 1, multiprocessing.Event())]
    else:
        with multiprocessing.Manager() as manager:
            stop_event = manager.Event()
            with ProcessPoolExecutor(jobs) as pool:
                futures = [
                    pool.submit(run_worker, args, i, jobs, stop_event)
                    for i in range(jobs)
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
    found = [r for r in results if r["stop_findings"]]
    if found:
        print_found(found)
    elif args.until_finding:
        print()
        print(
            "No {} finding in {} battles".format(
                "/".join(sorted(args.stop_on)), len(results)
            )
        )
    failed = any(f.severity in FAILING_SEVERITIES for f in ordered)
    return 1 if failed or found else 0


if __name__ == "__main__":
    sys.exit(main())
