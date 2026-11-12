"""UnifiClient's Site Manager (cloud) path: Site Manager for sites, then the
connector to each console's Network Integration API for everything else.

No database needed - the client only reads controller_type and api_key, and
HTTP goes through a fake session. Response bodies mirror real Integration API
shapes (Network 10.6) with made-up ids.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services import unifi
from app.services.unifi import UnifiClient, UnifiError

SM_SITE = "6650a1b2c3d4e5f6a7b8c9d0"
HOST = "HOSTID:123"
ISITE = "88f7af54-0000-0000-0000-000000000001"
BASE = f"https://api.ui.com/v1/connector/consoles/{HOST}/proxy/network/integration/v1"

AP_ID = "94e4b31f-0000-0000-0000-0000000000aa"
GUEST_ID = "e73e3b1d-0000-0000-0000-0000000000c1"


class _Resp:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.text = str(self._body)
        self.content = b"{}" if body is not None else b""

    def json(self):
        return self._body


def _page(items, total=None, offset=0):
    return {"offset": offset, "limit": 200, "count": len(items),
            "totalCount": len(items) if total is None else total, "data": items}


class FakeSession:
    """Routes (method, url) to canned bodies; records every call."""

    def __init__(self, routes):
        self.routes = routes
        self.headers = {}
        self.calls = []

    def _handle(self, method, url, params=None, json=None, **_):
        self.calls.append((method, url, params, json))
        handler = self.routes.get((method, url))
        if handler is None:
            return _Resp(404, {"message": "404 page not found"})
        return handler(params or {}, json) if callable(handler) else _Resp(200, handler)

    def get(self, url, **kw):
        return self._handle("GET", url, **kw)

    def post(self, url, **kw):
        return self._handle("POST", url, **kw)


def _clients_route(clients):
    def handler(params, _json):
        flt = params.get("filter")
        if flt:
            mac = flt.split("'")[1]
            return _Resp(200, _page([c for c in clients if c["macAddress"] == mac]))
        return _Resp(200, _page(clients))
    return handler


GUEST_CLIENT = {
    "type": "WIRELESS", "id": GUEST_ID, "name": "guest-phone",
    "connectedAt": "2026-11-12T06:00:00Z", "ipAddress": "10.0.50.23",
    "macAddress": "aa:bb:cc:00:00:01", "uplinkDeviceId": AP_ID,
    "access": {"type": "GUEST", "authorized": False},
}
STAFF_CLIENT = {
    "type": "WIRELESS", "id": "c-staff", "name": "laptop",
    "connectedAt": "2026-11-12T05:00:00Z", "ipAddress": "10.0.0.5",
    "macAddress": "aa:bb:cc:00:00:02", "uplinkDeviceId": AP_ID,
    "access": {"type": "DEFAULT"},
}
WIRED_CLIENT = {
    "type": "WIRED", "id": "c-nas", "name": "nas", "connectedAt": "2026-07-09T07:41:20Z",
    "ipAddress": "10.0.0.2", "macAddress": "aa:bb:cc:00:00:03", "access": {"type": "DEFAULT"},
}


def _routes(**overrides):
    routes = {
        ("GET", "https://api.ui.com/ea/sites"): {"data": [
            {"siteId": SM_SITE, "hostId": HOST, "meta": {"name": "default", "desc": "Default"}},
        ]},
        ("GET", f"{BASE}/sites"): lambda params, _j: _Resp(200, _page(
            [{"id": ISITE, "internalReference": "default", "name": "Default"}]
            if params.get("filter") == "internalReference.eq('default')" else []
        )),
        ("GET", f"{BASE}/sites/{ISITE}/devices"): _page([
            {"id": AP_ID, "macAddress": "11:22:33:44:55:66", "name": "Outdoor AP", "model": "UAP-AC-Lite"},
        ]),
        ("GET", f"{BASE}/sites/{ISITE}/clients"): _clients_route([GUEST_CLIENT, STAFF_CLIENT, WIRED_CLIENT]),
        ("GET", f"{BASE}/sites/{ISITE}/wifi/broadcasts"): _page([
            {"name": "Home", "type": "STANDARD", "enabled": True},
            {"name": "Captive Test", "type": "STANDARD", "enabled": False, "hotspotConfiguration": {}},
        ]),
        ("POST", f"{BASE}/sites/{ISITE}/clients/{GUEST_ID}/actions"): {"grantedAuthorization": {}},
    }
    routes.update(overrides)
    return routes


@pytest.fixture
def cloud():
    """A cloud UnifiClient wired to a FakeSession; returns (client, session)."""
    def build(routes=None):
        controller = SimpleNamespace(controller_type="cloud", api_key="test-key")
        client = UnifiClient(controller)
        session = FakeSession(routes or _routes())
        session.headers.update(client._session.headers)
        client._session = session
        return client, session
    return build


def test_cloud_site_resolved_once_and_cached(cloud):
    client, session = cloud()
    client.get_wlans(SM_SITE)
    client.get_wlans(SM_SITE)
    lookups = [c for c in session.calls if c[1] in ("https://api.ui.com/ea/sites", f"{BASE}/sites")]
    assert len(lookups) == 2  # one Site Manager lookup + one site match, then cached


def test_unknown_site_raises(cloud):
    client, _ = cloud()
    with pytest.raises(UnifiError, match="not visible"):
        client.get_wlans("not-a-site")


def test_site_without_matching_internal_reference_raises(cloud):
    routes = _routes()
    routes[("GET", "https://api.ui.com/ea/sites")] = {"data": [
        {"siteId": SM_SITE, "hostId": HOST, "meta": {"name": "branch"}},
    ]}
    client, _ = cloud(routes)
    with pytest.raises(UnifiError, match="internal name 'branch'"):
        client.get_wlans(SM_SITE)


def test_wlans_flag_hotspot_ssids_as_guest(cloud):
    client, _ = cloud()
    assert client.get_ssid_names(SM_SITE) == ["Captive Test", "Home"]
    assert client.get_guest_ssid_names(SM_SITE) == ["Captive Test"]


def test_active_clients_normalised_to_internal_api_fields(cloud):
    client, _ = cloud()
    with patch.object(unifi, "datetime", wraps=unifi.datetime) as dt:
        dt.now.return_value = unifi.datetime(2026, 11, 12, 6, 10, tzinfo=unifi.timezone.utc)
        clients = {c["mac"]: c for c in client.get_active_clients(SM_SITE)}

    guest = clients["aa:bb:cc:00:00:01"]
    assert guest == {
        "mac": "aa:bb:cc:00:00:01", "hostname": "guest-phone", "ip": "10.0.50.23",
        "essid": None, "ap_mac": "11:22:33:44:55:66", "uptime": 600, "signal": None,
        "authorized": False, "is_guest": True, "is_wired": False,
    }
    assert clients["aa:bb:cc:00:00:02"]["is_guest"] is False
    assert clients["aa:bb:cc:00:00:03"]["is_wired"] is True
    assert client.reports_client_ssid is False


def test_integration_list_follows_pages(cloud, monkeypatch):
    monkeypatch.setattr(unifi, "_INTEGRATION_PAGE_SIZE", 2)
    pages = {0: [GUEST_CLIENT, STAFF_CLIENT], 2: [WIRED_CLIENT]}
    routes = _routes()
    routes[("GET", f"{BASE}/sites/{ISITE}/clients")] = (
        lambda params, _j: _Resp(200, _page(pages[params["offset"]], total=3, offset=params["offset"]))
    )
    client, session = cloud(routes)
    assert len(client.get_active_clients(SM_SITE)) == 3
    offsets = [c[2]["offset"] for c in session.calls if c[1] == f"{BASE}/sites/{ISITE}/clients"]
    assert offsets == [0, 2]


def test_devices_flattened_with_mac(cloud):
    client, _ = cloud()
    assert client.get_devices(SM_SITE) == [
        {"mac": "11:22:33:44:55:66", "name": "Outdoor AP", "model": "UAP-AC-Lite", "id": AP_ID},
    ]


def test_authorize_guest_posts_client_action(cloud):
    client, session = cloud()
    client.authorize_guest(SM_SITE, "AA:BB:CC:00:00:01", minutes=90, up_kbps=1_000, down_kbps=500_000)

    lookup = next(c for c in session.calls if c[1] == f"{BASE}/sites/{ISITE}/clients")
    assert lookup[2] == {"filter": "macAddress.eq('aa:bb:cc:00:00:01')"}
    method, url, _params, body = session.calls[-1]
    assert (method, url) == ("POST", f"{BASE}/sites/{ISITE}/clients/{GUEST_ID}/actions")
    assert body == {
        "action": "AUTHORIZE_GUEST_ACCESS",
        "timeLimitMinutes": 90,
        "rxRateLimitKbps": 100_000,  # download, clamped to the API maximum
        "txRateLimitKbps": 1_000,    # upload
    }


def test_authorize_guest_omits_unset_limits(cloud):
    client, session = cloud()
    client.authorize_guest(SM_SITE, "aa:bb:cc:00:00:01", minutes=60)
    assert session.calls[-1][3] == {"action": "AUTHORIZE_GUEST_ACCESS", "timeLimitMinutes": 60}


def test_unauthorize_guest_posts_client_action(cloud):
    client, session = cloud()
    client.unauthorize_guest(SM_SITE, "aa:bb:cc:00:00:01")
    assert session.calls[-1][3] == {"action": "UNAUTHORIZE_GUEST_ACCESS"}


def test_guest_action_for_disconnected_device_raises(cloud):
    client, session = cloud()
    with pytest.raises(UnifiError, match="not connected"):
        client.authorize_guest(SM_SITE, "de:ad:be:ef:00:00")
    assert not any(c[0] == "POST" for c in session.calls)


def test_api_error_surfaces_as_unifi_error(cloud):
    routes = _routes()
    routes[("POST", f"{BASE}/sites/{ISITE}/clients/{GUEST_ID}/actions")] = (
        lambda _p, _j: _Resp(400, {"message": "Client is not a guest"})
    )
    client, _ = cloud(routes)
    with pytest.raises(UnifiError, match="HTTP 400"):
        client.authorize_guest(SM_SITE, "aa:bb:cc:00:00:01")


def test_self_hosted_authorize_still_uses_stamgr():
    controller = SimpleNamespace(
        controller_type="self_hosted", url="https://unifi.local", verify_ssl=True,
        auth_mode="api_key", api_key="k",
    )
    client = UnifiClient(controller)
    with patch.object(client, "_post", return_value={}) as post:
        client.authorize_guest("default", "AA:BB:CC:00:00:01", minutes=30, up_kbps=5, down_kbps=10)
    post.assert_called_once_with("default", "cmd/stamgr", {
        "cmd": "authorize-guest", "mac": "aa:bb:cc:00:00:01", "minutes": 30, "up": 5, "down": 10,
    })
    assert client.reports_client_ssid is True
