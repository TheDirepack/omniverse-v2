import pytest

from app.db.unconfirmed_session import init_unconfirmed_db


@pytest.fixture(autouse=True)
def setup_unconfirmed_db():
    init_unconfirmed_db()
    return

def test_build_freshness_comparison_report_prefers_fresh_over_none():
    from app.core.tools import build_freshness_comparison_report

    report = build_freshness_comparison_report(
        {
            "http://fresh.example": (
                "[SOURCE FRESHNESS SIGNALS]\nStaleness warning: none detected"
                "\n[END SIGNALS]\nBody text here"
            ),
            "http://unavailable.example": None,
        }
    )

    assert "CANDIDATE: http://fresh.example" in report
    assert "Staleness warning: none detected" in report
    assert (
        "Body text here" not in report
    )  # only the signal block, not the full page, is included
    assert "CANDIDATE: http://unavailable.example" in report
    assert "Unavailable" in report
