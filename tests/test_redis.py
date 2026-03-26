from app.redis import normalize_text, cache_key


def test_normalize_text():
    assert normalize_text("  Hello   World  ") == "hello world"
    assert normalize_text("Hello\n\tWorld") == "hello world"


def test_cache_key_same_for_equivalent_text():
    key1 = cache_key("jd", "Hello World")
    key2 = cache_key("jd", "  hello   world  ")
    assert key1 == key2


def test_cache_key_different_for_different_text():
    key1 = cache_key("jd", "Hello World")
    key2 = cache_key("jd", "Goodbye World")
    assert key1 != key2
