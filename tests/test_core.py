import tempfile
import unittest
from math import inf, nan
from pathlib import Path

from sceneops.budgets import Budget, BudgetExceeded, BudgetLimits
from sceneops.domain import (
    ActionType,
    Approval,
    Asset,
    Incident,
    IncidentStatus,
    Pipeline,
    TimelineEvent,
    new_id,
    to_primitive,
)
from sceneops.policy import (
    ActionRequest,
    PolicyConfig,
    approval_parameters_digest,
    evaluate_action,
)
from sceneops.state_machine import InvalidTransition, transition
from sceneops.store import IncidentStore


def incident() -> Incident:
    return Incident(
        id=new_id("inc"),
        pipeline_id="pipeline-demo",
        job_id="job-demo",
        asset=Asset(
            id="asset-demo",
            name="Episode_04_ProRes.mov",
            input_uri="gs://sceneops-input/Episode_04_ProRes.mov",
            expected_duration_seconds=1800,
        ),
    )


class DomainTests(unittest.TestCase):
    def test_domain_serializes_enums(self):
        payload = to_primitive(incident())
        self.assertEqual(payload["status"], "detected")
        self.assertEqual(payload["failure_class"], "unknown")


    def test_pipeline_and_job_ownership_are_explicit(self):
        pipeline = Pipeline('pipeline-demo', 'project-demo', 'Demo')
        self.assertEqual(pipeline.project_id, 'project-demo')
        self.assertEqual(incident().pipeline_id, pipeline.id)


class StateMachineTests(unittest.TestCase):
    def test_happy_path_begins_with_investigation(self):
        item = incident()
        transition(item, IncidentStatus.INVESTIGATING)
        self.assertEqual(item.status, IncidentStatus.INVESTIGATING)

    def test_skipping_diagnosis_fails_closed(self):
        with self.assertRaises(InvalidTransition):
            transition(incident(), IncidentStatus.RECOVERING)


class PolicyTests(unittest.TestCase):
    def test_prohibited_action_is_never_allowed(self):
        item = incident()
        transition(item, IncidentStatus.INVESTIGATING)
        transition(item, IncidentStatus.DIAGNOSED)
        decision = evaluate_action(ActionRequest(ActionType.DELETE_ASSET, item))
        self.assertFalse(decision.allowed)

    def test_fallback_requires_allowlist_and_approval_by_default(self):
        item = incident()
        transition(item, IncidentStatus.INVESTIGATING)
        transition(item, IncidentStatus.DIAGNOSED)
        approval = Approval(
            id="approval-1",
            incident_id=item.id,
            action=ActionType.RETRY_FALLBACK,
            actor="operator@example.com",
        )
        request = ActionRequest(
            ActionType.RETRY_FALLBACK,
            item,
            fallback_profile="sceneops-safe-hd",
            project_id='project-demo',
            job_project_id='project-demo',
            approval=approval,
        )
        approval.parameters_digest = approval_parameters_digest(request)
        approval.max_estimated_cost = request.estimated_cost
        item.approvals.append(approval)
        decision = evaluate_action(
            request
        )
        self.assertTrue(decision.allowed)

    def test_unknown_fallback_is_denied_even_with_approval(self):
        item = incident()
        transition(item, IncidentStatus.INVESTIGATING)
        transition(item, IncidentStatus.DIAGNOSED)
        approval = Approval("approval-1", item.id, ActionType.RETRY_FALLBACK, "op")
        decision = evaluate_action(
            ActionRequest(
                ActionType.RETRY_FALLBACK,
                item,
                fallback_profile="untrusted-profile",
                project_id='project-demo',
                job_project_id='project-demo',
                approval=approval,
            ),
            PolicyConfig(),
        )
        self.assertFalse(decision.allowed)

    def test_read_only_requires_allowed_owned_project(self):
        item = incident()
        denied = evaluate_action(
            ActionRequest(
                ActionType.QUERY,
                item,
                project_id='other-project',
                job_project_id='other-project',
            )
        )
        allowed = evaluate_action(
            ActionRequest(
                ActionType.QUERY,
                item,
                project_id='project-demo',
                job_project_id='project-demo',
            )
        )
        self.assertFalse(denied.allowed)
        self.assertTrue(allowed.allowed)


class BudgetTests(unittest.TestCase):
    def test_tool_call_limit_stops_next_call(self):
        budget = Budget(BudgetLimits(max_tool_calls=1))
        budget.record_tool_call()
        with self.assertRaises(BudgetExceeded):
            budget.record_tool_call()

    def test_invalid_costs_fail_before_accounting(self):
        budget = Budget()
        for value in (-1, nan, inf, -inf, 'bad'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                budget.record_recovery(value)  # type: ignore[arg-type]
        self.assertEqual(budget.recovery_attempts, 0)
        self.assertEqual(budget.estimated_cost, 0.0)

    def test_failed_budget_record_does_not_mutate_state(self):
        budget = Budget(BudgetLimits(max_estimated_cost=1.0))
        with self.assertRaises(BudgetExceeded):
            budget.record_recovery(2.0)
        self.assertEqual(budget.recovery_attempts, 0)


class StoreTests(unittest.TestCase):
    def test_round_trip_and_append_only_timeline(self):
        with tempfile.TemporaryDirectory() as directory:
            store = IncidentStore(Path(directory) / "sceneops.db")
            item = incident()
            store.save_incident(item)
            event = TimelineEvent(
                id="event-1",
                incident_id=item.id,
                type="incident.detected",
                message="Failure detected",
            )
            store.append_event(event)
            restored = store.get_incident(item.id)
            self.assertIsNotNone(restored)
            self.assertEqual(restored.asset.name, item.asset.name)
            self.assertEqual(store.timeline(item.id)[0].message, "Failure detected")


if __name__ == "__main__":
    unittest.main()
