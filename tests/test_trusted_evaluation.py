"""Trusted evaluation tools use synthetic responses and pytest-socket blocks the network."""

import gzip
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from research_fixtures import Providers, sourced

from aletheia.budgets import CallBudget, RunBudget
from aletheia.config import ProviderSettings
from aletheia.evaluation import KeySource
from aletheia.providers.errors import ErrorCode, ProviderError
from aletheia.providers.nebius import ModelResult, NebiusProvider, TokenUsage
from aletheia.trusted_evaluation import ReplayProvider, load_pages, trusted_claims, validate_claims

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import baseline_verdict as baseline  # noqa: E402
import check_retrieval as retrieval  # noqa: E402
import evaluate_research as runner  # noqa: E402
import score_trusted as scoring  # noqa: E402


def page(text="The Archive opened in 2000.", url="https://example.org/archive", **changes):
    return {
        "url": url,
        "canonical_url": url,
        "title": "Archive record",
        "original_text": text,
        "published_date": None,
        "retrieved_at": "2026-11-16T00:00:00+00:00",
        "limitations": [],
        **changes,
    }


def settings():
    return ProviderSettings(nebius_api_key="fake-model-key", nebius_model="fake-model")


def budget(search=4, extract=4):
    return CallBudget(1, search, extract, time.monotonic() + 60)


def archive(directory, identifier, pages):
    (directory / "pages").mkdir(exist_ok=True, parents=True)
    with gzip.open(directory / "pages" / f"{identifier}.json.gz", "wt", encoding="utf-8") as out:
        json.dump(pages, out)


def test_only_original_included_tuning_claims_can_run():
    assert len(trusted_claims()) == 77
    for ids, split in [(["t-01"], "tuning"), (None, "heldout"), (["c-03"], "tuning")]:
        with pytest.raises(ValueError):
            trusted_claims(ids=ids, split=split)
    claim = trusted_claims(ids=["t-02"])[0]
    for changes in ({"claim": "A substituted claim is forbidden."}, {"split": "heldout"}):
        with pytest.raises(ValueError):
            validate_claims([claim.model_copy(update=changes)])
    with pytest.raises(ValueError):
        validate_claims([claim, claim])
    with pytest.raises(ValueError):
        load_pages(Path("unused"), "../escape")


async def test_replay_ranking_aliases_missing_urls_and_call_limits():
    pages = [page(), page("Orbital planets and stars.", "https://example.org/space", title="Space")]
    pages[0]["canonical_url"] = "https://example.org/canonical"
    pages[0]["limitations"] = ["saved_limitation"]
    async with ReplayProvider(settings()) as search:
        search.set_pages(pages)
        calls = budget(search=1, extract=2)
        result = await search.search("orbital planets", budget=calls, max_results=1)
        assert [r.url for r in result.results] == [pages[1]["url"]]
        with pytest.raises(ProviderError) as error:
            await search.search("archive", budget=calls)
        assert error.value.code == ErrorCode.BUDGET
        extracted = await search.extract(
            ["https://example.org/canonical", "https://example.org/missing", pages[1]["url"]],
            budget=calls,
        )
        assert extracted.pages[0].content == pages[0]["original_text"]
        assert "saved_limitation" in extracted.pages[0].limitations
        assert extracted.pages[1].error == "not_available"
        assert extracted.pages[2].error == "budget_exhausted"
        assert calls.used == {"model": 0, "search": 1, "extract": 2}
        assert [(a.operation, a.units) for a in calls.attempts] == [
            ("search", 1),
            ("extract", 1),
            ("extract", 1),
        ]


async def test_replay_honors_deadlines_escalation_validation_and_truncation():
    async with ReplayProvider(
        settings().model_copy(update={"max_extracted_chars": 1024})
    ) as search:
        search.set_pages([page("A" * 2000)])
        calls = RunBudget()
        calls.search_attempts = 0
        with pytest.raises(ProviderError):
            await search.search("archive", budget=calls)
        calls.escalate()
        assert (await search.search("archive", budget=calls)).results
        result = await search.extract(["https://example.org/archive"], budget=calls)
        assert result.pages[0].truncated and len(result.pages[0].content) == 1024
        before = dict(calls.used)
        with pytest.raises(ProviderError) as error:
            await search.search("", budget=calls)
        assert error.value.code == ErrorCode.INVALID_REQUEST and calls.used == before
        calls.deadline = time.monotonic() - 1
        with pytest.raises(ProviderError) as error:
            await search.search("archive", budget=calls)
        assert error.value.code == ErrorCode.DEADLINE and calls.used == before


async def test_replay_runs_no_search_network_identical_pages_isolated_claims_and_no_labels(
    tmp_path, monkeypatch
):
    evidence = tmp_path / "evidence"
    claims = trusted_claims(ids=["t-02", "t-03"])
    for i, claim in enumerate(claims):
        archive(evidence, claim.id, [page(url=f"https://example.org/claim-{i}")])
        # The labels, source URLs and notes must not be serialized into model prompts.
        claim.sources = [KeySource(url="https://label.invalid/SECRET_SOURCE", shows="SECRET_QUOTE")]
        claim.note = "SECRET_OWNER_DECISION"
        claim.what_needs_correction = "SECRET_CORRECTION"
    providers = Providers()
    requests = []

    class Transport(runner.MeteredTransport):
        def __init__(self, provider, attempts):
            assert provider == "nebius", "Replay must never construct a search network transport"
            self.provider, self.attempts = provider, attempts

            def handle(request):
                requests.append(json.loads(request.content))
                return providers.handle(request)

            self.inner = httpx.MockTransport(handle)

    monkeypatch.setattr(runner, "MeteredTransport", Transport)
    # Captures pages handed to each lane, including repeat runs.
    offered = []
    original = ReplayProvider.search

    async def observe(self, *args, **kwargs):
        result = await original(self, *args, **kwargs)
        offered.append([r.model_dump() for r in result.results])
        return result

    monkeypatch.setattr(ReplayProvider, "search", observe)
    for n in (1, 2):
        args = SimpleNamespace(
            replay_evidence=evidence,
            dotenv=None,
            model=None,
            output=tmp_path / f"run-{n}",
            split="tuning",
            parallel=2,
            resume=False,
        )
        assert await runner.run_batch(args, claims, settings=settings())
        manifest = json.loads((args.output / "manifest.json").read_text())
        assert manifest["replay"] is True
        assert manifest["evidence_directory"] == str(evidence.resolve())
        for i, claim in enumerate(claims):
            saved = json.loads((args.output / "snapshots" / f"{claim.id}.json").read_text())
            assert {s["url"] for s in saved} == {f"https://example.org/claim-{i}"}
    assert offered and len(offered) % 2 == 0
    # Parallel completion order need not match; per-query offered pages must match.
    half = len(offered) // 2
    assert sorted(map(json.dumps, offered[:half])) == sorted(map(json.dumps, offered[half:]))
    assert requests and all("SECRET" not in json.dumps(r) for r in requests)
    assert all("expected_verdict" not in json.dumps(r) for r in requests)
    assert all("label.invalid" not in json.dumps(r) for r in requests)


class FakeModel:
    def __init__(self, answer):
        self.answer, self.requests = answer, []

    async def generate(self, **kwargs):
        self.requests.append(kwargs)
        kwargs["budget"].reserve("nebius", "model", 1)
        return ModelResult(
            baseline.Answer.model_validate(self.answer),
            TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120),
        )


@pytest.mark.parametrize(
    "quote,verdict,downgraded",
    [
        ({"page": 1, "text": "Archive opened  in\n2000."}, "true", False),
        ({"page": 1, "text": "The Archive opened in 1999."}, "cannot_settle", True),
        ({"page": 2, "text": "The Archive opened in 2000."}, "cannot_settle", True),
        ({"page": 1, "text": "   "}, "cannot_settle", True),
    ],
)
async def test_baseline_validates_quotes_in_one_call_without_label_metadata(
    quote, verdict, downgraded
):
    claim = trusted_claims(ids=["t-02"])[0]
    claim.note = "SECRET_NOTE"
    claim.sources = [KeySource(url="https://label.invalid/SECRET_SOURCE", shows="SECRET_QUOTE")]
    model = FakeModel(sourced({"verdict": "true", "quotes": [quote], "reason": "A short reason."}))
    result = await baseline.evaluate_claim(claim, [page()], model, 30)
    assert result["verdict"] == verdict and result["downgraded"] == downgraded
    assert result["original_answer"]["verdict"] == "true"
    assert result["token_usage"]["total_tokens"] == 120
    assert len(model.requests) == 1
    request = model.requests[0]
    text = request["instructions"] + request["input_text"]
    assert "SECRET" not in text and "label.invalid" not in text
    assert set(json.loads(request["input_text"])) == {"claim", "pages"}
    assert request["budget"].used["model"] == 1


def test_quote_spanning_sentences_is_valid_but_joining_distant_passages_is_not():
    answer = baseline.Answer(
        **sourced(dict(verdict="false", quotes=[{"page": 1, "text": "First. Last."}], reason="r"))
    )
    offered = [{"page": 1, "passages": ["First.", "Last."]}]
    assert not baseline.validate_answer(answer, offered, ["First.\nLast."])["downgraded"]
    assert baseline.validate_answer(answer, offered, ["First. Middle. Last."])["downgraded"]
    answer.quotes = []
    assert baseline.validate_answer(answer, offered, ["First. Last."])["downgraded"]


def test_baseline_limits_pages_and_uses_relevant_passages_across_the_document():
    pages = [page("Noise.\n" * 8000 + "The special archive opened in 2000.") for _ in range(8)]
    offered = baseline.prompt_pages("special archive", pages)
    assert len(offered) == 6
    assert [p["page"] for p in offered] == list(range(1, 7))
    assert all(sum(map(len, p["passages"])) <= 6000 for p in offered)
    assert all("special archive" in " ".join(p["passages"]) for p in offered)


async def test_baseline_run_manifest_new_folder_and_no_network_retries(tmp_path, monkeypatch):
    claims = trusted_claims(ids=["t-02"])
    archive(tmp_path, "t-02", [page()])
    monkeypatch.setattr(baseline, "EVIDENCE", tmp_path)
    attempts = []

    def factory(config):
        assert config.max_retries == 0 and config.tavily_api_key is None

        def handle(request):
            attempts.append(request)
            return httpx.Response(503)

        return NebiusProvider(config, transport=httpx.MockTransport(handle))

    args = SimpleNamespace(model="fake-model", parallel=2, output=tmp_path / "baseline")
    assert not await baseline.run(args, claims, settings=settings(), model_factory=factory)
    assert len(attempts) == 1
    manifest = json.loads((args.output / "manifest.json").read_text())
    assert manifest["recorded"] == 1 and manifest["failed"] == 1
    assert manifest["model"] == "fake-model" and manifest["revision"]
    assert manifest["token_totals"]["total_tokens"] == 0 and manifest["token_usage_missing"] == 1
    with pytest.raises(FileExistsError):
        await baseline.run(args, claims, settings=settings(), model_factory=factory)
    assert len(attempts) == 1


def test_retrieval_checks_page_site_quote_and_unavailable_quote(tmp_path):
    ids = ["t-02", "t-03", "f-01"]
    for identifier in ids:
        archive(tmp_path, identifier, [page("A  literal\nquotation.")])
    rows = [
        {"id": ids[0], "source_url": "http://www.example.org/archive/#fragment"},
        {"id": ids[1], "source_url": "https://example.org/other"},
        {"id": ids[2], "source_url": "https://different.org/archive"},
    ]
    references = {identifier: {"quote": "A literal quotation."} for identifier in ids}
    references[ids[2]]["quote"] = ""
    results = retrieval.check(rows, references, tmp_path)
    assert [r["same_page"] for r in results] == [True, False, False]
    assert [r["same_site"] for r in results] == [True, True, False]
    assert [r["quote_found"] for r in results] == [True, True, False]
    assert "does not prove the evidence is absent" in retrieval.summary(results)
    assert retrieval.page_key("https://example.org/a?q=1") != retrieval.page_key(
        "https://example.org/a?q=2"
    )


def test_scoring_handmade_batch_and_baseline_folders(tmp_path):
    rows = [
        {"id": "t-02", "verdict": "true"},
        {"id": "t-03", "verdict": "false"},
        {"id": "f-01", "verdict": "cannot_settle"},
        {"id": "f-02", "verdict": "cannot_settle"},
    ]
    folder = tmp_path / "batch"
    (folder / "claims").mkdir(parents=True)
    for identifier, outcome, verdict in [
        ("t-02", "decided", "true"),
        ("t-03", "decided", "true"),
        ("f-01", "unable_to_decide", None),
    ]:
        artifact = {
            "investigation": {
                "result": {
                    "outcome": outcome,
                    "verdict": verdict,
                    "token_usage": {"total_tokens": 100},
                }
            }
        }
        (folder / "claims" / f"{identifier}.json").write_text(json.dumps(artifact))
    # Excluded IDs must never be opened or counted.
    (folder / "claims" / "t-01.json").write_text("not valid JSON")
    result = scoring.score_run(folder, rows)
    assert (result["answered"], result["correct"], result["matches"], result["tokens"]) == (
        2,
        1,
        2,
        300,
    )
    assert result["interval"] == scoring.interval(2, 4)
    assert result["wrong"] == ["t-03 (true; expected false)"]
    assert result["decisions"]["f-02"] == "no answer"
    folder2 = tmp_path / "baseline"
    folder2.mkdir()
    (folder2 / "f-02.json").write_text(
        json.dumps(
            {
                "kind": "baseline",
                "verdict": "cannot_settle",
                "downgraded": True,
                "token_usage": {"total_tokens": 80},
            }
        )
    )
    baseline_score = scoring.score_run(folder2, rows)
    assert baseline_score["matches"] == 1 and baseline_score["downgraded"] == 1
    text = scoring.report([result, baseline_score])
    assert "2/4" in text and "4/4 answers differ" in text and "t-03 (true; expected false)" in text
    (folder / "manifest.json").write_text('{"split":"heldout"}')
    with pytest.raises(ValueError):
        scoring.score_run(folder, rows)


@pytest.mark.parametrize("tool", [baseline, retrieval, scoring, runner])
def test_tools_refuse_heldout_on_the_command_line(tool, tmp_path):
    arguments = ["--split", "heldout"]
    if tool is baseline:
        arguments += ["--model", "fake", "--output", str(tmp_path / "out")]
    elif tool is retrieval:
        arguments += ["--output", str(tmp_path / "out")]
    elif tool is scoring:
        arguments += [str(tmp_path)]
    else:
        arguments += ["--replay-evidence", str(tmp_path)]
    if tool is runner:
        assert tool.main(arguments) == 2
    else:
        with pytest.raises(SystemExit) as exc:
            tool.main(arguments)
        assert exc.value.code == 2


async def test_baseline_success_records_totals_and_label_changes_do_not_change_request(
    tmp_path, monkeypatch
):
    claims = trusted_claims(ids=["t-02", "t-03"])
    for claim in claims:
        archive(tmp_path, claim.id, [page()])
    monkeypatch.setattr(baseline, "EVIDENCE", tmp_path)
    models = []

    class Model(FakeModel):
        def __init__(self, config):
            super().__init__(
                sourced(
                    {
                        "verdict": "true",
                        "quotes": [{"page": 1, "text": "The Archive opened in 2000."}],
                        "reason": "Recorded date.",
                    }
                )
            )
            models.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    args = SimpleNamespace(model="fake-model", parallel=2, output=tmp_path / "successful")
    assert await baseline.run(args, claims, settings=settings(), model_factory=Model)
    manifest = json.loads((args.output / "manifest.json").read_text())
    assert manifest["token_totals"] == {
        "prompt_tokens": 200,
        "completion_tokens": 40,
        "total_tokens": 240,
    }
    assert manifest["recorded"] == 2 and manifest["downgraded"] == 0
    assert sum(len(model.requests) for model in models) == 2
    first_request = models[0].requests[0]
    changed = claims[0].model_copy(
        update={
            "expected_verdict": "false",
            "note": "SECRET_CHANGED_LABEL",
            "sources": [KeySource(url="https://labels.invalid/secret", shows="SECRET_QUOTE")],
        }
    )
    model = Model(settings())
    await baseline.evaluate_claim(changed, [page()], model, 30)
    for key in ("input_text", "instructions", "response_type"):
        assert model.requests[0][key] == first_request[key]


def test_scoring_retains_known_tokens_when_other_calls_have_missing_usage():
    artifact = {
        "events": [
            {"type": "task_finished", "payload": {"total_tokens": "123"}},
            {"type": "task_finished", "payload": {"total_tokens": "unknown"}},
        ]
    }
    assert scoring.token_count(artifact) == (123, True)


async def test_replay_rejects_wrong_claim_before_model_setup(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Provider settings must not be loaded for a forbidden claim")

    monkeypatch.setattr(runner.ProviderSettings, "from_environment", forbidden)
    args = SimpleNamespace(replay_evidence=tmp_path, dotenv=None, split="tuning")
    claim = trusted_claims(ids=["t-02"])[0].model_copy(update={"split": "heldout"})
    with pytest.raises(ValueError):
        await runner.run_batch(args, [claim])


def test_trusted_score_cli_keeps_77_denominator_and_refuses_to_overwrite(tmp_path, capsys):
    folder = tmp_path / "partial-baseline"
    folder.mkdir()
    (folder / "t-02.json").write_text(
        json.dumps({"kind": "baseline", "verdict": "true", "token_usage": {"total_tokens": 10}})
    )
    output = tmp_path / "report.md"
    assert scoring.main([str(folder), "--output", str(output)]) == 0
    assert "1/77" in output.read_text()
    before = output.read_text()
    assert scoring.main([str(folder), "--output", str(output)]) == 2
    assert output.read_text() == before
    (folder / "manifest.json").write_text('{"claim_ids": ["t-01"]}')
    assert scoring.main([str(folder)]) == 2
    capsys.readouterr()


@pytest.mark.parametrize(
    "quoted", ["The Archive's name is 'Museum'.", "The Archive’s name is “Museum”."]
)
def test_quote_glyphs_match_without_changing_original_answer(quoted):
    original = 'The Archive’s name is "Museum".'
    answer = baseline.Answer(
        **sourced(dict(verdict="true", quotes=[{"page": 1, "text": quoted}], reason="r"))
    )
    state = baseline.validate_answer(answer, [{"page": 1, "passages": [original]}], [original])
    assert not state["downgraded"]
    assert state["original_answer"]["quotes"][0]["text"] == quoted


@pytest.mark.parametrize(
    "quoted",
    [
        "The Archive opened in 1999.",
        "The Archive did not open in 2000.",
        "the Archive opened in 2000.",
        "The Archive opened in 20.00.",
    ],
)
def test_quote_normalization_preserves_facts_negation_case_and_numbers(quoted):
    original = "The Archive opened in 2000."
    answer = baseline.Answer(
        **sourced(dict(verdict="true", quotes=[{"page": 1, "text": quoted}], reason="r"))
    )
    state = baseline.validate_answer(answer, [{"page": 1, "passages": [original]}], [original])
    assert state["downgraded"]


@pytest.mark.parametrize("stop", ["semantic_rejection", "invalid_task_output"])
def test_rejected_final_check_is_not_scored_as_a_correct_abstention(stop):
    artifact = {
        "investigation": {
            "status": "partial",
            "stop_reason": stop,
            "result": {
                "outcome": "unable_to_decide",
                "unable_to_decide_reason": "insufficient_evidence",
            },
        }
    }
    assert scoring.decision(artifact) == "no answer"
    artifact["investigation"]["stop_reason"] = "budget_exhausted"
    assert scoring.decision(artifact) == "cannot_settle"


def test_scoring_stdout_is_utf8_under_a_legacy_windows_encoding(tmp_path):
    import os
    import subprocess

    result = subprocess.run(
        [sys.executable, str(Path(scoring.__file__)), str(tmp_path)],
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        capture_output=True,
        check=True,
    )
    assert "Wrong answers —" in result.stdout.decode("utf-8")


def test_quote_normalization_does_not_turn_inches_into_feet():
    answer = baseline.Answer(
        **sourced(
            dict(verdict="true", quotes=[{"page": 1, "text": "The height is 6'."}], reason="r")
        )
    )
    original = 'The height is 6".'
    state = baseline.validate_answer(answer, [{"page": 1, "passages": [original]}], [original])
    assert state["downgraded"]


async def test_replay_accepts_the_simple_loops_read_timeout():
    from aletheia.simple import READ_TIMEOUT_SECONDS

    async with ReplayProvider(settings()) as search:
        search.set_pages([page()])
        result = await search.extract(
            [page()["url"]], budget=budget(extract=1), timeout_seconds=READ_TIMEOUT_SECONDS
        )
        assert result.pages[0].content == page()["original_text"]


def test_sheet_scoring_maps_labels_and_scores_like_the_trusted_scorer(tmp_path, capsys):
    import csv

    import score_sheet

    from aletheia.evaluation import CLAIM_COLUMNS

    sheet = tmp_path / "claims.csv"
    base = dict.fromkeys(CLAIM_COLUMNS, "")
    labels = [
        ("s-001", "decided", "true", ""),
        ("s-002", "decided", "almost", ""),
        ("s-003", "unable_to_decide", "", "insufficient_evidence"),
    ]
    with sheet.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CLAIM_COLUMNS)
        writer.writeheader()
        for cid, outcome, verdict, reason in labels:
            writer.writerow(
                base
                | {
                    "id": cid,
                    "split": "heldout",
                    "claim": f"Claim {cid} about a public record.",
                    "case_type": "direct_fact",
                    "expected_outcome": outcome,
                    "expected_verdict": verdict,
                    "unable_reason": reason,
                }
            )
    assert score_sheet.sheet_rows(sheet) == [
        {"id": "s-001", "verdict": "true"},
        {"id": "s-002", "verdict": "false"},
        {"id": "s-003", "verdict": "cannot_settle"},
    ]
    run = tmp_path / "run"
    (run / "claims").mkdir(parents=True)

    def artifact(outcome, verdict=None):
        result = {"outcome": outcome, "verdict": verdict}
        return {"investigation": {"status": "completed", "result": result}, "events": []}

    for cid, art in [
        ("s-001", artifact("decided", "true")),
        ("s-002", artifact("decided", "true")),
        ("s-003", artifact("unable_to_decide")),
    ]:
        (run / "claims" / f"{cid}.json").write_text(json.dumps(art), encoding="utf-8")
    assert score_sheet.main([str(sheet), str(run)]) == 0
    out = capsys.readouterr().out
    assert "| run | 2/3 | 1/2 | 2/3 |" in out
    assert "s-002 (true; expected false)" in out
