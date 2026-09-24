# Workflows

Workflows chain multiple steps — retrieval, generation, tool calls,
human approval — into a repeatable, multi-step process, run in the
background rather than inline in a chat turn.

## Running a workflow

If your organization has configured workflows, they appear under the
**Workflows** dashboard section. Start a run, provide any required
inputs, and track its progress step by step.

## Human approval steps

Some workflows pause at a defined step for a human decision before
continuing (e.g. "approve this before it's sent"). If a workflow you're
part of is waiting on your approval, you'll see it under your
notifications — see [Notifications](NOTIFICATIONS.md).

## Building a workflow

Workflow creation is a developer/admin task — see the real node types,
variable syntax, and execution-history API in
[`docs/developer/WORKFLOWS.md`](../developer/WORKFLOWS.md).
