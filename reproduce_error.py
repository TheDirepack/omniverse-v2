from typing import Dict, Optional

def build_freshness_comparison_report(url_content_map: Dict[str, Optional[str]]) -> str:
    reports = []
    for url, content in url_content_map.items():
        if content is None:
            reports.append(f"CANDIDATE: {url}\nUnavailable (fetch budget exhausted or fetch failed).")
            continue
        if "[END SIGNALS]" in content:
            signal_block = content.split("[END SIGNALS]")[0] + "[END SIGNALS]"
        else:
            signal_block = content[:500]
        reports.append(f"CANDIDATE: {url}\n{signal_block}")

    return (
        "Compare these candidates. Prefer sources with NO staleness warning, "
        "a recent Last-Modified/'last edited' signal, and no unresolved 'moved' notice. "
        "A source that a redirect or canonical tag points AWAY from is likely the stale one, "
        "even if it ranked first in search results.\n\n" + "\n\n".join(reports)
    )

try:
    # Try with a slice object instead of a string
    build_freshness_comparison_report({"url1": slice(None, 500, None)})
except Exception as e:
    print(f"Caught exception: {type(e)} - {e}")

try:
    # Try with something else
    build_freshness_comparison_report({"url1": 123})
except Exception as e:
    print(f"Caught exception: {type(e)} - {e}")
