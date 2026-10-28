import unittest

from plate_core.workflow_runs_on import (
    DEFAULT_RUNS_ON,
    choose_runs_on,
    composite_action_yaml,
    has_idle_runner,
    is_hosted_only,
    parse_runs_on_var,
    runner_is_idle_match,
)


class WorkflowRunsOnTests(unittest.TestCase):
    def test_parse_defaults_to_ubuntu_latest(self):
        self.assertEqual(parse_runs_on_var(None), ["ubuntu-latest"])
        self.assertEqual(parse_runs_on_var(""), ["ubuntu-latest"])
        self.assertEqual(parse_runs_on_var("not-json"), ["ubuntu-latest"])

    def test_parse_json_array_and_string(self):
        self.assertEqual(
            parse_runs_on_var('["self-hosted", "plate-local"]'),
            ["self-hosted", "plate-local"],
        )
        self.assertEqual(parse_runs_on_var('"windows-latest"'), ["windows-latest"])

    def test_hosted_only_detection(self):
        self.assertTrue(is_hosted_only(["ubuntu-latest"]))
        self.assertFalse(is_hosted_only(["self-hosted", "plate-local"]))

    def test_runner_idle_match_requires_online_not_busy(self):
        runner = {
            "status": "online",
            "busy": False,
            "labels": [{"name": "self-hosted"}, {"name": "plate-local"}],
        }
        self.assertTrue(
            runner_is_idle_match(runner, ["self-hosted", "plate-local"])
        )
        busy = {**runner, "busy": True}
        self.assertFalse(runner_is_idle_match(busy, ["self-hosted", "plate-local"]))

    def test_choose_public_repo_always_hosted(self):
        chosen = choose_runs_on(
            plate_runs_on_var='["self-hosted", "plate-local"]',
            is_private_repo=False,
            is_fork_pull_request=False,
            runners=[{"status": "online", "busy": False, "labels": [{"name": "self-hosted"}]}],
        )
        self.assertEqual(chosen, list(DEFAULT_RUNS_ON))

    def test_choose_fork_pr_always_hosted(self):
        chosen = choose_runs_on(
            plate_runs_on_var='["self-hosted", "plate-local"]',
            is_private_repo=True,
            is_fork_pull_request=True,
            runners=[],
        )
        self.assertEqual(chosen, list(DEFAULT_RUNS_ON))

    def test_choose_local_when_idle_runner_present(self):
        runners = [
            {
                "status": "online",
                "busy": False,
                "labels": [
                    {"name": "self-hosted"},
                    {"name": "plate-local"},
                    {"name": "Linux"},
                ],
            }
        ]
        chosen = choose_runs_on(
            plate_runs_on_var='["self-hosted", "plate-local"]',
            is_private_repo=True,
            is_fork_pull_request=False,
            runners=runners,
        )
        self.assertEqual(chosen, ["self-hosted", "plate-local"])

    def test_choose_fallback_when_no_idle_runner(self):
        runners = [
            {
                "status": "online",
                "busy": True,
                "labels": [{"name": "self-hosted"}, {"name": "plate-local"}],
            }
        ]
        chosen = choose_runs_on(
            plate_runs_on_var='["self-hosted", "plate-local"]',
            is_private_repo=True,
            is_fork_pull_request=False,
            runners=runners,
        )
        self.assertEqual(chosen, list(DEFAULT_RUNS_ON))

    def test_has_idle_runner_helper(self):
        runners = [
            {"status": "offline", "busy": False, "labels": [{"name": "plate-local"}]},
            {
                "status": "online",
                "busy": False,
                "labels": [{"name": "plate-local"}, {"name": "self-hosted"}],
            },
        ]
        self.assertTrue(has_idle_runner(runners, ["plate-local"]))

    def test_composite_action_declares_runs_on_output(self):
        yaml_text = composite_action_yaml()
        self.assertIn("PLATE select runs-on", yaml_text)
        self.assertIn("runs_on:", yaml_text)
        self.assertIn("listSelfHostedRunnersForRepo", yaml_text)
        self.assertIn("inputs.plate-runs-on", yaml_text)
        self.assertNotIn("vars.", yaml_text)


if __name__ == "__main__":
    unittest.main()
