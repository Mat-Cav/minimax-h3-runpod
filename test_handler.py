import pytest
from handler import _build_prompt, _validate

def test_validates_ugc_input():
    assert _validate({"image": "https://example.com/a.jpg", "dialogue": "Oi mundo", "seconds": 15}) == ("https://example.com/a.jpg", "Oi mundo", 15, "9:16")

def test_rejects_dialogue_over_cap():
    with pytest.raises(ValueError, match="40 words"):
        _validate({"image": "https://example.com/a.jpg", "dialogue": "word " * 41})

def test_prompt_contains_spoken_copy():
    prompt = _build_prompt({}, "Isso mudou minha rotina.")
    assert "Brazilian Portuguese" in prompt
    assert '"Isso mudou minha rotina."' in prompt
