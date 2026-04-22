from __future__ import annotations

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_URI = os.getenv("GOOGLE_OAUTH_TOKEN_URI", "https://oauth2.googleapis.com/token").strip()


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    if value == "REPLACE_ME" or value.startswith("REPLACE_ME"):
        raise RuntimeError(f"Environment variable {name} still contains a placeholder value.")
    return value


def main() -> int:
    try:
        client_config = {
            "installed": {
                "client_id": required_env("GOOGLE_OAUTH_CLIENT_ID"),
                "client_secret": required_env("GOOGLE_OAUTH_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": TOKEN_URI,
            }
        }
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        open_browser=True,
        access_type="offline",
        prompt="consent",
    )

    if not credentials.refresh_token:
        print(
            "No refresh token was returned. Revoke the app's prior access and run this script again.",
            file=sys.stderr,
        )
        return 2

    print(f'export GOOGLE_OAUTH_REFRESH_TOKEN="{credentials.refresh_token}"')
    print(f'export GOOGLE_OAUTH_TOKEN_URI="{credentials.token_uri}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
