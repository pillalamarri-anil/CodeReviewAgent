"""AC11: the full pipeline runs offline on the mock provider with no network."""

import sys

from review_agent import pipeline as pipeline_mod
from review_agent.config import Settings
from review_agent.pipeline import RunInputs, run

REPO_FILE = "src/main/java/com/example/repository/OrderRepository.java"

_NATIVE_QUERY_FINDING = {
    "severity": "HIGH",
    "category": "SECURITY",
    "file": REPO_FILE,
    "line": 17,
    "title": "String-concatenated native SQL query",
    "description": "findNewOrders builds a native SQL string by concatenation.",
    "impact": "SQL injection risk and brittle queries.",
    "recommendation": "Use a bound parameter and JPQL.",
    "suggested_fix": None,
    "evidence": "nativeQuery = true",
    "confidence": 0.93,
}

# same line-bucket (17//5 == 18//5), same category, title normalizes identically -> merged
_DUP_FINDING = dict(_NATIVE_QUERY_FINDING, line=18,
                    title="String-concatenated  native SQL  query!!", confidence=0.88)


def _settings():
    return Settings(_env_file=None, llm_provider="mock", min_confidence=0.75,
                    max_context_tokens=8000, max_critical=0, max_high=0, max_medium=5)


def _patch_provider(monkeypatch, responses):
    from review_agent.llm.mock import MockProvider

    monkeypatch.setattr(pipeline_mod, "build_provider",
                        lambda s: MockProvider(responses=responses))


def test_run_flags_finding_and_fails_gate(monkeypatch, sample_repo, diff):
    _patch_provider(monkeypatch, {
        REPO_FILE: {"summary": "native query issue", "findings": [_NATIVE_QUERY_FINDING, _DUP_FINDING]},
    })

    report = run(_settings(), RunInputs(
        repo_path=sample_repo, base="main", head="feat/x",
        diff_text=diff("repo_change.diff"), publish=False,
    ))

    # two raw findings in the same line-bucket + category -> merged to one
    assert len(report.findings) == 1
    f = report.findings[0]
    assert f.file == REPO_FILE and f.category.value == "SECURITY"

    assert report.gate.status == "CHANGES REQUESTED"
    assert report.gate.exit_code == 1
    assert report.review_ok is True
    assert "openai" not in sys.modules and "anthropic" not in sys.modules


def test_run_passes_when_clean(monkeypatch, sample_repo, diff):
    _patch_provider(monkeypatch, {})  # mock returns no findings
    report = run(_settings(), RunInputs(
        repo_path=sample_repo, base="main", head="feat/x",
        diff_text=diff("method_edit.diff"), publish=False,
    ))
    assert report.findings == []
    assert report.gate.status == "PASS" and report.gate.exit_code == 0


def test_run_drops_unevidenced_finding(monkeypatch, sample_repo, diff):
    bad = dict(_NATIVE_QUERY_FINDING, evidence="text that is nowhere in the context")
    _patch_provider(monkeypatch, {REPO_FILE: {"summary": "x", "findings": [bad]}})
    report = run(_settings(), RunInputs(
        repo_path=sample_repo, base="main", head="feat/x",
        diff_text=diff("repo_change.diff"), publish=False,
    ))
    assert report.findings == []
    assert len(report.dropped) == 1
    assert "verbatim" in report.dropped[0].reason


def test_run_marks_review_failed_on_bad_json(monkeypatch, sample_repo, diff):
    from review_agent.llm.mock import MockProvider

    monkeypatch.setattr(pipeline_mod, "build_provider",
                        lambda s: MockProvider(raw="{ not valid json"))
    report = run(_settings(), RunInputs(
        repo_path=sample_repo, base="main", head="feat/x",
        diff_text=diff("repo_change.diff"), publish=False,
    ))
    assert report.review_ok is False
    assert report.gate.exit_code == 1
    assert any(fr.status == "failed" for fr in report.files_reviewed)
