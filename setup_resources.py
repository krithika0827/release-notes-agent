import json
import os
import re
from pathlib import Path
from anthropic import Anthropic

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def parse_agent_md(path: str = "agent.md") -> dict:
    raw = Path(path).read_text(encoding="utf-8")
    _, frontmatter, body = raw.split("---", 2)

    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
    model_match = re.search(r"^model:\s*(.+)$", frontmatter, re.MULTILINE)
    disabled = re.findall(r"-\s*name:\s*(\w+)\s*\n\s*enabled:\s*false", frontmatter)

    return {
        "name": name_match.group(1).strip().strip('"') if name_match else "Release Notes Generator",
        "model": model_match.group(1).strip().strip('"') if model_match else "claude-sonnet-5-5",
        "disabled_tools": disabled or ["web_search", "web_fetch"],
        "system": body.strip(),
    }


def parse_environment_yaml(path: str = "environment.yaml") -> dict:
    raw = Path(path).read_text(encoding="utf-8")
    name_match = re.search(r"^name:\s*(.+)$", raw, re.MULTILINE)
    hosts = re.findall(r'^\s+-\s*"?([^"\n]+)"?', raw, re.MULTILINE)

    return {
        "name": name_match.group(1).strip().strip('"') if name_match else "release-notes-sandbox",
        "allowed_hosts": hosts or ["github.com", "*.githubusercontent.com"],
    }


def main() -> None:
    agent_cfg = parse_agent_md()
    env_cfg = parse_environment_yaml()

    agent = client.beta.agents.create(
        name=agent_cfg["name"],
        model=agent_cfg["model"],
        system=agent_cfg["system"],
        tools=[
            {
                "type": "agent_toolset_20260401",
                "configs": [
                    {"name": tool, "enabled": False} for tool in agent_cfg["disabled_tools"]
                ],
            }
        ],
    )
    print(f"[created] Agent: {agent.id} (v{agent.version})")

    env = client.beta.environments.create(
        name=env_cfg["name"],
        config={
            "type": "cloud",
            "networking": {
                "type": "limited",
                "allowed_hosts": env_cfg["allowed_hosts"],
            },
        },
    )
    print(f"[created] Environment: {env.id}")

    lock_data = {
        "agent": {"id": agent.id, "version": agent.version},
        "environment": {"id": env.id},
    }
    Path("claude-lock.json").write_text(json.dumps(lock_data, indent=2))
    print("[saved]   claude-lock.json")


if __name__ == "__main__":
    main()
