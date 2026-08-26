import unittest

from pydantic import ValidationError

from auth.models import TokenCreateRequest


class AuthModelsTest(unittest.TestCase):
    def test_manual_token_requires_exactly_32_characters(self) -> None:
        request = TokenCreateRequest(name="Valid App", token="k" * 32)
        self.assertEqual(request.token, "k" * 32)

        for invalid_token in ("k" * 31, "k" * 33, f" {'k' * 30} "):
            with self.subTest(token_length=len(invalid_token)):
                with self.assertRaises(ValidationError):
                    TokenCreateRequest(name="Invalid App", token=invalid_token)


if __name__ == "__main__":
    unittest.main()
