import pytest

from utils.text import compress_and_encode, mask_card_number, mask_pattern, mask_series_code


class TestTextUtils:
    def test_mask_pattern_match_returns_masked_text(self) -> None:
        text = 'Username="mario_1234"'
        masked_text = mask_pattern(text, r'(?<=Username=")\w+(?=")')

        assert masked_text == 'Username="**********"'

    @pytest.mark.parametrize("text", ['Username="!@$$%^&*()"', 'Name="mario_1234"'])
    def test_mask_pattern_no_match_returns_input_text(self, text: str) -> None:
        assert mask_pattern(text, r'(?<=Username=")\w+(?=")') == text

    def test_mask_card_number_match_returns_masked_text(self) -> None:
        text = 'CardNumber="123456789"'
        masked_text = mask_card_number(text)

        assert masked_text == 'CardNumber="*****6789"'

    @pytest.mark.parametrize("text", ['CardNumber="abcdefghi"', 'Number="123456789"'])
    def test_mask_card_number_no_match_returns_input_text(self, text: str) -> None:
        assert mask_card_number(text) == text

    def test_mask_series_code_match_returns_masked_text(self) -> None:
        text = 'SeriesCode="123456789"'
        masked_text = mask_series_code(text)

        assert masked_text == 'SeriesCode="*********"'

    @pytest.mark.parametrize("text", ['SeriesCode="abcdefghi"', 'Code="123456789"'])
    def test_mask_series_code_no_match_returns_input_text(self, text: str) -> None:
        assert mask_series_code(text) == text

    @pytest.mark.parametrize(
        ("text", "result"),
        [
            ("This is a test string.", "eJwLycgsVgCiRIWS1OISheKSosy8dD0AWSQH2w=="),
            (b"This is a test string.", "eJwLycgsVgCiRIWS1OISheKSosy8dD0AWSQH2w=="),
        ],
    )
    def test_compress_and_encode(self, text: str, result: str) -> None:
        assert compress_and_encode(text) == result
