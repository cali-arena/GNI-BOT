"""
One-time Telethon login: creates session file in the mounted volume.
Run: python -m apps.collector.telegram_login

Requires: TELEGRAM_API_ID, TELEGRAM_API_HASH (env).
Session path: TELETHON_SESSION_PATH (default /data/telethon/session).
"""
import os
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

from telethon import TelegramClient


def main() -> None:
    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    session_path = os.environ.get("TELETHON_SESSION_PATH", "/data/telethon/session")

    if not api_id or not api_hash:
        print("Set TELEGRAM_API_ID and TELEGRAM_API_HASH in the environment.", file=sys.stderr)
        sys.exit(1)

    # Ensure session directory exists (for file-based session)
    session_dir = Path(session_path).resolve().parent
    session_dir.mkdir(parents=True, exist_ok=True)

    # Telethon adds .session suffix when given a path string
    client = TelegramClient(
        session_path,
        int(api_id),
        api_hash.strip(),
    )
    with client:
        # If session is new, prompts for phone number and code; then saves session to disk
        client.start()
        print("Telethon session created and saved to the mounted volume.")
        print("You can now run telegram_ingest.")


if __name__ == "__main__":
    main()
