
from lastfmng import ListChecker, StringChecker, RegexChecker

def test_ListChecker():
    c1 = ListChecker(["pop", "rock", "jazz"])
    assert "pop" in c1
    assert "rock" in c1
    assert "jazz" in c1

def test_StringChecker():
    c1 = StringChecker("pop, rock, jazz")
    assert "pop" in c1
    assert "rock" in c1
    assert "jazz" in c1

    c2 = StringChecker("pop rock jazz", " ")
    assert "pop" in c2
    assert "rock" in c2
    assert "jazz" in c2

def test_RegexChecker():
    c1 = RegexChecker("^([1-9][0-9])*[0-9]0s$")
    assert "80s" in c1
    assert "1980s" in c1
    assert "1880s" in c1
    assert "00s" in c1
    assert "2000s" in c1
    assert not "2001s" in c1
    assert not "81s" in c1
    assert not "1881s" in c1
    assert not "0080s" in c1
    assert not "080s" in c1

    c2 = RegexChecker("^[1-9][0-9]{3}$")
    assert not "0" in c2
    assert not "1" in c2
    assert not "10" in c2
    assert not "100" in c2
    assert "1000" in c2
    assert not "10000" in c2
    assert "2000" in c2
    assert "1995" in c2
    assert "2011" in c2
    assert "3587" in c2
    assert not "unknown" in c2
    assert not "0000" in c2


