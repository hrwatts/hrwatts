#!/usr/bin/env python3
"""
Generate profile snapshot and metrics for the GitHub profile README.
Designed to run in GitHub Actions and inject auto-generated sections into README.md.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from github import Auth, Github
except ImportError:
    print("ERROR: PyGithub not installed. Run: pip install -r requirements.txt")
    raise SystemExit(1)

USERNAME = "hrwatts"
TRACKED_OWNERS = ("hrwatts", "hrwdata")
TRACKED_ORGS = ("hrwdata",)
EXCLUDED_REPOSITORIES = {USERNAME}
PROFILE_README = Path(__file__).parent.parent / "README.md"
METRICS_OUTPUT = Path(__file__).parent.parent / "metrics.json"

SNAPSHOT_START = "<!-- START_SNAPSHOT -->"
SNAPSHOT_END = "<!-- END_SNAPSHOT -->"
SUMMARY_START = "<!-- START_SUMMARY -->"
SUMMARY_END = "<!-- END_SUMMARY -->"
METRICS_START = "<!-- START_METRICS -->"
METRICS_END = "<!-- END_METRICS -->"

CATEGORY_LABELS = {
    "stochastic": "Stochastic processes",
    "dynamical": "Dynamical systems",
    "probability": "Applied probability",
    "computing": "Statistical computing",
    "finance": "Quantitative finance",
    "other": "Other projects",
}

ACADEMIC_KEYWORDS = {
    "stochastic": ["stochastic", "brownian", "martingale", "markov", "poisson", "levy"],
    "dynamical": ["dynamical", "differential", "ode", "pde", "dynamics", "bifurcation"],
    "probability": ["probability", "probabilistic", "random", "bayesian", "inference"],
    "computing": ["computing", "numerical", "algorithm", "computation", "optimization"],
    "finance": ["trade", "algorithmic", "backtest", "quant", "forex", "stock", "portfolio", "risk"],
}

FRAMEWORK_KEYWORDS = {
    "tensorflow": ["tensorflow", "tf"],
    "pytorch": ["pytorch", "torch"],
    "numpy": ["numpy"],
    "scipy": ["scipy"],
    "matlab": ["matlab"],
}

FRAMEWORK_DISPLAY = [
    ("tensorflow", "TensorFlow"),
    ("pytorch", "PyTorch"),
    ("numpy", "NumPy"),
    ("scipy", "SciPy"),
    ("matlab", "MATLAB"),
]


def now_utc() -> datetime:
    return datetime.utcnow()


def is_tracked_repo(repo) -> bool:
    """Return True when the repository should appear in the public profile."""
    owner_login = getattr(getattr(repo, "owner", None), "login", "").lower()
    repo_name = getattr(repo, "name", "").lower()
    is_fork = bool(getattr(repo, "fork", False))
    is_private = bool(getattr(repo, "private", False))

    return (
        owner_login in TRACKED_OWNERS
        and repo_name not in EXCLUDED_REPOSITORIES
        and not is_fork
        and not is_private
    )


def get_account_repos(gh: Github, account_name: str, is_org: bool) -> List:
    """Fetch public repositories for a user or organization account."""
    try:
        account = gh.get_organization(account_name) if is_org else gh.get_user(account_name)
        repos = list(account.get_repos(type="public", sort="updated", direction="desc"))
        print(f"Fetched {len(repos)} repositories from {account_name}")
        return repos
    except Exception as exc:
        print(f"ERROR fetching repositories for {account_name}: {exc}")
        return []


def get_tracked_repos(gh: Github) -> List:
    """Fetch and filter repositories that should appear on the profile."""
    all_repos = []
    seen = set()

    account_specs: Tuple[Tuple[str, bool], ...] = (
        (USERNAME, False),
        *((org_name, True) for org_name in TRACKED_ORGS),
    )

    for account_name, is_org in account_specs:
        for repo in get_account_repos(gh, account_name, is_org):
            if not is_tracked_repo(repo):
                continue
            if repo.full_name in seen:
                continue
            seen.add(repo.full_name)
            all_repos.append(repo)

    all_repos.sort(key=lambda repo: repo.updated_at or datetime.min, reverse=True)
    print(f"Tracking {len(all_repos)} repositories after filtering")
    return all_repos


def repo_sort_key(repo) -> tuple:
    has_description = bool((repo.description or "").strip())
    updated_ts = repo.updated_at.timestamp() if repo.updated_at else 0
    return (has_description, repo.stargazers_count, updated_ts)


def categorize_repos(repos: List) -> Dict[str, List]:
    """Categorize repositories by research area."""
    categorized = {key: [] for key in CATEGORY_LABELS}

    for repo in repos:
        name_lower = repo.name.lower()
        description = (repo.description or "").lower()
        full_text = f"{name_lower} {description}"

        for category, keywords in ACADEMIC_KEYWORDS.items():
            if any(keyword in full_text for keyword in keywords):
                categorized[category].append(repo)
                break
        else:
            categorized["other"].append(repo)

    return categorized


def extract_frameworks(repos: List) -> Dict[str, int]:
    """Extract framework usage from repository descriptions and names."""
    frameworks = {name: 0 for name in FRAMEWORK_KEYWORDS}

    for repo in repos:
        name_lower = repo.name.lower()
        description = (repo.description or "").lower()
        full_text = f"{name_lower} {description}"

        for framework, keywords in FRAMEWORK_KEYWORDS.items():
            if any(keyword in full_text for keyword in keywords):
                frameworks[framework] += 1

    return frameworks


def calculate_stats(repos: List, categorized: Dict[str, List]) -> Dict:
    """Calculate aggregate repository statistics."""
    total_stars = sum(repo.stargazers_count for repo in repos)
    total_forks = sum(repo.forks_count for repo in repos)

    languages: Dict[str, int] = {}
    for repo in repos:
        try:
            for language, byte_count in repo.get_languages().items():
                languages[language] = languages.get(language, 0) + byte_count
        except Exception:
            continue

    top_languages = sorted(languages.items(), key=lambda item: item[1], reverse=True)[:5]

    return {
        "tracked_owners": list(TRACKED_OWNERS),
        "excluded_repositories": sorted(EXCLUDED_REPOSITORIES),
        "total_repositories": len(repos),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "repositories_by_research_area": {
            key: len(category_repos) for key, category_repos in categorized.items()
        },
        "stars_by_research_area": {
            key: sum(repo.stargazers_count for repo in category_repos)
            for key, category_repos in categorized.items()
        },
        "top_languages": [
            {"name": language, "bytes": byte_count}
            for language, byte_count in top_languages
        ],
        "generated_at": now_utc().isoformat() + "Z",
    }


def select_featured_repos(repos: List, categorized: Dict[str, List], limit: int = 5) -> List:
    """Pick a small set of repositories that represents the portfolio."""
    featured: List = []
    seen = set()

    for category in ("stochastic", "dynamical", "probability", "computing", "finance"):
        ranked = sorted(categorized[category], key=repo_sort_key, reverse=True)
        for repo in ranked:
            if repo.name not in seen:
                featured.append(repo)
                seen.add(repo.name)
                break
        if len(featured) >= limit:
            return featured[:limit]

    for repo in sorted(repos, key=repo_sort_key, reverse=True):
        if repo.name not in seen:
            featured.append(repo)
            seen.add(repo.name)
        if len(featured) >= limit:
            break

    return featured[:limit]


def format_portfolio_summary(stats: Dict, repos: List, categorized: Dict[str, List]) -> str:
    """Format a concise portfolio snapshot for README injection."""
    generated = now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")
    primary_languages = ", ".join(lang["name"] for lang in stats["top_languages"][:3]) or "N/A"
    recent_repos = ", ".join(f"`{repo.full_name}`" for repo in repos[:3]) or "N/A"
    featured_repos = select_featured_repos(repos, categorized)

    lines = [
        "- Tracking public, non-fork repositories owned by `hrwatts` and `hrwdata`",
        f"- Public repositories: {stats['total_repositories']}",
        f"- Total stars and forks: {stats['total_stars']} stars, {stats['total_forks']} forks",
        f"- Primary languages: {primary_languages}",
        f"- Recently updated: {recent_repos}",
        "",
        "### Featured Repositories",
    ]

    for repo in featured_repos:
        description = repo.description or "No description provided."
        lines.append(f"- [{repo.full_name}]({repo.html_url}) - {description}")

    lines.append("")
    lines.append(f"*Last updated: {generated}*")
    return "\n".join(lines)


def format_snapshot_markdown(stats: Dict, repos: List) -> str:
    """Format a reliable in-README replacement for external stats cards."""
    generated = now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")
    top_languages = stats["top_languages"] or []

    lines = [
        "### Profile Stats",
        "- Tracking public, non-fork repositories owned by `hrwatts` and `hrwdata`",
        "- Excludes the `hrwatts` profile repository",
        f"- Public repositories counted: {stats['total_repositories']}",
        f"- Total stars: {stats['total_stars']}",
        f"- Total forks: {stats['total_forks']}",
        "",
        "### Top Languages",
    ]

    if top_languages:
        for language in top_languages:
            lines.append(f"- {language['name']}: {language['bytes']:,} bytes")
    else:
        lines.append("- No language data available")

    if repos:
        lines.extend(
            [
                "",
                "### Recently Updated",
                *[f"- `{repo.full_name}`" for repo in repos[:5]],
            ]
        )

    lines.append("")
    lines.append(f"*Last updated: {generated}*")
    return "\n".join(lines)


def format_metrics_markdown(stats: Dict, frameworks: Dict[str, int]) -> str:
    """Format daily metrics as Markdown for README injection."""
    repo_stats = stats["repositories_by_research_area"]
    star_stats = stats["stars_by_research_area"]
    generated = now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = ["### Research Area Breakdown"]
    for key in ("stochastic", "dynamical", "probability", "computing", "finance", "other"):
        lines.append(
            f"- {CATEGORY_LABELS[key]}: {repo_stats[key]} repos ({star_stats[key]} stars)"
        )

    lines.extend(
        [
            "",
            "### Framework Usage",
            f"- TensorFlow: {frameworks['tensorflow']} projects",
            f"- PyTorch: {frameworks['pytorch']} projects",
            f"- NumPy: {frameworks['numpy']} projects",
            f"- SciPy: {frameworks['scipy']} projects",
            f"- MATLAB: {frameworks['matlab']} projects",
            "",
            "### Primary Languages",
        ]
    )

    for language in stats["top_languages"]:
        lines.append(f"- {language['name']}: {language['bytes']:,} bytes")

    lines.append("")
    lines.append(f"*Last updated: {generated}*")
    return "\n".join(lines)


def inject_section(readme_path: Path, start_marker: str, end_marker: str, body: str) -> bool:
    """Replace a marker-delimited section in the README."""
    try:
        content = readme_path.read_text(encoding="utf-8")
        if start_marker not in content or end_marker not in content:
            print(f"WARNING: Markers not found: {start_marker} ... {end_marker}")
            return False

        start_idx = content.find(start_marker) + len(start_marker)
        end_idx = content.find(end_marker)
        updated_content = content[:start_idx] + "\n" + body + "\n" + content[end_idx:]
        readme_path.write_text(updated_content, encoding="utf-8")
        return True
    except Exception as exc:
        print(f"ERROR injecting README section: {exc}")
        return False


def save_metrics_json(stats: Dict) -> bool:
    """Persist raw metrics for inspection and workflow commits."""
    try:
        METRICS_OUTPUT.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        print(f"Saved metrics to {METRICS_OUTPUT}")
        return True
    except Exception as exc:
        print(f"ERROR saving metrics JSON: {exc}")
        return False


def main() -> bool:
    """Generate the README snapshot and metrics sections."""
    print(f"Generating profile snapshot for @{USERNAME}")
    print(f"Generated at: {now_utc().isoformat()}Z")

    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("ERROR: GITHUB_TOKEN environment variable not set")
        return False

    auth = Auth.Token(github_token)
    gh = Github(auth=auth)
    repos = get_tracked_repos(gh)
    if not repos:
        print("ERROR: no repositories found")
        return False

    categorized = categorize_repos(repos)
    frameworks = extract_frameworks(repos)
    stats = calculate_stats(repos, categorized)

    snapshot_markdown = format_snapshot_markdown(stats, repos)
    summary_markdown = format_portfolio_summary(stats, repos, categorized)
    metrics_markdown = format_metrics_markdown(stats, frameworks)

    snapshot_ok = inject_section(PROFILE_README, SNAPSHOT_START, SNAPSHOT_END, snapshot_markdown)
    summary_ok = inject_section(PROFILE_README, SUMMARY_START, SUMMARY_END, summary_markdown)
    metrics_ok = inject_section(PROFILE_README, METRICS_START, METRICS_END, metrics_markdown)
    json_ok = save_metrics_json(stats)

    if snapshot_ok and summary_ok and metrics_ok and json_ok:
        print("Profile snapshot generation complete")
        return True

    print("Profile snapshot generation failed")
    return False


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
