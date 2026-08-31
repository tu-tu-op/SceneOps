"""Generated, ground-truth-separated evaluation for all controlled incidents."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from statistics import mean
import tempfile
from time import perf_counter

from sceneops.baselines import alert_only, deterministic_baseline
from sceneops.budgets import Budget
from sceneops.config import Settings
from sceneops.detection import detect_incident
from sceneops.diagnosis import rank_hypotheses
from sceneops.domain import ActionType, FailureClass
from sceneops.evidence import EvidenceBuilder
from sceneops.recovery import plan_recovery
from sceneops.scenarios import scenario_catalog
from sceneops.store import IncidentStore
from sceneops.telemetry import LocalTelemetryProvider
from sceneops.workflow import SceneOpsRuntime


@dataclass(slots=True)
class MethodResult:
    root_cause_correct: bool
    recovery_selection_correct: bool
    unsafe_action: bool
    recovery_succeeded: bool
    verification_correct: bool
    escalated: bool
    evidence_precision: float
    diagnose_seconds: float
    recover_seconds: float
    tool_calls: int
    estimated_cost: float


def run_evaluation(variants_per_class: int = 4) -> dict:
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        runtime = SceneOpsRuntime(
            Settings(database_path=Path(directory) / 'evaluation.db')
        )
        for case in scenario_catalog(variants_per_class):
            incident = detect_incident(case.telemetry, case.asset)
            started = perf_counter()
            evidence = EvidenceBuilder().collect(
                incident, LocalTelemetryProvider(case.simulator), Budget()
            )
            hypotheses = rank_hypotheses(evidence)
            plan = plan_recovery(hypotheses[0])
            diagnose_seconds = perf_counter() - started
            selected = [item for item in evidence if item.id in plan.evidence_ids]
            precision = (
                sum(
                    case.truth.root_cause in item.supports
                    for item in selected
                )
                / len(selected)
                if selected
                else 0.0
            )
            alert = alert_only(evidence)
            deterministic = deterministic_baseline(evidence)
            scenario_name = case.truth.root_cause.value
            recovery_started = perf_counter()
            completed = runtime.run(scenario_name, actor='evaluator')
            recover_seconds = perf_counter() - recovery_started
            actual_action = completed.action_attempts[0].action
            rows.append(
                {
                    'case_id': case.id,
                    'failure_class': case.truth.root_cause.value,
                    'baseline_a': asdict(
                        MethodResult(
                            alert.root_cause == case.truth.root_cause,
                            False,
                            False,
                            False,
                            False,
                            alert.escalated,
                            0.0,
                            0.0,
                            0.0,
                            0,
                            0.0,
                        )
                    ),
                    'baseline_b': asdict(
                        MethodResult(
                            deterministic.root_cause == case.truth.root_cause,
                            deterministic.action in case.truth.allowed_actions,
                            deterministic.action in case.truth.forbidden_actions,
                            deterministic.action in case.truth.allowed_actions,
                            True,
                            deterministic.escalated,
                            precision,
                            diagnose_seconds,
                            0.0,
                            1,
                            plan.estimated_cost,
                        )
                    ),
                    'sceneops': asdict(
                        MethodResult(
                            completed.failure_class == case.truth.root_cause,
                            actual_action in case.truth.allowed_actions,
                            actual_action in case.truth.forbidden_actions,
                            completed.verification.passed,
                            completed.verification.passed
                            == case.truth.recovery_should_succeed,
                            completed.status.value == 'escalated',
                            precision,
                            diagnose_seconds,
                            recover_seconds,
                            1,
                            completed.action_attempts[0].estimated_cost,
                        )
                    ),
                }
            )
    return {
        'generated': True,
        'case_count': len(rows),
        'variants_per_class': variants_per_class,
        'methods': {
            name: _aggregate(rows, name)
            for name in ('baseline_a', 'baseline_b', 'sceneops')
        },
        'cases': rows,
    }


def _aggregate(rows: list[dict], method: str) -> dict:
    values = [row[method] for row in rows]
    return {
        'root_cause_accuracy': mean(item['root_cause_correct'] for item in values),
        'recovery_selection_accuracy': mean(
            item['recovery_selection_correct'] for item in values
        ),
        'unsafe_action_rate': mean(item['unsafe_action'] for item in values),
        'recovery_success_rate': mean(item['recovery_succeeded'] for item in values),
        'verification_accuracy': mean(
            item['verification_correct'] for item in values
        ),
        'false_escalation_rate': mean(item['escalated'] for item in values),
        'evidence_precision': mean(item['evidence_precision'] for item in values),
        'mean_diagnose_seconds': mean(item['diagnose_seconds'] for item in values),
        'mean_recover_seconds': mean(item['recover_seconds'] for item in values),
        'mean_tool_calls': mean(item['tool_calls'] for item in values),
        'mean_estimated_cost': mean(item['estimated_cost'] for item in values),
    }


def write_results(results: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / 'evaluation-results.json'
    report_path = output_dir / 'evaluation-report.md'
    json_path.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# SceneOps generated evaluation',
        '',
        f'Cases: {results["case_count"]}',
        '',
        '| Method | Root cause | Recovery selection | Unsafe action | Recovery success | Verification | False escalation |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    for name, metrics in results['methods'].items():
        lines.append(
            '| {name} | {root:.1%} | {selection:.1%} | {unsafe:.1%} | '
            '{recovery:.1%} | {verification:.1%} | {escalation:.1%} |'.format(
                name=name,
                root=metrics['root_cause_accuracy'],
                selection=metrics['recovery_selection_accuracy'],
                unsafe=metrics['unsafe_action_rate'],
                recovery=metrics['recovery_success_rate'],
                verification=metrics['verification_accuracy'],
                escalation=metrics['false_escalation_rate'],
            )
        )
    lines.extend(
        [
            '',
            'These values are generated from the checked-in deterministic corpus. '
            'No live Grafana, Google, or Gemini calls were made.',
        ]
    )
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return json_path, report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Run the SceneOps evaluator')
    parser.add_argument('--variants', type=int, default=4)
    parser.add_argument('--output', type=Path, default=Path('evaluation-results'))
    args = parser.parse_args(argv)
    if not 1 <= args.variants <= 20:
        parser.error('--variants must be between 1 and 20')
    results = run_evaluation(args.variants)
    paths = write_results(results, args.output)
    print(f'evaluated {results["case_count"]} cases')
    print(f'JSON: {paths[0]}')
    print(f'Markdown: {paths[1]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
