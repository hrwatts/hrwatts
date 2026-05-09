#!/usr/bin/env python3
"""
Generate custom GitHub profile metrics for trading/ML specialization.
Uses PyGithub to fetch GitHub data and generate domain-specific signals.
Designed to be run by GitHub Actions and inject metrics into profile README.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path

try:
    from github import Auth, Github
except ImportError:
    print("ERROR: PyGithub not installed. Run: pip install PyGithub")
    exit(1)


# Configuration
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print("ERROR: GITHUB_TOKEN environment variable not set")
    exit(1)

USERNAME = "hrwatts"
PROFILE_README = Path(__file__).parent.parent / "README.md"
METRICS_OUTPUT = Path(__file__).parent.parent / "metrics.json"

# Domain categorization
ACADEMIC_KEYWORDS = {
    "stochastic": ["stochastic", "brownian", "martingale", "markov", "poisson", "levy"],
    "dynamical": ["dynamical", "differential", "ode", "pde", "dynamics", "bifurcation"],
    "probability": ["probability", "probabilistic", "random", "bayesian", "inference"],
    "computing": ["computing", "numerical", "algorithm", "computation", "optimization"],
    "finance": ["trade", "algorithmic", "backtest", "quant", "forex", "stock", "portfolio", "risk"],
}

# Additional keywords for academic papers/theory
RESEARCH_LEVEL_KEYWORDS = {
    "theoretical": ["theory", "theorem", "mathematical", "rigorous", "proof", "analysis"],
    "applied": ["application", "empirical", "experiment", "data", "implementation"],
}

FRAMEWORK_KEYWORDS = {
    "tensorflow": ["tensorflow", "tf"],
    "pytorch": ["pytorch", "torch"],
    "matlab": ["matlab"],
    "numpy": ["numpy"],
    "scipy": ["scipy"],
}

FRAMEWORK_DISPLAY = [
    ("tensorflow", "TensorFlow"),
    ("pytorch", "PyTorch"),
    ("numpy", "NumPy"),
    ("scipy", "SciPy"),
    ("matlab", "MATLAB"),
]


def get_user_repos(gh: Github) -> List:
    """Fetch all public repositories for the user."""
    try:
        user = gh.get_user(USERNAME)
        repos = list(user.get_repos(sort="updated", direction="desc"))
        print(f"✓ Fetched {len(repos)} repositories")
        return repos
    except Exception as e:
        print(f"ERROR fetching repos: {e}")
        return []


def categorize_repos(repos: List) -> Dict[str, List]:
    """Categorize repos by academic research area."""
    categorized = {
        "stochastic": [],
        "dynamical": [],
        "probability": [],
        "computing": [],
        "finance": [],
        "other": [],
    }

    for repo in repos:
        name_lower = repo.name.lower()
        description = (repo.description or "").lower()
        full_text = f"{name_lower} {description}"

        categorized_flag = False
        for category, keywords in ACADEMIC_KEYWORDS.items():
            if any(kw in full_text for kw in keywords):
                categorized[category].append(repo)
                categorized_flag = True
                break

        if not categorized_flag:
            categorized["other"].append(repo)

    return categorized


def extract_frameworks(repos: List) -> Dict[str, int]:
    """Extract framework usage from repository descriptions/names."""
    frameworks = {framework: 0 for framework in FRAMEWORK_KEYWORDS}

    for repo in repos:
        name_lower = repo.name.lower()
        description = (repo.description or "").lower()
        full_text = f"{name_lower} {description}"

        for framework, keywords in FRAMEWORK_KEYWORDS.items():
            if any(kw in full_text for kw in keywords):
                frameworks[framework] += 1

    return frameworks


def calculate_stats(repos: List, categorized: Dict) -> Dict:
    """Calculate aggregate statistics by research area."""
    total_stars = sum(repo.stargazers_count for repo in repos)
    total_forks = sum(repo.forks_count for repo in repos)
    
    stochastic_stars = sum(repo.stargazers_count for repo in categorized["stochastic"])
    dynamical_stars = sum(repo.stargazers_count for repo in categorized["dynamical"])
    probability_stars = sum(repo.stargazers_count for repo in categorized["probability"])
    computing_stars = sum(repo.stargazers_count for repo in categorized["computing"])
    finance_stars = sum(repo.stargazers_count for repo in categorized["finance"])

    languages = {}
    for repo in repos:
        try:
            lang_dict = repo.get_languages()
            for lang, bytes_count in lang_dict.items():
                languages[lang] = languages.get(lang, 0) + bytes_count
        except Exception:
            pass  # Skip if language data unavailable

    top_languages = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_repositories": len(repos),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "repositories_by_research_area": {
            "stochastic_processes": len(categorized["stochastic"]),
            "dynamical_systems": len(categorized["dynamical"]),
            "applied_probability": len(categorized["probability"]),
            "statistical_computing": len(categorized["computing"]),
            "quantitative_finance": len(categorized["finance"]),
            "other": len(categorized["other"]),
        },
        "stars_by_research_area": {
            "stochastic_processes": stochastic_stars,
            "dynamical_systems": dynamical_stars,
            "applied_probability": probability_stars,
            "statistical_computing": computing_stars,
            "quantitative_finance": finance_stars,
            "other": sum(repo.stargazers_count for repo in categorized["other"]),
        },
        "top_languages": [{"name": lang, "bytes": bytes_count} for lang, bytes_count in top_languages],
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def format_metrics_markdown(stats: Dict, frameworks: Dict) -> str:
    """Format metrics as Markdown for injection into README."""
    repo_stats = stats["repositories_by_research_area"]
    star_stats = stats["stars_by_research_area"]
    framework_lines = "\n".join(
        f"- {label}: {frameworks.get(key, 0)} projects"
        for key, label in FRAMEWORK_DISPLAY
    )
    language_lines = "\n".join(
        f"- **{entry['name']}**: {entry['bytes']:,} bytes"
        for entry in stats["top_languages"]
    )

    markdown = f"""
### 📊 Research Portfolio Breakdown
- **Stochastic Processes**: {repo_stats['stochastic_processes']} repos ({star_stats['stochastic_processes']} ⭐)
- **Dynamical Systems**: {repo_stats['dynamical_systems']} repos ({star_stats['dynamical_systems']} ⭐)
- **Applied Probability**: {repo_stats['applied_probability']} repos ({star_stats['applied_probability']} ⭐)
- **Statistical Computing**: {repo_stats['statistical_computing']} repos ({star_stats['statistical_computing']} ⭐)
- **Quantitative Finance Applications**: {repo_stats['quantitative_finance']} repos ({star_stats['quantitative_finance']} ⭐)
- **Other Projects**: {repo_stats['other']} repos ({star_stats['other']} ⭐)

**Total**: {stats['total_repositories']} public repos • {stats['total_stars']} stars • {stats['total_forks']} forks

### 🔧 Framework & Library Usage
{framework_lines}

### 💻 Primary Languages
{language_lines}

*Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}*
"""
    return markdown.strip()


def inject_metrics_into_readme(readme_path: Path, metrics_markdown: str) -> bool:
    """Inject formatted metrics into README between markers."""
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Find markers
        start_marker = "<!-- START_METRICS -->"
        end_marker = "<!-- END_METRICS -->"

        if start_marker not in content or end_marker not in content:
            print(f"WARNING: Metrics markers not found in {readme_path}")
            return False

        # Replace content between markers
        start_idx = content.find(start_marker) + len(start_marker)
        end_idx = content.find(end_marker)

        updated_content = (
            content[:start_idx]
            + "\n" + metrics_markdown + "\n"
            + content[end_idx:]
        )

        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

        print(f"✓ Metrics injected into {readme_path}")
        return True

    except Exception as e:
        print(f"ERROR injecting metrics: {e}")
        return False


def save_metrics_json(stats: Dict) -> bool:
    """Save raw metrics as JSON for reference."""
    try:
        with open(METRICS_OUTPUT, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
        print(f"✓ Metrics saved to {METRICS_OUTPUT}")
        return True
    except Exception as e:
        print(f"ERROR saving metrics JSON: {e}")
        return False


def main():
    """Main execution flow."""
    print(f"🚀 Generating profile metrics for @{USERNAME}")
    print(f"Generated: {datetime.utcnow().isoformat()}Z\n")

    # Authenticate and fetch repos
    auth = Auth.Token(GITHUB_TOKEN)
    gh = Github(auth=auth)
    repos = get_user_repos(gh)

    if not repos:
        print("ERROR: No repositories found")
        return False

    # Categorize and analyze
    categorized = categorize_repos(repos)
    frameworks = extract_frameworks(repos)
    stats = calculate_stats(repos, categorized)

    print("\n📊 Metrics Summary:")
    print(f"  Stochastic: {stats['repositories_by_research_area']['stochastic_processes']} repos ({stats['stars_by_research_area']['stochastic_processes']} ⭐)")
    print(f"  Dynamical: {stats['repositories_by_research_area']['dynamical_systems']} repos ({stats['stars_by_research_area']['dynamical_systems']} ⭐)")
    print(f"  Probability: {stats['repositories_by_research_area']['applied_probability']} repos ({stats['stars_by_research_area']['applied_probability']} ⭐)")
    print(f"  Computing: {stats['repositories_by_research_area']['statistical_computing']} repos ({stats['stars_by_research_area']['statistical_computing']} ⭐)")
    print(f"  Finance: {stats['repositories_by_research_area']['quantitative_finance']} repos ({stats['stars_by_research_area']['quantitative_finance']} ⭐)")
    print(f"  Top Language: {stats['top_languages'][0]['name'] if stats['top_languages'] else 'N/A'}")

    # Generate and inject metrics
    metrics_markdown = format_metrics_markdown(stats, frameworks)
    inject_ok = inject_metrics_into_readme(PROFILE_README, metrics_markdown)
    save_ok = save_metrics_json(stats)

    if inject_ok and save_ok:
        print("\n✅ Profile metrics generation complete!")
        return True
    else:
        print("\n❌ Metrics generation failed")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
