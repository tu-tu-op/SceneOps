import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from math import inf, nan
from pathlib import Path

from sceneops.budgets import Budget, BudgetExceeded, BudgetLimits
from sceneops.domain import (
    ActionType,
    Approval,
    IncidentStatus,
    TimelineEvent,
)
from sceneops.policy import (
    ActionRequest,
    PolicyConfig,
    approval_parameters_digest,
    evaluate_action,
)
from sceneops.scenarios import resource_saturation
from sceneops.service import IncidentService
from sceneops.store import IncidentStore
from sceneops.telemetry import LocalTelemetryProvider


class SecurityPolicyTests(unittest.TestCase):
    def setUp(self):
        self.case = resource_saturation()
        from sceneops.detection import detect_incident

        self.incident = detect_incident(self.case.telemetry, self.case.asset)
        self.incident.status = IncidentStatus.DIAGNOSED

    def request(self, **changes):
        values = {
            'action': ActionType.RETRY_SAME,
            'incident': self.incident,
            'estimated_cost': 1.0,
            'project_id': 'project-demo',
            'job_project_id': 'project-demo',
            'retry_count': 0,
            'parameters': {'profile': 'same'},
        }
        values.update(changes)
        return ActionRequest(**values)

    def recorded_approval(self, request, **changes):
        values = {
            'id': 'approval-security',
            'incident_id': self.incident.id,
            'action': request.action,
            'actor': 'operator',
            'expires_at': (
                datetime.now(timezone.utc) + timedelta(minutes=5)
            ).isoformat(),
            'parameters_digest': approval_parameters_digest(request),
            'max_estimated_cost': request.estimated_cost,
        }
        values.update(changes)
        approval = Approval(**values)
        self.incident.approvals.append(approval)
        return ActionRequest(
            **{
                **{
                    field: getattr(request, field)
                    for field in request.__dataclass_fields__
                },
                'approval': approval,
            }
        )

    def test_cross_project_reads_and_writes_fail_closed(self):
        read = self.request(
            action=ActionType.QUERY,
            project_id='other',
            job_project_id='other',
        )
        write = self.request(job_project_id='other')
        self.assertFalse(evaluate_action(read).allowed)
        self.assertFalse(evaluate_action(write).allowed)

    def test_invalid_cost_retry_and_destructive_action_fail_closed(self):
        for cost in (-1, nan, inf, -inf, 'bad'):
            with self.subTest(cost=cost):
                self.assertFalse(
                    evaluate_action(self.request(estimated_cost=cost)).allowed
                )
        self.assertFalse(evaluate_action(self.request(retry_count=2)).allowed)
        self.assertFalse(
            evaluate_action(self.request(action=ActionType.DELETE_ASSET)).allowed
        )
        with self.assertRaises(ValueError):
            ActionType('destroy_everything')

    def test_invalid_approval_variants_are_denied_without_crash(self):
        base = self.request()
        variants = (
            {'actor': ''},
            {'expires_at': 'not-a-date'},
            {
                'expires_at': (
                    datetime.now(timezone.utc) - timedelta(seconds=1)
                ).isoformat()
            },
            {'incident_id': 'wrong-incident'},
            {'parameters_digest': 'wrong-parameters'},
        )
        for changes in variants:
            self.incident.approvals.clear()
            request = self.recorded_approval(base, **changes)
            with self.subTest(changes=changes):
                self.assertFalse(evaluate_action(request).allowed)

    def test_approval_cannot_be_replayed_for_changed_parameters(self):
        approved = self.recorded_approval(self.request())
        self.assertTrue(evaluate_action(approved).allowed)
        altered = ActionRequest(
            **{
                **{
                    field: getattr(approved, field)
                    for field in approved.__dataclass_fields__
                },
                'parameters': {'profile': 'changed'},
            }
        )
        self.assertFalse(evaluate_action(altered).allowed)

    def test_budget_exhaustion_does_not_mutate_accounting(self):
        budget = Budget(BudgetLimits(max_recovery_attempts=1))
        budget.record_recovery(1)
        before = budget.snapshot()
        with self.assertRaises(BudgetExceeded):
            budget.record_recovery(1)
        self.assertEqual(budget.snapshot().recovery_attempts, before.recovery_attempts)


class PersistenceBypassTests(unittest.TestCase):
    def test_direct_status_bypass_is_denied_and_not_audited(self):
        with tempfile.TemporaryDirectory() as directory:
            store = IncidentStore(Path(directory) / 'sceneops.db')
            from sceneops.detection import detect_incident

            case = resource_saturation()
            incident = detect_incident(case.telemetry, case.asset)
            store.save_incident(incident)
            incident.status = IncidentStatus.RESOLVED
            with self.assertRaises(PermissionError):
                store.save_incident(incident)
            with self.assertRaises(ValueError):
                store.save_with_event(
                    incident,
                    TimelineEvent('fake', incident.id, 'fake', 'fake'),
                )
            self.assertEqual(
                store.get_incident(incident.id).status, IncidentStatus.DETECTED
            )
            self.assertEqual(store.timeline(incident.id), [])


if __name__ == '__main__':
    unittest.main()
