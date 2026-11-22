from parzprint.translate.languages import AUTO, LANGUAGES, name_of, ordered, push_recent


def test_languages_contents():
    codes = [c for c, _ in LANGUAGES]
    assert len(codes) >= 100 and len(set(codes)) == len(codes) and AUTO not in codes
    assert dict(LANGUAGES)["en"] == "Inglês" and dict(LANGUAGES)["pt"] == "Português"
    assert {"es", "fr", "de", "it", "ja", "ko", "zh-CN", "zh-TW", "ru", "ar"} <= set(codes)


def test_languages_sorted_without_accents():
    names = [n for _, n in LANGUAGES]
    assert names.index("Árabe") < names.index("Armênio") < names.index("Basco")


def test_name_of():
    assert name_of("auto") == "Detectar idioma" and name_of("en") == "Inglês"
    assert name_of("xx") == "xx"


def test_ordered_recent_first():
    out = ordered(["ja", "xx", "en"], with_auto=True)
    assert [c for c, _ in out[:3]] == ["auto", "ja", "en"] and len({c for c, _ in out}) == len(out)
    assert ordered([], with_auto=False)[0] == LANGUAGES[0]


def test_push_recent():
    assert push_recent(["en", "ja", "es", "fr", "de"], "it") == ["it", "en", "ja", "es", "fr"]
    assert push_recent(["en"], "auto") == ["en"] and push_recent(["en", "ja"], "ja") == ["ja", "en"]
