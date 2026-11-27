# Moving the Agent Loop Out of Your Backend with Claude Managed Agents

If you've ever built an agent that runs code or edits files on top of a standard chat API, you know how repetitive the backend loop gets. Standard model APIs are built for synchronous request-response turns, where you send a prompt, parse a tool call, run commands in your own container, and repeat until the model finishes. Real engineering work doesn't happen in single turns, and keeping a worker alive across 20 steps while managing context windows and connection drops gets messy fast.

In April 2026, Anthropic launched **Claude Managed Agents** (`managed-agents-2026-04-01`) to move that execution loop and container lifecycle onto their infrastructure. Instead of wiring up your own sandbox runner, you define an agent and a container environment, start a stateful session, and listen to an event stream.

## Why the runtime loop and workspace belong together

A reasoning loop without a filesystem can't produce real artifacts, and a container without an event-driven loop still forces your backend to babysit every tool call. Managed agents pairs both inside one architecture across four primitives:

1. **Agent:** A versioned config holding the model, system instructions, built-in shell and file tools, and optional MCP servers or skills. You can define it in a markdown file (`agent.md`) or through the API.
2. **Environment:** A reusable container template. You can run on Anthropic's hosted Linux image with common developer tools pre-installed, or connect your own self-hosted worker.
3. **Session:** A live runtime instance that pairs one agent version with one environment, keeping the working directory and event history alive on Anthropic's servers.
4. **Events:** An asynchronous stream where your app sends prompts or mid-run interrupts over HTTP and reads tool executions, status updates, and replies over Server-Sent Events (SSE).

Because the loop runs inside Anthropic's control plane rather than a blocking HTTP worker on your backend, mid-course interrupts work naturally and dropped connections don't kill an in-flight job. You simply reconnect with the session ID.

## Stateful sessions and infrastructural guardrails

What makes managed agents practical for multi-step work is how a run wraps up. Instead of destroying the container the moment a prompt finishes, the session simply transitions to `idle`. Your cloned repos, intermediate scripts, and generated files stay intact on disk, so sending a follow-up request takes zero setup and picks up right where it left off.

Of course, giving an AI model shell access inside a container comes with real security risks. Relying purely on system prompts to stop a malicious `README.md` or commit message from leaking secrets doesn't scale in production. Managed agents locks down the container at the infrastructure layer instead:

* **Network allowlists:** Outbound traffic is restricted to an explicit list of approved domains at the container boundary, so cloning a GitHub repo doesn't open the door to arbitrary outbound requests.
* **Credential vaults:** API tokens live in an external vault rather than inside container environment variables. A proxy attaches the auth header to matching outbound requests automatically, so the model never actually sees the secret.

## Pricing and spend controls

There are no platform fees or minimums. Usage bills across model tokens at standard API rates ($2 / $10 per million input/output tokens for Sonnet 5.5; $4 / $20 for Opus 5.5), built-in web search at $10 per 1,000 searches, and active container runtime at **$0.08 per session-hour**.

Container runtime is metered to the millisecond only while the session is actively running. Sitting in `idle` costs nothing, so keeping a warm workspace ready for follow-up turns carries zero compute penalty. For a 20-second coding workflow, the container overhead adds less than a tenth of a cent, and you can attach a configured per-session budget that pauses execution if hit without destroying your sandbox.

## In practice: generating commit-cited release notes from git history

To see how these pieces hold up in practice, I built a Python CLI (`release-notes-agent`) that takes a public GitHub URL and a tag range and outputs a categorized `RELEASE_NOTES.md`. Setup is separated from execution: one script registers a versioned Sonnet 5.5 agent from `agent.md` (with web search turned off so the model stays strictly grounded in the repo) and provisions an environment locked solely to `github.com` and `*.githubusercontent.com`.

Running it against `fastapi/fastapi` across tags `0.162.0..0.165.0` executed **83 shell and file calls across 12 releases** inside a single session with a configured $0.50 budget, with zero retry or context-compaction code in my local Python script. Because `agent.md` tells the model to inspect actual diffs and check every hash against `git log`, it cross-checked each cited hash against `git log` before including it and surfaced real breaking changes, including Python 3.10 support being dropped, Starlette bumping to `>=1.6.0`, and new request body and form size limits.

Once the session hit `idle`, my CLI downloaded `RELEASE_NOTES.md` straight from the scoped session Files API. And because the container stays warm while idle, sending a follow-up prompt ("Rewrite the breaking changes as a Slack update") ran right away against the already-cloned repo.

## Honest trade-offs and where it fits

Even though managed agents takes a lot of container plumbing off your plate, there are a few practical limits to keep in mind before using it in production:

* **Backend only:** It handles the execution loop and sandbox, not the UI. If your product needs a chat widget, file uploader, or inline approval prompts, you still build that frontend yourself.
* **Control-plane trade-offs:** Unlike self-hosted frameworks such as LangGraph or the open-source Claude Agent SDK, your session state and credential vaults live on Anthropic's control plane. Self-hosted managed agents entered private beta on November 12, 2026 for teams that need on-prem execution, but standard public beta sessions do not yet support Zero Data Retention (ZDR), HIPAA, or Batch pricing.
* **Cold-start latency:** Spinning up a container and opening an SSE stream adds startup overhead. If you are building synchronous Q&A or single-turn JSON extraction that does not need a filesystem or shell, the stateless Messages API is still faster and simpler.

Overall, managed agents is overkill for basic request-response chat, but a strong fit for asynchronous background workflows (like release notes, repo audits, or test fixes) where you want an isolated Linux environment, strict network egress, and resumable sessions without maintaining the runner yourself.
