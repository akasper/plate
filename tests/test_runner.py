import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from plate_core.cli import main
from plate_core.runner import (
    PUBLIC_REPO_ERROR,
    SHARED_RUNNER_LABEL,
    apply_runner_add,
    apply_runner_remove,
    get_runner_status,
    plan_runner_add,
    plan_runner_remove,
    run_runner_doctor,
    runner_state_path,
    save_runner_state,
)


class RunnerModuleTests(unittest.TestCase):
    def _private_client(self, runners=None):
        client = MagicMock()
        client.api.side_effect = lambda endpoint, method="GET", fields=None, **_: {
            "private": True,
            "runners": runners or [],
            "token": "reg-token",
        }
        return client

    def _public_client(self):
        client = MagicMock()
        client.api.return_value = {"private": False}
        return client

    def test_add_dry_run_private_repo(self):
        report = plan_runner_add("acme/private-app", client=self._private_client())
        self.assertTrue(report.ok)
        self.assertTrue(report.dry_run)
        self.assertIn(SHARED_RUNNER_LABEL, report.labels)
        self.assertTrue(any(a["action"] == "fetch_registration_token" for a in report.actions))

    def test_add_refuses_public_repo(self):
        report = plan_runner_add("acme/public-app", client=self._public_client())
        self.assertFalse(report.ok)
        self.assertEqual(report.error, PUBLIC_REPO_ERROR)

    def test_add_apply_writes_state_without_config_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = apply_runner_add(
                "acme/private-app",
                repo_root=tmp,
                os_label="linux",
                client=self._private_client(),
            )
            self.assertTrue(report.ok)
            self.assertFalse(report.dry_run)
            state_path = runner_state_path(tmp)
            self.assertTrue(state_path.is_file())
            state = json.loads(state_path.read_text())
            self.assertEqual(state["repo"], "acme/private-app")
            self.assertEqual(state["labels"], [SHARED_RUNNER_LABEL, "linux"])
            self.assertTrue(state["ephemeral"])

    def test_status_lists_runners(self):
        runners = [
            {
                "id": 7,
                "name": "local-1",
                "status": "online",
                "busy": False,
                "labels": [{"name": SHARED_RUNNER_LABEL}, {"name": "linux"}],
            }
        ]
        client = self._private_client(runners=runners)

        def api(endpoint, method="GET", **kwargs):
            if endpoint.endswith("/actions/runners"):
                return {"runners": runners}
            return {"private": True}

        client.api.side_effect = api
        report = get_runner_status(repo="acme/private-app", client=client)
        self.assertTrue(report.ok)
        self.assertEqual(len(report.runners), 1)
        self.assertEqual(report.runners[0].status, "online")
        self.assertFalse(report.runners[0].busy)

    def test_remove_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_runner_state(
                tmp,
                {"repo": "acme/private-app", "labels": [SHARED_RUNNER_LABEL, "linux"], "ephemeral": True},
            )
            report = plan_runner_remove(repo_root=tmp, client=self._private_client())
            self.assertTrue(report.ok)
            self.assertTrue(report.dry_run)

    def test_remove_apply_deletes_and_clears_state(self):
        runners = [{"id": 9, "name": "r1", "status": "offline", "busy": False, "labels": []}]

        def api(endpoint, method="GET", **kwargs):
            if endpoint.endswith("/actions/runners"):
                return {"runners": runners}
            if endpoint.endswith("/remove-token"):
                return {"token": "remove-token"}
            return {"private": True}

        client = MagicMock()
        client.api.side_effect = api

        with tempfile.TemporaryDirectory() as tmp:
            save_runner_state(tmp, {"repo": "acme/private-app", "labels": [SHARED_RUNNER_LABEL, "linux"], "ephemeral": True})
            report = apply_runner_remove(repo_root=tmp, client=client, subprocess_runner=lambda *a, **k: (0, "", ""))
            self.assertTrue(report.ok)
            self.assertEqual(report.removed_runner_ids, [9])
            self.assertFalse(runner_state_path(tmp).is_file())

    def test_doctor_passes_with_state_and_scopes(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_runner_state(
                tmp,
                {
                    "repo": "acme/private-app",
                    "labels": [SHARED_RUNNER_LABEL, "linux"],
                    "ephemeral": True,
                    "isolation": {"non_admin_user": True, "no_personal_files_access": True},
                },
            )

            def gh_status(args, **kwargs):
                return 0, "Token scopes: repo, read:org\n", ""

            report = run_runner_doctor(
                repo_root=tmp,
                client=self._private_client(),
                subprocess_runner=gh_status,
                service_probe=lambda: True,
            )
            self.assertTrue(report.ok)
            ids = {c.id for c in report.checks}
            self.assertIn("labels", ids)
            self.assertIn("token_scopes", ids)
            self.assertIn("service", ids)

    def test_cli_runner_guidance_no_subcommand(self):
        from plate_core.cli import RUNNER_ADOPTER_DOC, main

        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["runner", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["doc"], RUNNER_ADOPTER_DOC)
        self.assertIn("add", payload["subcommands_planned"])

    def test_cli_add_json_dry_run(self):
        from plate_core.runner import RunnerAddReport

        with patch("plate_core.cli.plan_runner_add") as mock_plan:
            mock_plan.return_value = RunnerAddReport(
                ok=True,
                dry_run=True,
                repo="acme/private-app",
                labels=[SHARED_RUNNER_LABEL, "linux"],
                actions=[{"action": "fetch_registration_token", "state": "planned"}],
            )
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["runner", "add", "acme/private-app", "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue().strip())
            self.assertTrue(payload["dry_run"])


if __name__ == "__main__":
    unittest.main()
