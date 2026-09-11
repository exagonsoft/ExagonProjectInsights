import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import requests

GITHUB_API = "https://api.github.com"


class GitHubClient:
    def __init__(self) -> None:
        self.app_id = os.environ["GITHUB_APP_ID"]
        self.private_key_path = Path(os.environ["GITHUB_PRIVATE_KEY_PATH"])

    def _app_jwt(self) -> str:
        private_key = self.private_key_path.read_text()
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + (9 * 60),
            "iss": self.app_id,
        }
        return jwt.encode(payload, private_key, algorithm="RS256")

    def _request(self, method: str, url: str, token: str, **kwargs):
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()

    def _paginate(self, url: str, token: str, params: dict | None = None, max_pages: int = 10) -> list[dict]:
        items = []
        query = dict(params or {})
        query["per_page"] = 100
        for page in range(1, max_pages + 1):
            query["page"] = page
            batch = self._request("GET", url, token, params=query)
            items.extend(batch)
            if len(batch) < 100:
                break
        return items

    def get_installation(self, account: str = "exagonsoft") -> dict:
        installations = self._request(
            "GET", f"{GITHUB_API}/app/installations", self._app_jwt()
        )
        for installation in installations:
            if installation["account"]["login"].lower() == account.lower():
                return installation
        raise RuntimeError(f"No GitHub App installation found for @{account}")

    def installation_token(self, installation_id: int) -> str:
        result = self._request(
            "POST",
            f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
            self._app_jwt(),
        )
        return result["token"]

    def repositories(self, account: str = "exagonsoft") -> list[dict]:
        installation = self.get_installation(account)
        token = self.installation_token(installation["id"])
        result = self._request(
            "GET", f"{GITHUB_API}/installation/repositories", token
        )
        return result["repositories"]

    def repository(self, owner: str, repo: str) -> dict:
        installation = self.get_installation(owner)
        token = self.installation_token(installation["id"])
        return self._request("GET", f"{GITHUB_API}/repos/{owner}/{repo}", token)

    def issues(self, owner: str, repo: str, state: str = "open") -> list[dict]:
        installation = self.get_installation(owner)
        token = self.installation_token(installation["id"])
        return self._paginate(
            f"{GITHUB_API}/repos/{owner}/{repo}/issues",
            token,
            params={"state": state},
        )

    def pull_requests(self, owner: str, repo: str, state: str = "open") -> list[dict]:
        installation = self.get_installation(owner)
        token = self.installation_token(installation["id"])
        return self._paginate(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
            token,
            params={"state": state},
        )

    def commits(self, owner: str, repo: str, days: int = 180) -> list[dict]:
        installation = self.get_installation(owner)
        token = self.installation_token(installation["id"])
        since = datetime.now(timezone.utc) - timedelta(days=days)
        try:
            return self._paginate(
                f"{GITHUB_API}/repos/{owner}/{repo}/commits",
                token,
                params={"since": since.isoformat()},
            )
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 409:
                return []
            raise

    def reviews(self, owner: str, repo: str, pull_number: int) -> list[dict]:
        installation = self.get_installation(owner)
        token = self.installation_token(installation["id"])
        return self._paginate(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pull_number}/reviews",
            token,
            max_pages=3,
        )
