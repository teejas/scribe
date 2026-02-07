from scribe.notes import _escape_applescript


def test_escape_applescript_quotes():
    assert _escape_applescript('say "hello"') == 'say \\"hello\\"'


def test_escape_applescript_backslashes():
    assert _escape_applescript("path\\to\\file") == "path\\\\to\\\\file"


def test_escape_applescript_plain():
    assert _escape_applescript("normal text") == "normal text"


def test_escape_applescript_mixed():
    assert _escape_applescript('a "b" c\\d') == 'a \\"b\\" c\\\\d'
