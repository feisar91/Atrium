from app.extensions import db
from app.models import UserRole, PlatformSetting
from tests.factories import make_user


def _reset_display_settings() -> None:
    """Delete any existing timezone/date_format PlatformSetting rows so a
    test starts from the default. Needed because these rows can leak across
    tests under the current db_session fixture's isolation gap - same
    pattern as session_remember_days / email_settings elsewhere in this
    suite."""
    for key in ("timezone", "date_format"):
        existing = db.session.get(PlatformSetting, key)
        if existing:
            db.session.delete(existing)
    db.session.commit()


def test_update_settings_rejects_invalid_timezone(client, db_session, auth_headers):
    _reset_display_settings()
    admin = make_user(role=UserRole.SUPERADMIN)
    resp = client.put(
        "/api/settings", json={"timezone": "Not/AZone"}, headers=auth_headers(admin)
    )
    assert resp.status_code == 400
    assert "timezone" in resp.get_json()["error"].lower()


def test_update_settings_accepts_valid_timezone(client, db_session, auth_headers):
    _reset_display_settings()
    admin = make_user(role=UserRole.SUPERADMIN)
    resp = client.put(
        "/api/settings", json={"timezone": "Australia/Sydney"}, headers=auth_headers(admin)
    )
    assert resp.status_code == 200
    assert resp.get_json()["timezone"]["value"] == "Australia/Sydney"


def test_update_settings_rejects_invalid_date_format(client, db_session, auth_headers):
    _reset_display_settings()
    admin = make_user(role=UserRole.SUPERADMIN)
    resp = client.put(
        "/api/settings", json={"date_format": "DD-MM-YY"}, headers=auth_headers(admin)
    )
    assert resp.status_code == 400
    assert "date format" in resp.get_json()["error"].lower()


def test_update_settings_accepts_valid_date_format(client, db_session, auth_headers):
    _reset_display_settings()
    admin = make_user(role=UserRole.SUPERADMIN)
    resp = client.put(
        "/api/settings", json={"date_format": "DD/MM/YYYY"}, headers=auth_headers(admin)
    )
    assert resp.status_code == 200
    assert resp.get_json()["date_format"]["value"] == "DD/MM/YYYY"


def test_get_display_settings_defaults(client, db_session, auth_headers):
    _reset_display_settings()
    user = make_user(role=UserRole.CLIENT)
    resp = client.get("/api/settings/display", headers=auth_headers(user))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["timezone"] == "UTC"
    assert body["date_format"] == "MM/DD/YYYY"


def test_get_display_settings_reachable_by_non_superadmin(client, db_session, auth_headers):
    _reset_display_settings()
    admin = make_user(role=UserRole.SUPERADMIN)
    client.put(
        "/api/settings",
        json={"timezone": "America/New_York", "date_format": "YYYY-MM-DD"},
        headers=auth_headers(admin),
    )

    client_user = make_user(role=UserRole.CLIENT)
    resp = client.get("/api/settings/display", headers=auth_headers(client_user))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["timezone"] == "America/New_York"
    assert body["date_format"] == "YYYY-MM-DD"


def test_get_display_settings_requires_auth(client, db_session):
    resp = client.get("/api/settings/display")
    assert resp.status_code == 401


# ── /settings/my-ip: Docker gateway detection ────────────────────────────────

_ROUTE_TABLE = (
    "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
    "eth0\t00000000\t010013AC\t0003\t0\t0\t0\t00000000\t0\t0\t0\n"   # default via 172.19.0.1
    "eth0\t000013AC\t00000000\t0001\t0\t0\t0\t0000FFFF\t0\t0\t0\n"   # 172.19.0.0/16 link
)


def _patch_route_table(monkeypatch, content):
    import builtins
    import io
    from app.api import settings as settings_mod

    real_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if path == "/proc/net/route":
            if content is None:
                raise FileNotFoundError(path)
            return io.StringIO(content)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)
    settings_mod._container_gateway_ip.cache_clear()
    return settings_mod


def test_container_gateway_ip_parses_default_route(monkeypatch):
    settings_mod = _patch_route_table(monkeypatch, _ROUTE_TABLE)
    try:
        assert settings_mod._container_gateway_ip() == "172.19.0.1"
    finally:
        settings_mod._container_gateway_ip.cache_clear()


def test_container_gateway_ip_none_without_route_table(monkeypatch):
    settings_mod = _patch_route_table(monkeypatch, None)
    try:
        assert settings_mod._container_gateway_ip() is None
    finally:
        settings_mod._container_gateway_ip.cache_clear()


def test_my_ip_flags_docker_gateway(client, monkeypatch):
    settings_mod = _patch_route_table(monkeypatch, _ROUTE_TABLE)
    try:
        resp = client.get("/api/settings/my-ip", headers={"X-Real-IP": "172.19.0.1"})
        assert resp.get_json() == {"ip": "172.19.0.1", "is_proxy_gateway": True}

        resp = client.get("/api/settings/my-ip", headers={"X-Real-IP": "192.168.1.50"})
        assert resp.get_json() == {"ip": "192.168.1.50", "is_proxy_gateway": False}
    finally:
        settings_mod._container_gateway_ip.cache_clear()
