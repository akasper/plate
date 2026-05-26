package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:   "gh-plate",
	Short: "A gh CLI extension for PLATE-based workflows",
	Long: `gh-plate is a GitHub CLI extension that provides tooling for
PLATE (Process Lifecycle Agentic Task Engine) based project workflows.`,
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Fprintln(os.Stdout, "gh-plate: use --help to see available commands")
	},
}

// Execute runs the root command.
func Execute() {
	if err := rootCmd.Execute(); err != nil {
		os.Exit(1)
	}
}
