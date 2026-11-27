import json
import os
import sys
import time
from pathlib import Path
from anthropic import Anthropic

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def load_lock(lock_path: str = "claude-lock.json") -> tuple[str, int, str]:
    lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    return (
        lock["agent"]["id"],
        lock["agent"]["version"],
        lock["environment"]["id"],
    )


def download_output_artifact(
    session_id: str,
    dest_path: str = "sample_output/RELEASE_NOTES.md",
    retries: int = 5,
    delay_seconds: float = 1.5,
) -> None:
    for attempt in range(1, retries + 1):
        files = client.beta.files.list(
            scope_id=session_id,
            betas=["managed-agents-2026-04-01"],
        )
        for f in files.data:
            if f.filename.endswith("RELEASE_NOTES.md"):
                content = client.beta.files.download(
                    file_id=f.id,
                    betas=["managed-agents-2026-04-01"],
                )
                out = Path(dest_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(content.read())
                print(f"[saved]   Downloaded {f.filename} -> {dest_path}")
                return

        if attempt < retries:
            time.sleep(delay_seconds)

    raise RuntimeError(
        f"RELEASE_NOTES.md did not appear in session {session_id} outputs after {retries} attempts."
    )


def generate_release_notes(repo_url: str, rev_range: str = "HEAD~15..HEAD") -> None:
    agent_id, agent_version, environment_id = load_lock()

    session = client.beta.sessions.create(
        agent={"type": "agent", "id": agent_id, "version": agent_version},
        environment_id=environment_id,
        title=f"Release Notes: {repo_url} ({rev_range})",
        budget={
            "type": "limit",
            "max_list_cost": {"amount": "50", "currency": "USD"},
        },
    )
    print(f"[session] Started {session.id} (agent v{agent_version})")

    stop_reason = None
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[
                {
                    "type": "user.message",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Generate release notes for {repo_url} covering `{rev_range}`. "
                                "Write the full document to /mnt/session/outputs/RELEASE_NOTES.md."
                            ),
                        }
                    ],
                }
            ],
        )

        for event in stream:
            match event.type:
                case "agent.tool_use":
                    print(f"[tool]    {event.name}")
                case "agent.message":
                    for block in event.content:
                        if block.type == "text":
                            print(block.text, end="", flush=True)
                case "session.error":
                    print(f"\n[error]   {event.error}")
                case "session.status_idle":
                    raw_sr = getattr(event, "stop_reason", None)
                    stop_reason = getattr(raw_sr, "type", raw_sr)
                    print(f"\n[done]    Session idle (stop_reason={stop_reason}).")
                    break

    if stop_reason not in (None, "end_turn"):
        raise RuntimeError(f"Session {session.id} stopped early with stop_reason={stop_reason}")

    download_output_artifact(session.id)


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/pallets/flask"
    git_range = sys.argv[2] if len(sys.argv) > 2 else "3.0.3..3.1.0"
    generate_release_notes(repo, git_range)
