def validate_login_credential(credential):
    """Require the session cookie used by Bilibili's read-only APIs."""
    if credential is None:
        raise ValueError("扫码登录未返回凭证")
    credential.raise_for_no_sessdata()
    return credential


def can_refresh_credential(credential) -> bool:
    """Cookie refresh requires both the CSRF token and refresh token."""
    return credential.has_bili_jct() and credential.has_ac_time_value()
