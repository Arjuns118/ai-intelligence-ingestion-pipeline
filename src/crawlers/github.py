import asyncio
import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

load_dotenv()

INPUT = Path("data/raw/arxiv_papers.json")
OUTPUT = Path("data/processed/research_papers.json")

GITHUB_API = "https://api.github.com"

# GitHub allows more search requests when authenticated.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_API_TOKEN")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "AI-Engineer-Demo-Pipeline",
}

if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"


STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "for", "to", "in",
    "on", "with", "from", "by", "using", "via", "is", "are",
    "as", "at", "we", "our", "this", "that", "into", "new",
    "towards", "toward", "based", "through", "learning"
}


def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def meaningful_tokens(text):
    words = normalize(text).split()
    return {
        word for word in words
        if len(word) >= 3 and word not in STOPWORDS
    }


def similarity(title, repo):
    """
    Score how closely a GitHub repository appears related
    to the research paper title.
    """

    title_norm = normalize(title)

    repo_name = repo.get("name", "")
    description = repo.get("description") or ""

    combined = f"{repo_name} {description}"

    combined_norm = normalize(combined)

    sequence_score = SequenceMatcher(
        None,
        title_norm,
        combined_norm
    ).ratio()

    title_tokens = meaningful_tokens(title)
    repo_tokens = meaningful_tokens(combined)

    if title_tokens:
        overlap = len(title_tokens & repo_tokens) / len(title_tokens)
    else:
        overlap = 0

    # Give stronger weight to meaningful word overlap.
    score = (0.45 * sequence_score) + (0.55 * overlap)

    return score, overlap


async def github_request(session, url, params=None):
    """
    Request GitHub API with retry handling.
    """

    for attempt in range(5):

        try:
            async with session.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:

                if response.status == 200:
                    return await response.json()

                if response.status == 403 or response.status == 429:
                    reset = response.headers.get("X-RateLimit-Reset")

                    if reset:
                        import time
                        wait = max(
                            1,
                            min(int(reset) - int(time.time()) + 1, 90)
                        )
                    else:
                        wait = min(60, 5 * (attempt + 1))

                    print(
                        f"GitHub rate limit reached. "
                        f"Waiting {wait}s..."
                    )

                    await asyncio.sleep(wait)
                    continue

                if response.status >= 500:
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)
                    continue

                return None

        except Exception as error:
            wait = min(30, 2 ** attempt)
            print(
                f"GitHub request error: {error}. "
                f"Retrying in {wait}s..."
            )
            await asyncio.sleep(wait)

    return None


async def find_repository(session, paper):
    title = paper.get("content", {}).get("title", "").strip()

    if not title:
        return None

    # Search GitHub using the exact paper title.
    search_queries = [
        f'"{title}"',
        title
    ]

    candidates = []

    for query in search_queries:

        data = await github_request(
            session,
            f"{GITHUB_API}/search/repositories",
            params={
                "q": query,
                "per_page": 10,
                "sort": "stars",
                "order": "desc"
            }
        )

        if not data:
            continue

        candidates.extend(data.get("items", []))

        # Stop if we found enough candidates.
        if candidates:
            break

    if not candidates:
        return None

    # Remove duplicate repositories.
    unique = {}

    for repo in candidates:
        full_name = repo.get("full_name")

        if full_name:
            unique[full_name] = repo

    candidates = list(unique.values())

    scored = []

    for repo in candidates:
        score, overlap = similarity(title, repo)

        scored.append(
            (
                score,
                overlap,
                repo
            )
        )

    scored.sort(
        key=lambda x: (x[0], x[1]),
        reverse=True
    )

    best_score, best_overlap, best_repo = scored[0]

    # Conservative matching:
    # We do NOT attach unrelated repositories just because
    # they have many stars.
    if best_score < 0.55 or best_overlap < 0.35:
        return None

    return {
        "url": best_repo.get("html_url"),
        "stars": best_repo.get("stargazers_count"),
        "repo_name": best_repo.get("full_name"),
        "match_score": round(best_score, 3),
        "token_overlap": round(best_overlap, 3),
    }


async def main():

    with open(INPUT, "r", encoding="utf-8") as f:
        papers = json.load(f)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Load existing results so the script can resume.
    existing = {}

    if OUTPUT.exists():
        try:
            with open(OUTPUT, "r", encoding="utf-8") as f:
                old_results = json.load(f)

            for item in old_results:
                title = item.get("content", {}).get("title")

                if title:
                    existing[title] = item

        except Exception:
            existing = {}

    results = []

    connector = aiohttp.TCPConnector(
        limit=3,
        ssl=False
    )

    async with aiohttp.ClientSession(
        connector=connector
    ) as session:

        for index, paper in enumerate(papers, start=1):

            content = paper.setdefault("content", {})
            title = content.get("title", "").strip()

            # Preserve an already verified GitHub match.
            old = existing.get(title)

            if old:
                old_content = old.get("content", {})

                if old_content.get("github_url"):
                    paper["content"]["github_url"] = (
                        old_content.get("github_url")
                    )

                    paper["content"]["github_stars"] = (
                        old_content.get("github_stars")
                    )

                    results.append(paper)

                    print(
                        f"[{index}/{len(papers)}] "
                        f"Already enriched: {title[:70]}"
                    )
                    continue

            print(
                f"[{index}/{len(papers)}] "
                f"Searching: {title[:80]}"
            )

            repo = await find_repository(
                session,
                paper
            )

            if repo:

                content["github_url"] = repo["url"]
                content["github_stars"] = repo["stars"]

                print(
                    f"  ✓ {repo['repo_name']} "
                    f"| stars={repo['stars']} "
                    f"| score={repo['match_score']}"
                )

            else:

                content["github_url"] = None
                content["github_stars"] = None

                print("  - No sufficiently reliable repository match")

            results.append(paper)

            # Save progress after every paper.
            with open(OUTPUT, "w", encoding="utf-8") as f:
                json.dump(
                    results,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            # Small delay to be polite to GitHub.
            await asyncio.sleep(1)

    matched = sum(
        1
        for item in results
        if item.get("content", {}).get("github_url")
    )

    stars = sum(
        1
        for item in results
        if item.get("content", {}).get("github_stars") is not None
    )

    print("\n================================")
    print("GitHub enrichment complete")
    print("================================")
    print("Papers:", len(results))
    print("GitHub repositories:", matched)
    print("GitHub star values:", stars)
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    asyncio.run(main())