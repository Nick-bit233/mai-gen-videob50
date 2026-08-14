def validate_login_credential(credential):
    """Validate the minimum credential required for authenticated read/download APIs."""
    if credential is None:
        raise ValueError("未获取到 Bilibili 登录凭证")
    credential.raise_for_no_sessdata()
    return credential


def can_refresh_credential(credential) -> bool:
    """Refreshing cookies requires both CSRF and a refresh token."""
    return credential.has_bili_jct() and credential.has_ac_time_value()
