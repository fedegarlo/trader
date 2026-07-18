from datetime import date

from trader.prices import PriceCache


def test_history_reads_cached_closes_in_range(tmp_path):
    (tmp_path / "AAPL.csv").write_text(
        "date,close\n2026-07-13,10\n2026-07-14,11\n2026-07-15,12\n2026-07-20,13\n")
    cache = PriceCache(cache_dir=str(tmp_path), offline=True)
    hist = cache.history("AAPL", date(2026, 7, 14), date(2026, 7, 16))
    assert hist == [(date(2026, 7, 14), 11.0), (date(2026, 7, 15), 12.0)]


def test_history_empty_when_no_cache(tmp_path):
    cache = PriceCache(cache_dir=str(tmp_path), offline=True)
    assert cache.history("NOPE", date(2026, 1, 1), date(2026, 12, 31)) == []
