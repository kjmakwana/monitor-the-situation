# tests/test_correlation_engine.py

import pytest
from ingestion.correlation_engine import (
    classify_military,
    classify_region,
    classify_tickers,
    enrich_article,
)


class TestClassifyRegion:
    def test_unambiguous_title_match(self):
        assert classify_region("Ukraine war update", "", "global") == "europe"

    def test_capital_city_match(self):
        assert classify_region("Talks in Riyadh on oil output", "", "global") == "middle_east"

    def test_summary_only_match(self):
        assert classify_region("Markets react to latest news", "Pakistan and India trade tensions rise", "global") == "s_asia"

    def test_title_dominates_summary(self):
        # Title: China (apac x3). Summary: mentions europe once. apac should win.
        assert classify_region("China expands naval presence", "European leaders expressed concern.", "global") == "apac"

    def test_no_match_returns_fallback(self):
        assert classify_region("Breaking news", "Something happened somewhere.", "se_asia") == "se_asia"

    def test_multi_phrase_highest_count_wins(self):
        # Iran + Tehran + Riyadh → middle_east (3 hits) beats europe (0)
        assert classify_region("Iran and Saudi discuss deal", "Tehran and Riyadh met yesterday.", "global") == "middle_east"

    def test_tie_returns_fallback(self):
        # Construct a genuine tie: exactly equal hits for two regions, fallback is source
        result = classify_region("Russia Iran deal", "Moscow Tehran pipeline.", "americas")
        # europe: russia, moscow = 2 hits (×3 title + summary). middle_east: iran, tehran = 2 hits
        # title×3: "russia iran deal russia iran deal russia iran deal" → russia×3, iran×3
        # summary: "moscow tehran pipeline" → moscow×1, tehran×1
        # europe: russia×3 + moscow×1 = 4. middle_east: iran×3 + tehran×1 = 4 → tie → fallback
        assert result == "americas"

    def test_case_insensitive(self):
        assert classify_region("UKRAINE UPDATE", "KYIV SIEGE", "global") == "europe"

    def test_multi_word_phrase(self):
        assert classify_region("Tensions in South China Sea rise", "", "global") == "apac"


class TestClassifyMilitary:
    def test_keyword_in_title_promotes(self):
        assert classify_military("Airstrike hits city", "", False) is True

    def test_keyword_in_summary_promotes(self):
        assert classify_military("Update from the region", "Troops deployed along the border.", False) is True

    def test_feed_level_true_preserved(self):
        assert classify_military("Diplomatic meeting", "Trade talks concluded.", True) is True

    def test_no_keyword_returns_false(self):
        assert classify_military("Trade deal signed", "The agreement covers agriculture.", False) is False

    def test_case_insensitive(self):
        assert classify_military("MISSILE LAUNCH DETECTED", "", False) is True

    def test_partial_word_no_match(self):
        # "wars" should not match "war" keyword via word boundary
        assert classify_military("The culture wars debate", "Award ceremony for journalists.", False) is False


class TestClassifyTickers:
    def test_known_keyword_returns_tickers(self):
        result = classify_tickers("Iran sanctions discussed", "")
        assert "BRENT" in result
        assert "WTI" in result

    def test_unknown_text_returns_empty(self):
        assert classify_tickers("Local council meeting", "Road repair budget approved.") == []

    def test_deduplication(self):
        # "iran" and "iraq" both map to BRENT — should appear only once
        result = classify_tickers("Iran and Iraq oil deal", "")
        assert result.count("BRENT") == 1

    def test_multiple_keywords_aggregate(self):
        result = classify_tickers("Ukraine wheat crisis", "Russia natural gas supplies cut.")
        assert "WHEAT" in result
        assert "NATGAS" in result

    def test_returns_list(self):
        assert isinstance(classify_tickers("China trade", ""), list)


class TestEnrichArticle:
    def _base(self, **overrides):
        base = {
            "title": "",
            "summary": "",
            "region": "global",
            "is_military": False,
        }
        base.update(overrides)
        return base

    def test_region_overridden_from_content(self):
        article = self._base(title="Nigeria oil spill crisis", region="global")
        result = enrich_article(article)
        assert result["region"] == "africa"

    def test_military_promoted_by_content(self):
        article = self._base(title="Drone strikes hit warehouse", region="global")
        result = enrich_article(article)
        assert result["is_military"] is True

    def test_tickers_populated(self):
        article = self._base(title="Saudi Arabia cuts oil production", region="middle_east")
        result = enrich_article(article)
        assert result["tickers"] is not None
        assert "BRENT" in result["tickers"]

    def test_no_match_tickers_is_none(self):
        article = self._base(title="Local sports results", summary="Home team wins again.")
        result = enrich_article(article)
        assert result["tickers"] is None

    def test_no_geo_match_preserves_region(self):
        article = self._base(title="Markets open mixed", region="s_asia")
        result = enrich_article(article)
        assert result["region"] == "s_asia"

    def test_returns_same_dict(self):
        article = self._base(title="Germany election results")
        result = enrich_article(article)
        assert result is article  # mutates and returns same object
