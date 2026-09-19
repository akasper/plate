"""
Regression tests for #988: Always prefer host-native look-and-feel for agent-to-user
interactive prompts.

These tests ensure that the universal host-native interaction principle is present
in shipped guidance, persona, and template artifacts.
"""

import unittest
from pathlib import Path


class HostNativeInteractionTests(unittest.TestCase):
    def test_universal_principle_in_agent_guidance(self):
        """Regression test for #988: A universal host-native interaction principle
        must be documented in agent_guidance.py and included in the guidance sections."""
        from plate_core.agent_guidance import (
            HOST_NATIVE_INTERACTION_PRINCIPLE,
            get_agent_guidance_sections,
        )

        # Verify the principle exists and has core content
        self.assertIn("Host-Native Interactive Prompt Preference", HOST_NATIVE_INTERACTION_PRINCIPLE)
        self.assertIn("must prefer the host's native look-and-feel", HOST_NATIVE_INTERACTION_PRINCIPLE)
        self.assertIn("over free-form prose questions", HOST_NATIVE_INTERACTION_PRINCIPLE)

        # Verify host matrix is documented
        self.assertIn("Copilot CLI", HOST_NATIVE_INTERACTION_PRINCIPLE)
        self.assertIn("Grok Build", HOST_NATIVE_INTERACTION_PRINCIPLE)
        self.assertIn("ask_user_question", HOST_NATIVE_INTERACTION_PRINCIPLE)
        self.assertIn("gh plate qanda", HOST_NATIVE_INTERACTION_PRINCIPLE)
        self.assertIn("Fallback", HOST_NATIVE_INTERACTION_PRINCIPLE)

        # Verify scope is universal (not Q&A-only)
        self.assertIn("whenever the agent solicits structured human judgment", HOST_NATIVE_INTERACTION_PRINCIPLE)
        self.assertIn("not only when processing open `Question` issues", HOST_NATIVE_INTERACTION_PRINCIPLE)

        # Verify it's included in guidance sections
        sections = get_agent_guidance_sections()
        self.assertIn("host_native_interaction", sections)
        self.assertEqual(sections["host_native_interaction"], HOST_NATIVE_INTERACTION_PRINCIPLE)

    def test_qanda_guidance_references_host_matrix(self):
        """Regression test for #988: QANDA_CURIOSITY_GUIDANCE must reference the
        host-native principle and include the host matrix."""
        from plate_core.agent_guidance import QANDA_CURIOSITY_GUIDANCE

        # Verify reference to the principle
        self.assertIn("host-native preference", QANDA_CURIOSITY_GUIDANCE.lower())
        self.assertIn("HOST_NATIVE_INTERACTION_PRINCIPLE", QANDA_CURIOSITY_GUIDANCE)

        # Verify host matrix is present
        self.assertIn("Copilot CLI", QANDA_CURIOSITY_GUIDANCE)
        self.assertIn("Grok Build", QANDA_CURIOSITY_GUIDANCE)
        self.assertIn("ask_user_question", QANDA_CURIOSITY_GUIDANCE)

        # Verify enforcement language
        self.assertIn("consistently default to native TUI", QANDA_CURIOSITY_GUIDANCE)
        self.assertIn("Do not require user reminders", QANDA_CURIOSITY_GUIDANCE)

    def test_template_agents_md_question_loop_native_ui(self):
        """Regression test for #988: template_payload/AGENTS.md Question loop
        must instruct agents to use host-native look-and-feel, not chat-only Q&A."""
        template_agents = Path("src/plate_core/template_payload/AGENTS.md")
        self.assertTrue(template_agents.exists(), "Template AGENTS.md must exist")

        with open(template_agents, encoding="utf-8") as f:
            content = f.read()

        # Find the Question work loop section
        self.assertIn("**Question**", content)

        # Verify host-native language is in the Question loop
        # The guidance should appear in step 2 (presentation step)
        self.assertIn("host-native look-and-feel", content)
        self.assertIn("Copilot CLI native TUI", content)
        self.assertIn("Grok Build `ask_user_question`", content)
        self.assertIn("Fall back to `gh plate qanda`", content)
        self.assertIn("Do not wait for the user to say", content)

    def test_template_agents_md_interactive_epic_planning_native_ui(self):
        """Regression test for #988: template_payload/AGENTS.md Interactive Epic Planning
        section must instruct agents to use host-native look-and-feel."""
        template_agents = Path("src/plate_core/template_payload/AGENTS.md")
        self.assertTrue(template_agents.exists(), "Template AGENTS.md must exist")

        with open(template_agents, encoding="utf-8") as f:
            content = f.read()

        # Find the Interactive Epic Planning section
        self.assertIn("## Interactive Epic Planning", content)

        # Verify host-native language is in the planning section
        self.assertIn("Present questions using host-native look-and-feel", content)
        self.assertIn("rather than free-form chat", content)

    def test_all_guidance_sections_include_host_native_principle(self):
        """Regression test for #988: The host_native_interaction principle must be
        available as a guidance section for MCP tools and personas to inject."""
        from plate_core.agent_guidance import get_agent_guidance_sections

        sections = get_agent_guidance_sections()

        # Verify host_native_interaction is a first-class section
        self.assertIn("host_native_interaction", sections)

        # Verify it comes before or alongside qanda_curiosity
        # (order matters for injection priority)
        section_keys = list(sections.keys())
        self.assertIn("host_native_interaction", section_keys)
        self.assertIn("qanda_curiosity", section_keys)

        # Both should be present
        self.assertTrue(len(sections["host_native_interaction"]) > 100)
        self.assertTrue(len(sections["qanda_curiosity"]) > 100)

    def test_host_matrix_coverage(self):
        """Regression test for #988: The host matrix must document Copilot CLI,
        Grok Build, other hosts, and fallback (gh plate qanda / CLI)."""
        from plate_core.agent_guidance import HOST_NATIVE_INTERACTION_PRINCIPLE

        required_hosts = [
            "Copilot CLI",
            "Grok Build",
            "ask_user_question",
            "gh plate qanda",
            "Other hosts",
        ]

        for host in required_hosts:
            self.assertIn(
                host,
                HOST_NATIVE_INTERACTION_PRINCIPLE,
                f"Host matrix must document '{host}'",
            )

    def test_scope_is_universal_not_qanda_only(self):
        """Regression test for #988: The principle must apply universally to all
        agent→user interactive prompts, not only Curiosity/Q&A mode."""
        from plate_core.agent_guidance import HOST_NATIVE_INTERACTION_PRINCIPLE

        # Verify universal scope examples
        self.assertIn("Epic planning", HOST_NATIVE_INTERACTION_PRINCIPLE)
        self.assertIn("blocking questions", HOST_NATIVE_INTERACTION_PRINCIPLE)
        self.assertIn("What-next", HOST_NATIVE_INTERACTION_PRINCIPLE)
        self.assertIn("confirmations", HOST_NATIVE_INTERACTION_PRINCIPLE)

        # Verify explicit non-Q&A-only language
        self.assertIn(
            "not only when processing open `Question` issues",
            HOST_NATIVE_INTERACTION_PRINCIPLE,
        )

    def test_enforcement_no_user_reminder_required(self):
        """Regression test for #988: Agents must not wait for the user to say
        "use the TUI" or similar—they must default to native first."""
        from plate_core.agent_guidance import HOST_NATIVE_INTERACTION_PRINCIPLE

        self.assertIn(
            'must **not** wait for the user to say "use the TUI"',
            HOST_NATIVE_INTERACTION_PRINCIPLE,
        )
        self.assertIn("Default to native first", HOST_NATIVE_INTERACTION_PRINCIPLE)


if __name__ == "__main__":
    unittest.main()
