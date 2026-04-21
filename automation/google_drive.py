from __future__ import annotations

from dataclasses import dataclass

import requests

from automation.config import AuthConfigError, DiscoveryError, drive_roots, required_google_env


TOKEN_SCOPES = "https://www.googleapis.com/auth/drive.readonly"


@dataclass
class DriveClient:
    access_token: str

    @classmethod
    def from_env(cls) -> "DriveClient":
        env = required_google_env()
        response = requests.post(
            env["GOOGLE_OAUTH_TOKEN_URI"],
            data={
                "client_id": env["GOOGLE_OAUTH_CLIENT_ID"],
                "client_secret": env["GOOGLE_OAUTH_CLIENT_SECRET"],
                "refresh_token": env["GOOGLE_OAUTH_REFRESH_TOKEN"],
                "grant_type": "refresh_token",
                "scope": TOKEN_SCOPES,
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise AuthConfigError(f"Failed to refresh Google OAuth token: {response.text}")
        access_token = response.json().get("access_token", "")
        if not access_token:
            raise AuthConfigError("Google OAuth token refresh returned no access token.")
        return cls(access_token=access_token)

    def _get(self, path: str, params: dict) -> dict:
        response = requests.get(
            f"https://www.googleapis.com/drive/v3/{path}",
            headers={"Authorization": f"Bearer {self.access_token}"},
            params=params,
            timeout=30,
        )
        if response.status_code != 200:
            raise DiscoveryError(f"Google Drive API request failed for {path}: {response.text}")
        return response.json()

    def discover_course_folders(self, limit: int | None = None) -> list[dict]:
        queries = ["mimeType='application/vnd.google-apps.folder'", "trashed=false", "name contains ' CF'"]
        roots = drive_roots()
        if roots:
            quoted = " or ".join(f"'{root}' in parents" for root in roots)
            queries.append(f"({quoted})")
        payload = self._get(
            "files",
            {
                "q": " and ".join(queries),
                "fields": "files(id,name,modifiedTime,webViewLink)",
                "pageSize": min(limit or 200, 200),
                "orderBy": "name_natural",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            },
        )
        files = payload.get("files", [])
        if limit is not None:
            return files[:limit]
        return files

    def list_folder_items(self, folder_id: str) -> list[dict]:
        payload = self._get(
            "files",
            {
                "q": f"'{folder_id}' in parents and trashed=false",
                "fields": "files(id,name,mimeType,webViewLink,webContentLink,modifiedTime)",
                "pageSize": 500,
                "orderBy": "folder,name_natural",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            },
        )
        return payload.get("files", [])
