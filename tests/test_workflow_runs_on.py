import unittest

from plate_core.workflow_runs_on import (
    DEFAULT_RUNS_ON,
    LINUX_RUNS_ON_UNTRUSTED_CONDITION,
    LINUX_RUNS_ON_VAR_EXPRESSION,
    PLATE_RUNS_ON_INPUT_EXPRESSION,
    choose_runs_on,
    composite_action_yaml,
    has_idle_runner,
    is_hosted_only,
    is_hosted_runner_label,
    parse_runs_on_var,
    resolve_linux_runs_on,
    runner_is_idle_match,
)


class WorkflowRunsOnTests(unittest.TestCase):
    def test_parse_defaults_to_ubuntu_latest(self):
        self.assertEqual(parse_runs_on_var(None), ["ubuntu-latest"])
        self.assertEqual(parse_runs_on_var(""), ["ubuntu-latest"])
        self.assertEqual(parse_runs_on_var('""'), ["ubuntu-latest"])

    def test_parse_plain_runner_label(self):
        self.assertEqual(parse_runs_on_var("ubicloud-standard-2"), ["ubicloud-standard-2"])
        self.assertEqual(parse_runs_on_var("self-hosted"), ["self-hosted"])

    def test_parse_json_array_and_string(self):
        self.assertEqual(
            parse_runs_on_var('["self-hosted", "plate-local"]'),
            ["self-hosted", "plate-local"],
        )
        self.assertEqual(parse_runs_on_var('"windows-latest"'), ["windows-latest"])

    def test_parse_numeric_plain_label(self):
        self.assertEqual(parse_runs_on_var("123"), ["123"])
        self.assertEqual(parse_runs_on_var("42"), ["42"])

    def test_parse_rejects_invalid_json_values(self):
        self.assertEqual(parse_runs_on_var("{}"), ["ubuntu-latest"])
        self.assertEqual(parse_runs_on_var("true"), ["ubuntu-latest"])
        self.assertEqual(parse_runs_on_var('["ok", ""]'), ["ubuntu-latest"])

    def test_composite_action_parse_emits_warning_on_invalid_json(self):
        yaml_text = composite_action_yaml()
        self.assertIn("core.warning", yaml_text)
        self.assertIn("PLATE_RUNS_ON must be a runner label", yaml_text)
        self.assertNotIn("PLATE_RUNS_ON parse failed", yaml_text)

    def test_hosted_only_detection(self):
        self.assertTrue(is_hosted_only(["ubuntu-latest"]))
        self.assertTrue(is_hosted_runner_label("ubicloud-standard-2"))
        self.assertTrue(is_hosted_only(["ubicloud-standard-2"]))
        self.assertFalse(is_hosted_only(["self-hosted", "plate-local"]))

    def test_linux_runs_on_var_expression_documents_variables(self):
        self.assertIn("vars.CI_RUNS_ON", LINUX_RUNS_ON_VAR_EXPRESSION)
        self.assertIn("vars.PLATE_RUNS_ON", LINUX_RUNS_ON_VAR_EXPRESSION)

    def test_linux_runs_on_var_expression_has_json_and_fork_guard(self):
        self.assertIn("github.event.repository.private", LINUX_RUNS_ON_VAR_EXPRESSION)
        self.assertIn("startsWith(", LINUX_RUNS_ON_VAR_EXPRESSION)
        self.assertIn("fromJSON(", LINUX_RUNS_ON_VAR_EXPRESSION)
        self.assertIn(LINUX_RUNS_ON_UNTRUSTED_CONDITION, LINUX_RUNS_ON_VAR_EXPRESSION)
        self.assertTrue(LINUX_RUNS_ON_VAR_EXPRESSION.startswith("${{ "))
        self.assertTrue(LINUX_RUNS_ON_VAR_EXPRESSION.endswith(" }}"))
        # The short probe input expression is intentionally different and unchanged.
        self.assertEqual(
            PLATE_RUNS_ON_INPUT_EXPRESSION,
            "${{ vars.CI_RUNS_ON || vars.PLATE_RUNS_ON }}",
        )

    def test_resolve_linux_runs_on_plain_label_passes_through(self):
        self.assertEqual(
            resolve_linux_runs_on(
                "ubicloud-standard-2",
                None,
                repository_private=True,
                pr_head_full_name=None,
                repository="acme/app",
            ),
            "ubicloud-standard-2",
        )
        self.assertEqual(
            resolve_linux_runs_on(
                "plate-local",
                None,
                repository_private=True,
                pr_head_full_name=None,
                repository="acme/app",
            ),
            "plate-local",
        )

    def test_resolve_linux_runs_on_decodes_json(self):
        self.assertEqual(
            resolve_linux_runs_on(
                None,
                '["self-hosted", "plate-local"]',
                repository_private=True,
                pr_head_full_name=None,
                repository="acme/app",
            ),
            ["self-hosted", "plate-local"],
        )
        self.assertEqual(
            resolve_linux_runs_on(
                '"ubuntu-24.04"',
                None,
                repository_private=True,
                pr_head_full_name=None,
                repository="acme/app",
            ),
            "ubuntu-24.04",
        )

    def test_resolve_linux_runs_on_fork_and_public_guard(self):
        array = '["self-hosted", "plate-local"]'
        self.assertEqual(
            resolve_linux_runs_on(
                None,
                array,
                repository_private=True,
                pr_head_full_name="evil/plate",
                repository="acme/app",
            ),
            "ubuntu-latest",
        )
        self.assertEqual(
            resolve_linux_runs_on(
                None,
                array,
                repository_private=False,
                pr_head_full_name=None,
                repository="acme/app",
            ),
            "ubuntu-latest",
        )
        self.assertEqual(
            resolve_linux_runs_on(
                None,
                array,
                repository_private=None,
                pr_head_full_name=None,
                repository="acme/app",
            ),
            "ubuntu-latest",
        )
        self.assertEqual(
            resolve_linux_runs_on(
                None,
                array,
                repository_private=True,
                pr_head_full_name="acme/app",
                repository="acme/app",
            ),
            ["self-hosted", "plate-local"],
        )

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
        self.assertIn("github-token:", yaml_text)
        self.assertIn("inputs.github-token || github.token", yaml_text)
        self.assertNotIn("vars.", yaml_text)

    def test_composite_action_probe_falls_back_on_api_errors(self):
        yaml_text = composite_action_yaml()
        self.assertIn("catch (err)", yaml_text)
        self.assertIn("core.warning", yaml_text)
        self.assertIn("return null", yaml_text)

    def test_composite_action_treats_ubicloud_as_hosted(self):
        yaml_text = composite_action_yaml()
        self.assertIn("ubicloud-", yaml_text)
        self.assertIn("isHostedLabel", yaml_text)


if __name__ == "__main__":
    unittest.main()
