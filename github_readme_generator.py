#!/usr/bin/env python3
"""GitHub Profile README Generator.

Fetches a GitHub user's profile data via the REST API and generates
a polished profile README.md file. Uses only the Python standard library.

Usage:
    python github_readme_generator.py <username> [--token TOKEN] [--output PATH]
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime


# ---------------------------------------------------------------------------
# GitHub API client
# ---------------------------------------------------------------------------

API_BASE = "https://api.github.com"


def _build_request(url, token=None):
    """Build a urllib Request with appropriate headers."""
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "github-readme-generator")
    if token:
        req.add_header("Authorization", f"token {token}")
    return req


def api_get(url, token=None):
    """Perform a GET request against the GitHub API.

    Returns the parsed JSON response. Raises SystemExit on fatal errors.
    """
    req = _build_request(url, token)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print(f"Error: Resource not found – {url}", file=sys.stderr)
            sys.exit(1)
        if exc.code == 403:
            reset = exc.headers.get("X-RateLimit-Reset")
            msg = "API rate limit exceeded."
            if reset:
                reset_time = datetime.utcfromtimestamp(int(reset)).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                )
                msg += f" Resets at {reset_time}."
            msg += " Use --token to authenticate for higher limits."
            print(f"Error: {msg}", file=sys.stderr)
            sys.exit(1)
        print(
            f"Error: GitHub API returned HTTP {exc.code} for {url}",
            file=sys.stderr,
        )
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Error: Network request failed – {exc.reason}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------


def fetch_profile(username, token=None):
    """Fetch the user's profile information."""
    return api_get(f"{API_BASE}/users/{username}", token)


def fetch_repos(username, token=None):
    """Fetch all public repos, paginating if necessary."""
    repos = []
    page = 1
    while True:
        url = (
            f"{API_BASE}/users/{username}/repos"
            f"?sort=stars&direction=desc&per_page=100&page={page}"
        )
        batch = api_get(url, token)
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def fetch_events(username, token=None):
    """Fetch recent public events."""
    url = f"{API_BASE}/users/{username}/events/public?per_page=30"
    return api_get(url, token)


# ---------------------------------------------------------------------------
# Data processing
# ---------------------------------------------------------------------------


def compute_language_stats(repos):
    """Aggregate language usage across all repos.

    Returns a list of (language, percentage) tuples sorted by frequency.
    """
    counter = Counter()
    for repo in repos:
        lang = repo.get("language")
        if lang:
            counter[lang] += 1
    total = sum(counter.values())
    if total == 0:
        return []
    return [(lang, count / total * 100) for lang, count in counter.most_common()]


def top_repos(repos, n=6):
    """Return the top-n repos by stargazer count (excluding forks)."""
    original = [r for r in repos if not r.get("fork")]
    original.sort(key=lambda r: r.get("stargazers_count", 0), reverse=True)
    return original[:n]


def format_event(event):
    """Return a human-readable one-liner for a GitHub event, or None to skip."""
    etype = event.get("type", "")
    repo_name = event.get("repo", {}).get("name", "")
    payload = event.get("payload", {})
    created = event.get("created_at", "")
    date_str = ""
    if created:
        try:
            dt = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ")
            date_str = dt.strftime("%b %d")
        except ValueError:
            pass

    if etype == "PushEvent":
        commits = payload.get("commits", [])
        count = len(commits) if commits else payload.get("size", 0)
        if count == 0:
            count = payload.get("distinct_size", 1)
        unit = "commit" if count == 1 else "commits"
        return f"Pushed {count} {unit} to `{repo_name}` ({date_str})"
    if etype == "PullRequestEvent":
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})
        title = pr.get("title", "")
        return f"{action.capitalize()} PR \"{title}\" in `{repo_name}` ({date_str})"
    if etype == "IssuesEvent":
        action = payload.get("action", "")
        issue = payload.get("issue", {})
        title = issue.get("title", "")
        return f"{action.capitalize()} issue \"{title}\" in `{repo_name}` ({date_str})"
    if etype == "WatchEvent":
        return f"Starred `{repo_name}` ({date_str})"
    if etype == "CreateEvent":
        ref_type = payload.get("ref_type", "")
        ref = payload.get("ref", "")
        if ref_type == "repository":
            return f"Created repository `{repo_name}` ({date_str})"
        if ref:
            return f"Created {ref_type} `{ref}` in `{repo_name}` ({date_str})"
        return None
    if etype == "ForkEvent":
        forkee = payload.get("forkee", {}).get("full_name", "")
        return f"Forked `{repo_name}` to `{forkee}` ({date_str})"
    if etype == "IssueCommentEvent":
        issue = payload.get("issue", {})
        title = issue.get("title", "")
        return f"Commented on \"{title}\" in `{repo_name}` ({date_str})"
    return None


def format_events(events, limit=10):
    """Return a list of formatted event strings."""
    lines = []
    for event in events:
        line = format_event(event)
        if line:
            lines.append(line)
        if len(lines) >= limit:
            break
    return lines


# ---------------------------------------------------------------------------
# README generation
# ---------------------------------------------------------------------------


def _section_header(profile):
    """Generate the header section with name, avatar, bio, and metadata."""
    name = profile.get("name") or profile.get("login", "")
    login = profile.get("login", "")
    avatar = profile.get("avatar_url", "")
    bio = profile.get("bio", "")
    location = profile.get("location", "")
    company = profile.get("company", "")
    blog = profile.get("blog", "")

    lines = []
    lines.append(f"# Hi there! I'm {name} 👋\n")
    if avatar:
        lines.append(f'<img src="{avatar}" width="200" align="right" />\n')
    if bio:
        lines.append(f"**{bio}**\n")

    meta_parts = []
    if location:
        meta_parts.append(f"📍 {location}")
    if company:
        meta_parts.append(f"🏢 {company}")
    if blog:
        url = blog if blog.startswith("http") else f"https://{blog}"
        meta_parts.append(f"🔗 [{blog}]({url})")
    if meta_parts:
        lines.append(" | ".join(meta_parts) + "\n")

    return "\n".join(lines)


def _section_stats(profile, repos):
    """Generate the GitHub Stats section."""
    followers = profile.get("followers", 0)
    following = profile.get("following", 0)
    public_repos = profile.get("public_repos", 0)
    total_stars = sum(r.get("stargazers_count", 0) for r in repos)

    lines = [
        "## 📊 GitHub Stats\n",
        "| Followers | Following | Public Repos | Total Stars |",
        "|-----------|-----------|--------------|-------------|",
        f"| {followers} | {following} | {public_repos} | {total_stars} |\n",
    ]
    return "\n".join(lines)


def _section_top_repos(repos):
    """Generate the Top Repositories section."""
    top = top_repos(repos)
    if not top:
        return ""

    lines = ["## 🏆 Top Repositories\n"]
    lines.append("| Repository | Description | Language | ⭐ | 🍴 |")
    lines.append("|------------|-------------|----------|---:|---:|")
    for repo in top:
        name = repo.get("name", "")
        url = repo.get("html_url", "")
        desc = repo.get("description") or ""
        # Truncate long descriptions for table readability
        if len(desc) > 80:
            desc = desc[:77] + "..."
        # Escape pipe characters in descriptions
        desc = desc.replace("|", "\\|")
        lang = repo.get("language") or "—"
        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)
        lines.append(f"| [{name}]({url}) | {desc} | {lang} | {stars} | {forks} |")
    lines.append("")
    return "\n".join(lines)


def _section_languages(repos):
    """Generate the Language Breakdown section."""
    stats = compute_language_stats(repos)
    if not stats:
        return ""

    lines = ["## 💻 Language Breakdown\n"]
    for lang, pct in stats:
        bar_len = round(pct / 5)  # scale to ~20 chars max
        bar = "█" * bar_len
        lines.append(f"- **{lang}** {bar} {pct:.1f}%")
    lines.append("")
    return "\n".join(lines)


def _section_activity(events):
    """Generate the Recent Activity section."""
    formatted = format_events(events)
    if not formatted:
        return ""

    lines = ["## ⚡ Recent Activity\n"]
    for entry in formatted:
        lines.append(f"- {entry}")
    lines.append("")
    return "\n".join(lines)


def _section_connect(profile):
    """Generate the Connect With Me section."""
    blog = profile.get("blog", "")
    twitter = profile.get("twitter_username", "")
    email = profile.get("email", "")
    login = profile.get("login", "")

    links = []
    if blog:
        url = blog if blog.startswith("http") else f"https://{blog}"
        links.append(f"- 🌐 [{blog}]({url})")
    if twitter:
        links.append(f"- 🐦 [@{twitter}](https://twitter.com/{twitter})")
    if email:
        links.append(f"- 📧 [{email}](mailto:{email})")
    links.append(f"- 🐙 [{login}](https://github.com/{login})")

    if not links:
        return ""

    return "## 🤝 Connect With Me\n\n" + "\n".join(links) + "\n"


def generate_readme(profile, repos, events):
    """Assemble the full README from all sections."""
    sections = [
        _section_header(profile),
        _section_stats(profile, repos),
        _section_top_repos(repos),
        _section_languages(repos),
        _section_activity(events),
        _section_connect(profile),
    ]
    # Filter out empty sections and join with a separator
    parts = [s for s in sections if s.strip()]
    readme = "\n---\n\n".join(parts)
    readme += (
        "\n---\n\n"
        "<p align=\"center\">"
        "<i>Generated with "
        "<a href=\"https://github.com\">GitHub Profile README Generator</a>"
        "</i>"
        "</p>\n"
    )
    return readme


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a GitHub profile README.md from a user's public data.",
    )
    parser.add_argument("username", help="GitHub username to generate a README for")
    parser.add_argument(
        "-t",
        "--token",
        default=None,
        help="GitHub personal access token (overrides GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="README.md",
        help="Output file path (default: README.md)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    token = args.token or os.environ.get("GITHUB_TOKEN")

    if token:
        print("Authenticating with provided token...")
    else:
        print("No token provided – using unauthenticated access (60 req/hr limit).")

    username = args.username

    print(f"Fetching profile for {username}...")
    profile = fetch_profile(username, token)

    print("Fetching repositories...")
    repos = fetch_repos(username, token)

    print("Fetching recent activity...")
    try:
        events = fetch_events(username, token)
    except SystemExit:
        # Events endpoint can fail for some users; non-fatal
        print("Warning: Could not fetch events, skipping activity section.")
        events = []

    print("Generating README...")
    readme = generate_readme(profile, repos, events)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(readme)

    print(f"Done! README written to {args.output}")


if __name__ == "__main__":
    main()
