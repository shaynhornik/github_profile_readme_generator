# GitHub Profile README Generator

A Python CLI tool that fetches any GitHub user's public profile data via the GitHub REST API and generates a polished profile `README.md` file.

**Zero dependencies** — uses only the Python standard library.

## Features

- Fetches profile info, repositories, and recent activity from the GitHub API
- Generates a Markdown README with:
  - Header with name, avatar, bio, location, company, and website
  - GitHub stats table (followers, following, repos, total stars)
  - Top repositories ranked by stars (with language, stars, forks)
  - Language breakdown with visual bar chart
  - Recent activity feed (pushes, PRs, issues, stars, forks)
  - Social/contact links
- Optional token-based authentication for higher rate limits
- Pagination support for users with 100+ repos

## Usage

```bash
python github_readme_generator.py <username> [--token TOKEN] [--output PATH]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `username` | GitHub username (required) |
| `--token`, `-t` | GitHub personal access token (optional, overrides `GITHUB_TOKEN` env var) |
| `--output`, `-o` | Output file path (default: `README.md`) |

### Examples

```bash
# Generate a README for any public user
python github_readme_generator.py octocat

# Use a token for higher API rate limits
python github_readme_generator.py octocat --token ghp_yourtoken

# Or set the token as an environment variable
export GITHUB_TOKEN=ghp_yourtoken
python github_readme_generator.py octocat

# Write to a custom output path
python github_readme_generator.py octocat -o profile.md
```

## GitHub Profile README

To display a README on your GitHub profile page, create a repository with the same name as your GitHub username (e.g., `shaynhornik/shaynhornik`) and place the generated `README.md` in it.

## License

MIT
