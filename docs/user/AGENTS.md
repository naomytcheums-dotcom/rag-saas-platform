# Agents

There are two distinct kinds of agent in this platform — see
[Autonomous Agents](../advanced/AUTONOMOUS_AGENTS.md) for the difference
in depth. This page covers the everyday, chat-facing kind.

## Configured agents

An agent is a persona: a system prompt, a set of tools it's allowed to
use, and model configuration. If your organization has set one up
(e.g. "Support Agent", "Sales Assistant"), select it from the agent
picker when starting a new conversation in [Chat](CHAT.md).

## Autonomous agents

Autonomous agents are different: instead of responding to one chat
turn, they plan and execute a multi-step goal on their own (e.g.
"research competitor X and summarize pricing"), with visible progress
per step. If your organization has this feature enabled, you'll find it
under its own **Autonomous Agents** section in the dashboard rather than
inside Chat. See [Autonomous Agents](../advanced/AUTONOMOUS_AGENTS.md)
and [`docs/autonomous/OVERVIEW.md`](../autonomous/OVERVIEW.md).

## Creating an agent

Creating and configuring agents is an admin/builder task — see
[Custom Tools](../developer/CUSTOM_TOOLS.md) for the developer-facing
setup.
