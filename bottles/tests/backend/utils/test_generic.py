import pytest

from bottles.backend.utils.generic import detect_encoding


# CP932 is superset of Shift-JIS, which is default codec for Japanese in Windows
# GBK is default codec for Chinese in Windows
@pytest.mark.parametrize(
    "text, hint, codec",
    [
        ("Hello, world!", None, "ascii"),
        ("   ", None, "ascii"),
        ("Привет, мир!", None, "windows-1251"),
        ("こんにちは、世界！", "ja_JP", "cp932"),
        ("こんにちは、世界！", "ja_JP.utf-8", "utf-8"),
        ("你好，世界！", "zh_CN", "gbk"),
        ("你好，世界！", "zh_CN.UTF-8", "utf-8"),
        ("你好，世界！", "zh_CN.invalid_fallback", "gbk"),
        ("", None, "utf-8"),
    ],
)
def test_detect_encoding(text: str, hint: str | None, codec: str | None):
    text_bytes = text.encode(codec)
    guess = detect_encoding(text_bytes, hint)
    assert guess.lower() == codec.lower()
