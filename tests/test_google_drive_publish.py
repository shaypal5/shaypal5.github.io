import subprocess
import unittest
from types import SimpleNamespace
from unittest import mock

from automation.config import AuthConfigError, DiscoveryError, PublishError
from automation.google_drive import DriveClient
from automation.publish import commit_all, create_pull_request, ensure_branch, publish_changes, push_branch, run_git


class GoogleDrivePublishTests(unittest.TestCase):
    def test_drive_client_from_env_and_requests(self) -> None:
        response = mock.Mock(status_code=200)
        response.json.return_value = {"access_token": "token-1"}
        with mock.patch("automation.google_drive.required_google_env", return_value={
            "GOOGLE_OAUTH_CLIENT_ID": "id",
            "GOOGLE_OAUTH_CLIENT_SECRET": "secret",
            "GOOGLE_OAUTH_REFRESH_TOKEN": "refresh",
            "GOOGLE_OAUTH_TOKEN_URI": "https://oauth.example/token",
        }), mock.patch("automation.google_drive.requests.post", return_value=response) as post:
            client = DriveClient.from_env()
            self.assertEqual(client.access_token, "token-1")
            post.assert_called_once()

        bad_response = mock.Mock(status_code=400, text="bad")
        bad_response.json.return_value = {}
        with mock.patch("automation.google_drive.required_google_env", return_value={
            "GOOGLE_OAUTH_CLIENT_ID": "id",
            "GOOGLE_OAUTH_CLIENT_SECRET": "secret",
            "GOOGLE_OAUTH_REFRESH_TOKEN": "refresh",
            "GOOGLE_OAUTH_TOKEN_URI": "https://oauth.example/token",
        }), mock.patch("automation.google_drive.requests.post", return_value=bad_response):
            with self.assertRaises(AuthConfigError):
                DriveClient.from_env()

        empty_response = mock.Mock(status_code=200)
        empty_response.json.return_value = {}
        with mock.patch("automation.google_drive.required_google_env", return_value={
            "GOOGLE_OAUTH_CLIENT_ID": "id",
            "GOOGLE_OAUTH_CLIENT_SECRET": "secret",
            "GOOGLE_OAUTH_REFRESH_TOKEN": "refresh",
            "GOOGLE_OAUTH_TOKEN_URI": "https://oauth.example/token",
        }), mock.patch("automation.google_drive.requests.post", return_value=empty_response):
            with self.assertRaises(AuthConfigError):
                DriveClient.from_env()

    def test_drive_client_get_and_queries(self) -> None:
        client = DriveClient(access_token="token")
        ok = mock.Mock(status_code=200)
        ok.json.return_value = {"files": [{"id": "1", "name": "Valid Course 24 CF"}]}
        with mock.patch("automation.google_drive.requests.get", return_value=ok) as get, \
            mock.patch("automation.google_drive.drive_roots", return_value=["root-a", "root-b"]):
            folders = client.discover_course_folders(limit=1)
            self.assertEqual(folders, [{"id": "1", "name": "Valid Course 24 CF"}])
            params = get.call_args.kwargs["params"]
            self.assertIn("'root-a' in parents", params["q"])
            items = client.list_folder_items("folder-1")
            self.assertEqual(items, [{"id": "1", "name": "Valid Course 24 CF"}])
        with mock.patch("automation.google_drive.requests.get", return_value=ok), \
            mock.patch("automation.google_drive.drive_roots", return_value=[]):
            self.assertEqual(client.discover_course_folders(limit=None), [{"id": "1", "name": "Valid Course 24 CF"}])

        bad = mock.Mock(status_code=500, text="nope")
        bad.json.return_value = {}
        with mock.patch("automation.google_drive.requests.get", return_value=bad):
            with self.assertRaises(DiscoveryError):
                client._get("files", {})

    def test_drive_client_paginates_folder_queries(self) -> None:
        client = DriveClient(access_token="token")
        with mock.patch.object(
            client,
            "_get",
            side_effect=[
                {
                    "files": [
                        {"id": "1", "name": "cf"},
                        {"id": "2", "name": "Real Course 24 CF"},
                    ],
                    "nextPageToken": "page-2",
                },
                {"files": [{"id": "3", "name": "Real Course 25 CF"}]},
            ],
        ) as get, mock.patch("automation.google_drive.drive_roots", return_value=[]):
            self.assertEqual(
                client.discover_course_folders(limit=None),
                [
                    {"id": "2", "name": "Real Course 24 CF"},
                    {"id": "3", "name": "Real Course 25 CF"},
                ],
            )
            self.assertNotIn("pageToken", get.call_args_list[0].args[1])
            self.assertEqual(get.call_args_list[1].args[1]["pageToken"], "page-2")

        with mock.patch.object(
            client,
            "_get",
            side_effect=[
                {
                    "files": [
                        {"id": "1", "name": "cf"},
                        {"id": "2", "name": "Real Course 24 CF"},
                    ],
                    "nextPageToken": "page-2",
                },
                {
                    "files": [
                        {"id": "3", "name": "Real Course 25 CF"},
                        {"id": "4", "name": "Real Course 26 CF"},
                    ]
                },
            ],
        ), mock.patch("automation.google_drive.drive_roots", return_value=[]):
            self.assertEqual(
                client.discover_course_folders(limit=3),
                [
                    {"id": "2", "name": "Real Course 24 CF"},
                    {"id": "3", "name": "Real Course 25 CF"},
                    {"id": "4", "name": "Real Course 26 CF"},
                ],
            )

        with mock.patch.object(client, "_get") as get, \
            mock.patch("automation.google_drive.drive_roots", return_value=[]):
            self.assertEqual(client.discover_course_folders(limit=0), [])
            get.assert_not_called()

        with mock.patch.object(
            client,
            "_get",
            side_effect=[
                {"files": [{"id": "a"}], "nextPageToken": "page-2"},
                {"files": [{"id": "b"}]},
            ],
        ) as get:
            self.assertEqual(client.list_folder_items("folder-1"), [{"id": "a"}, {"id": "b"}])
            self.assertEqual(get.call_args_list[1].args[1]["pageToken"], "page-2")

    def test_drive_client_lists_folder_items_recursively(self) -> None:
        client = DriveClient(access_token="token")
        with mock.patch.object(
            client,
            "list_folder_items",
            side_effect=[
                [
                    {"id": "slides-folder", "name": "Slides", "mimeType": "application/vnd.google-apps.folder"},
                    {"id": "admin-folder", "name": "Admin", "mimeType": "application/vnd.google-apps.folder"},
                    {"id": "root-file", "name": "Root deck", "mimeType": "application/pdf"},
                ],
                [
                    {"id": "nested-file", "name": "Lecture deck", "mimeType": "application/pdf"},
                ],
            ],
        ) as list_items:
            items = client.list_folder_items_recursive(
                "folder-1",
                should_descend=lambda item: item.get("name") == "Slides",
            )
        self.assertEqual(
            items,
            [
                {"id": "root-file", "name": "Root deck", "mimeType": "application/pdf"},
                {"id": "nested-file", "name": "Lecture deck", "mimeType": "application/pdf"},
            ],
        )
        self.assertEqual(list_items.call_args_list[0].args[0], "folder-1")
        self.assertEqual(list_items.call_args_list[1].args[0], "slides-folder")

    def test_drive_client_export_file_text(self) -> None:
        client = DriveClient(access_token="token")
        ok = mock.Mock(status_code=200, text="hello")
        with mock.patch("automation.google_drive.requests.get", return_value=ok) as get:
            self.assertEqual(client.export_file_text("file-1", "text/plain"), "hello")
            self.assertIn("/files/file-1/export", get.call_args.args[0])

        bad = mock.Mock(status_code=404, text="missing")
        with mock.patch("automation.google_drive.requests.get", return_value=bad):
            with self.assertRaises(DiscoveryError):
                client.export_file_text("file-1", "text/plain")

    def test_publish_helpers(self) -> None:
        good = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="ok\n", stderr="")
        with mock.patch("automation.publish.subprocess.run", return_value=good):
            self.assertEqual(run_git(["status"]), "ok")

        bad = subprocess.CompletedProcess(args=["git"], returncode=1, stdout="", stderr="failed")
        with mock.patch("automation.publish.subprocess.run", return_value=bad):
            with self.assertRaises(PublishError):
                run_git(["status"])

        with mock.patch("automation.publish.run_git") as run:
            run.side_effect = ["other-branch", ""]
            ensure_branch("target")
            run.assert_any_call(["checkout", "-B", "target"])

        with mock.patch("automation.publish.run_git") as run:
            run.side_effect = ["target"]
            ensure_branch("target")
            self.assertEqual(run.call_count, 1)

        with mock.patch("automation.publish.run_git") as run:
            run.side_effect = ["", ""]
            commit_all("msg")
            run.assert_any_call(["add", "automation", "data", "docs", "tests", ".github", "teaching", "teaching.md", "_config.yml", ".gitignore", "pyproject.toml"])
        with mock.patch("automation.publish.run_git") as run:
            run.side_effect = ["", "M changed", ""]
            commit_all("msg")
            run.assert_any_call(["commit", "-m", "msg"])

        with mock.patch("automation.publish.run_git") as run:
            push_branch("branch")
            run.assert_called_with(["push", "-u", "origin", "branch"])

        success = subprocess.CompletedProcess(args=["gh"], returncode=0, stdout="https://example.com/pr\n", stderr="")
        with mock.patch("automation.publish.subprocess.run", return_value=success):
            self.assertEqual(create_pull_request("T", "B"), "https://example.com/pr")

        empty_success = subprocess.CompletedProcess(args=["gh"], returncode=0, stdout=" \n", stderr="")
        with mock.patch("automation.publish.subprocess.run", return_value=empty_success):
            with self.assertRaises(PublishError):
                create_pull_request("T", "B")

        failure = subprocess.CompletedProcess(args=["gh"], returncode=1, stdout="", stderr="boom")
        with mock.patch("automation.publish.subprocess.run", return_value=failure):
            with self.assertRaises(PublishError):
                create_pull_request("T", "B")

        with mock.patch("automation.publish.ensure_branch") as ensure, \
            mock.patch("automation.publish.commit_all") as commit, \
            mock.patch("automation.publish.push_branch") as push, \
            mock.patch("automation.publish.create_pull_request", return_value="https://example.com/pr"):
            result = publish_changes("branch", "Title", "Body", "Commit")
            ensure.assert_called_once_with("branch")
            commit.assert_called_once_with("Commit")
            push.assert_called_once_with("branch")
            self.assertEqual(result.pr_url, "https://example.com/pr")
