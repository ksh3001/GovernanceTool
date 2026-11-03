"""Headless runs of the bundled sample apps, used to record and check the demo replay cache."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .agreement import Agreement, compute_agreement
from .answer_key import load_answer_key
from .assess import run_assessment
from .config import ROOT
from .controls import load_controls
from .findings import FindingsFile
from .ingest import ingest
from .llm import LLMClient
from .questionnaire import Questionnaire
from .tiers import control_applicability, load_classifier

FRAMEWORK = "eu_ai_act"
SAMPLES_DIR = ROOT / "samples"
DEMO_CACHE = ROOT / "demo" / "replay_cache.jsonl"


@dataclass
class SampleRun:
    name: str
    findings: FindingsFile
    agreement: Agreement | None = None


@dataclass
class DemoReport:
    runs: list[SampleRun] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def sample_folders(samples_dir: Path = SAMPLES_DIR) -> list[Path]:
    return sorted(p.parent for p in Path(samples_dir).glob("*/answer_key.yaml"))


def assess_sample(folder: Path, llm: LLMClient, packs_dir: Path | None = None) -> SampleRun:
    """Assess one sample app from its local folder, the same way the 'Load sample apps' button sets it up."""
    pack = (packs_dir or ROOT / "control_packs") / FRAMEWORK
    key = load_answer_key(folder / "answer_key.yaml")
    q = Questionnaire.model_validate_json((folder / "questionnaire.json").read_text(encoding="utf-8"))
    tier = load_classifier(pack)(q)
    controls = load_controls(pack)
    findings = run_assessment(
        app_id=folder.name, framework=FRAMEWORK, controls=controls,
        applicability=control_applicability(controls, tier.tier, q), q=q, tier=tier,
        ingested=ingest(folder / "repo", folder / "docs"), llm=llm)
    agreement = compute_agreement(findings, key, tier.tier) if key.framework == FRAMEWORK else None
    return SampleRun(name=key.app_name, findings=findings, agreement=agreement)


def run_samples(llm: LLMClient, folders: list[Path] | None = None) -> DemoReport:
    """Assess every sample. A replay miss or configuration error is reported, not raised."""
    report = DemoReport()
    for folder in folders if folders is not None else sample_folders():
        try:
            report.runs.append(assess_sample(folder, llm))
        except RuntimeError as exc:
            report.problems.append(f"{folder.name}: {exc}")
    return report


def describe(report: DemoReport) -> list[str]:
    """Plain-text summary: one line per control and the agreement with the expert key."""
    lines: list[str] = []
    for run in report.runs:
        f = run.findings
        lines.append(f"\n{run.name}: tier {f.tier_label or '-'} · mode {f.llm_mode}")
        for item in f.findings:
            flag = f"  [{'; '.join(item.flags)}]" if item.flags else ""
            lines.append(f"  {item.article:<14} {item.status:<22} {len(item.citations)} citation(s) "
                         f"verification {item.verification or '-'}{flag}")
        a = run.agreement
        if a:
            lines.append(f"  Agreement with the key: {a.assessed_agreed} of {a.assessed_total} model-assessed controls · "
                         f"tier {'match' if a.tier_match else 'MISMATCH'}"
                         + ("" if a.confirmed_by_expert else " · DRAFT KEY, not expert-confirmed"))
            for t in a.traps:
                lines.append(f"  Trap case {t.control_id}: {'detected' if t.detected else 'NOT detected'}")
    for problem in report.problems:
        lines.append(f"\nPROBLEM {problem}")
    return lines
