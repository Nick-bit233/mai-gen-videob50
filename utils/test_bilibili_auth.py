import unittest

from utils.bilibili_auth import can_refresh_credential, validate_login_credential


class FakeCredential:
    def __init__(self, *, sessdata=True, bili_jct=False, ac_time_value=False):
        self._sessdata = sessdata
        self._bili_jct = bili_jct
        self._ac_time_value = ac_time_value

    def raise_for_no_sessdata(self):
        if not self._sessdata:
            raise ValueError("missing SESSDATA")

    def has_bili_jct(self):
        return self._bili_jct

    def has_ac_time_value(self):
        return self._ac_time_value


class BilibiliCredentialValidationTests(unittest.TestCase):
    def test_login_accepts_read_only_credential_without_bili_jct(self):
        credential = FakeCredential(sessdata=True, bili_jct=False)

        self.assertIs(validate_login_credential(credential), credential)

    def test_login_rejects_missing_sessdata(self):
        with self.assertRaisesRegex(ValueError, "missing SESSDATA"):
            validate_login_credential(FakeCredential(sessdata=False, bili_jct=True))

    def test_refresh_requires_bili_jct_and_refresh_token(self):
        self.assertTrue(
            can_refresh_credential(
                FakeCredential(bili_jct=True, ac_time_value=True)
            )
        )
        self.assertFalse(
            can_refresh_credential(
                FakeCredential(bili_jct=False, ac_time_value=True)
            )
        )
        self.assertFalse(
            can_refresh_credential(
                FakeCredential(bili_jct=True, ac_time_value=False)
            )
        )


if __name__ == "__main__":
    unittest.main()
