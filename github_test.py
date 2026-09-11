import time
from pathlib import Path

import jwt
import requests


APP_ID = "4903854"
PRIVATE_KEY_PATH = Path("github-app.private-key.pem")

GITHUB_API = "https://api.github.com"


def create_app_jwt() -> str:
    private_key = PRIVATE_KEY_PATH.read_text()

    now = int(time.time())

    payload = {
        "iat": now - 60,
        "exp": now + (9 * 60),
        "iss": APP_ID,
    }

    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
    )


def github_request(method: str, url: str, token: str, **kwargs):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response = requests.request(
        method,
        url,
        headers=headers,
        **kwargs,
    )

    print(f"{method} {url}")
    print(f"Status: {response.status_code}")

    if not response.ok:
        print(response.text)
        response.raise_for_status()

    return response.json()


def main():
    print("Creating GitHub App JWT...")
    jwt_token = create_app_jwt()

    print("Getting App installations...")
    installations = github_request(
        "GET",
        f"{GITHUB_API}/app/installations",
        jwt_token,
    )

    if not installations:
        print()
        print("The App has no installations yet.")
        print("Install 'Exagon Project Insights' on @exagonsoft first.")
        return

    print()
    print("Installations:")

    for installation in installations:
        print(
            f"- ID: {installation['id']}"
            f" | Account: {installation['account']['login']}"
        )

    installation = next(
        (
            item
            for item in installations
            if item["account"]["login"].lower() == "exagonsoft"
        ),
        installations[0],
    )

    installation_id = installation["id"]

    print()
    print(f"Using installation ID: {installation_id}")

    print("Creating installation access token...")

    token_response = github_request(
        "POST",
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        jwt_token,
    )

    installation_token = token_response["token"]

    print("Installation token created.")

    print()
    print("Getting repositories...")

    repositories = github_request(
        "GET",
        f"{GITHUB_API}/installation/repositories",
        installation_token,
    )

    print()
    print(f"Repositories available: {repositories['total_count']}")

    for repo in repositories["repositories"]:
        print(
            f"- {repo['full_name']}"
            f" | ⭐ {repo['stargazers_count']}"
            f" | 🍴 {repo['forks_count']}"
            f" | Issues: {repo['open_issues_count']}"
        )


if __name__ == "__main__":
    main()