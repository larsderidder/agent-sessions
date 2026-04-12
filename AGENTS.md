# AGENTS

Repository-local completion policy for `agent-sessions`.

After finishing code changes in this repo, the default expectation is to:

1. Run the relevant local tests and formatting checks.
2. Validate the change against actual client installs in isolation when the work
   touches provider integrations.
3. Verify or wait for CI to pass before treating the change as complete.
4. Publish the package once tests and CI are green and the release path is ready.
5. Distribute the updated package across the fleet when access and rollout
   tooling are available.
6. Restart the Tether stack everywhere after fleet rollout and verify health.

If any step is blocked by missing credentials, host access, client fixtures, CI
permissions, or release controls, record the blocker explicitly in the final
handoff instead of silently skipping it.
