# release-notes-agent

A Python CLI that generates commit-cited release notes from any public GitHub repository. Pass it a repo URL and a commit or tag range (for example, `0.162.0..0.165.0`), and it clones the repo inside a sandboxed Linux container, inspects actual code diffs alongside `git log`, and writes a categorized `RELEASE_NOTES.md` file.

Instead of running a local Docker container or babysitting a custom `while True` tool loop, this project delegates the entire runtime to **Claude Managed Agents** (`managed-agents-2026-04-01`). Your local CLI simply kicks off an asynchronous session, streams live execution events, and pulls the finished artifact down once the container finishes.

* **Architecture write-up:** [Moving the Agent Loop Out of Your Backend with Claude Managed Agents](BLOG_POST.md)
* **Example output:** [`sample_output/RELEASE_NOTES.md`](sample_output/RELEASE_NOTES.md) (generated from `fastapi/fastapi` `0.162.0..0.165.0` across 83 tool calls)

## Quickstart

### 1. Clone and install dependencies

Requires Python 3.11 or newer.

    git clone https://github.com/krithika0827/release-notes-agent.git
    cd release-notes-agent
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -U "anthropic>=1.13" "brotli>=1.2"

### 2. Set your Anthropic API key

Create an API key in the Claude Console under **Settings -> API Keys** (requires active API credits, billed separately from a Claude Pro/Max subscription), then export it:

    export ANTHROPIC_API_KEY="sk-ant-..."

### 3. Register the agent and sandbox environment

    python setup_resources.py

This registers the versioned agent from `agent.md` and creates the cloud container environment from `environment.yaml`, pinning the agent version and environment ID locally in `claude-lock.json`.

### 4. Generate release notes

    python generate_notes.py https://github.com/fastapi/fastapi 0.162.0..0.165.0

The CLI streams live `bash` and file tool executions over Server-Sent Events (SSE) while Anthropic's container inspects the repository, then downloads the finished output to `sample_output/RELEASE_NOTES.md`.

## How it works

1. **Provision once:** `setup_resources.py` registers a Sonnet 5.5 agent from `agent.md` (with web search off so it only reads the repo) and creates a Linux sandbox from `environment.yaml` locked to GitHub traffic. Those IDs get saved to `claude-lock.json`.
2. **Run in the cloud:** `generate_notes.py` opens a session with a configured $0.50 budget and streams SSE events while Anthropic's container clones the repo, inspects code diffs, and verifies commit hashes against `git log`.
3. **Pull the artifact:** Once the session goes `idle`, the CLI downloads `RELEASE_NOTES.md` via the session Files API. The container stays warm afterward, so follow-up prompts run immediately without re-cloning.

## Project structure

| File | Description |
| :--- | :--- |
| `agent.md` | Agent system prompt, model version, and grounded toolset definition |
| `environment.yaml` | Cloud Linux container template and GitHub-only egress allowlist |
| `setup_resources.py` | Provisions the agent and environment and writes `claude-lock.json` |
| `generate_notes.py` | Thin CLI runner that streams session events and downloads the artifact |
| `sample_output/RELEASE_NOTES.md` | Real release notes generated from `fastapi/fastapi` (`0.162.0..0.165.0`) |
| `BLOG_POST.md` | Technical breakdown of Claude Managed Agents and its trade-offs |
