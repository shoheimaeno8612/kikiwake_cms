#!/usr/bin/env python3
import json
import re
import sys

ENV_FILE_RE = re.compile(r"(^|/)\.env(\.local|\.production|\.development)?$")

BASH_EXPOSE_RE = re.compile(
    r"\b(cat|less|more|head|tail|grep|egrep|fgrep|strings|xxd|hexdump|od|vim|vi|nano|open|bat)\b[^|;&\n]*\.env(\.local|\.production|\.development)?\b"
)
BASH_FORCE_ADD_RE = re.compile(
    r"\bgit\s+add\s+(-f|--force)\b[^|;&\n]*\.env(\.local|\.production|\.development)?\b"
)


def is_protected_env_path(path: str) -> bool:
    if not path:
        return False
    if path.endswith(".env.example"):
        return False
    return bool(ENV_FILE_RE.search(path))


def bash_command_touches_env(command: str) -> bool:
    if ".env.example" in command:
        command = command.replace(".env.example", "")
    return bool(BASH_EXPOSE_RE.search(command) or BASH_FORCE_ADD_RE.search(command))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input", {}) or {}

    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        if is_protected_env_path(file_path):
            print(
                f"Blocked: reading '{file_path}' is not allowed. "
                ".env contains secrets (Supabase/R2/Gemini keys) and must not be read into the session.",
                file=sys.stderr,
            )
            return 2

    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if bash_command_touches_env(command):
            print(
                "Blocked: this command would expose or force-track .env contents. "
                ".env holds secrets and must not be read, printed, or force-added to git.",
                file=sys.stderr,
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
