"""CLI runner (PRD s2, s9):

    python -m review_agent --repo . --pr $PR --base $BASE --head $HEAD --commit $SHA

Exit code is the quality gate result: 0 = PASS, 1 = CHANGES REQUESTED / hard failure.
"""

from __future__ import annotations

import argparse
import sys

from . import logging as L
from .config import load_settings
from .pipeline import RunInputs, run
from .report.json_report import write_report


def _parse_args(argv):
    p = argparse.ArgumentParser(prog="review-agent", description="AI code review for Java PRs")
    p.add_argument("--repo", default=".", help="path to the local checkout (default: .)")
    p.add_argument("--pr", type=int, default=None, help="pull request number")
    p.add_argument("--base", default=None, help="base branch / ref")
    p.add_argument("--head", default=None, help="head branch / ref")
    p.add_argument("--commit", default=None, help="head commit SHA (for the build status)")
    p.add_argument("--overlay", default="", help="dir of knowledge docs / review-rules.yaml to overlay")
    p.add_argument("--report", default="review-report.json", help="output report path")
    p.add_argument("--status-url", default="", help="URL to link from the commit status")
    pub = p.add_mutually_exclusive_group()
    pub.add_argument("--publish", dest="publish", action="store_true",
                     help="post comments + set commit status on the PR")
    pub.add_argument("--no-publish", dest="publish", action="store_false",
                     help="local run: write the report only (default)")
    p.set_defaults(publish=False)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    settings = load_settings()

    inp = RunInputs(
        repo_path=args.repo, pr_id=args.pr, base=args.base, head=args.head,
        commit=args.commit, overlay_dir=args.overlay, publish=args.publish,
        status_url=args.status_url,
    )

    try:
        report = run(settings, inp)
    except Exception as e:
        L.error(f"review failed: {e}")
        return 2

    out = write_report(report, args.report)
    L.step(f"report written: {out}")

    gate = report.gate
    print(f"\n{gate.status}  score={gate.score}/100  "
          f"CRITICAL={gate.counts['CRITICAL']} HIGH={gate.counts['HIGH']} "
          f"MEDIUM={gate.counts['MEDIUM']} LOW={gate.counts['LOW']}", file=sys.stderr)
    for r in gate.reasons:
        print(f"  - {r}", file=sys.stderr)
    return gate.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
