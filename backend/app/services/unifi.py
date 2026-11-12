"""
Unifi API client - supports two controller types:

self_hosted  UniFi Network Application running on-premises or on a console.
             Auth: username/password (auto-detects UniFi OS vs legacy) or API key.
             Uses the Network application's internal API (/api/s/{site}/...).

cloud        UniFi Site Manager at api.ui.com.
             Auth: API key only, generated at unifi.ui.com → Settings → API Keys.
             Site Manager itself (/ea/...) only lists hosts and sites. Everything
             else goes through its connector to each console's official Network
             Integration API:
               api.ui.com/v1/connector/consoles/{hostId}/proxy/network/integration/v1/...
             The connector refuses the internal API for current keys ("v1 keys
             created after the v2 key release reach each application's public
             integration API only"), and the old /ea/clients/active and
             /ea/sites/{id}/cmd/stamgr routes do not exist.

             Integration API limits vs. self-hosted:
             - clients carry no SSID, so active devices can't be filtered per
               SSID (reports_client_ssid is False)
             - guests can only be authorized/unauthorized while connected, since
               the action targets a client id, not a MAC
             - no signal strength
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

CLOUD_API_BASE = "https://api.ui.com"

# Integration API list endpoints cap a page at 200 items.
_INTEGRATION_PAGE_SIZE = 200
# AUTHORIZE_GUEST_ACCESS accepts rate limits in this range (kbps).
_MIN_RATE_KBPS, _MAX_RATE_KBPS = 2, 100_000


class UnifiError(Exception):
    pass


class UnifiClient:
    def __init__(self, controller):
        self._is_cloud = getattr(controller, "controller_type", "self_hosted") == "cloud"
        self._session = requests.Session()

        if self._is_cloud:
            self.base_url = CLOUD_API_BASE
            self._session.headers.update({
                "X-API-Key": controller.api_key,
                "Content-Type": "application/json",
            })
            self._logged_in = True
            self._is_unifi_os = False  # not used for cloud path
            # Site Manager siteId -> (connector Integration API base, integration site id)
            self._cloud_sites: dict[str, tuple[str, str]] = {}
        else:
            self.base_url = controller.url.rstrip("/")
            self._session.verify = controller.verify_ssl
            self.auth_mode = getattr(controller, "auth_mode", "password")
            self._logged_in = False
            self._is_unifi_os = False

            if self.auth_mode == "api_key":
                self._session.headers.update({
                    "X-API-Key": controller.api_key,
                    "Content-Type": "application/json",
                })
                self._is_unifi_os = True
                self._logged_in = True
            else:
                self.username = controller.username
                self.password = controller.password

    # ── Self-hosted auth ────────────────────────────────────────────────────

    def _login(self):
        if self.auth_mode == "api_key":
            return

        # Try UniFi OS console endpoint first
        try:
            r = self._session.post(
                f"{self.base_url}/api/auth/login",
                json={"username": self.username, "password": self.password},
                timeout=10,
            )
            if r.status_code == 200:
                self._is_unifi_os = True
                self._logged_in = True
                token = r.json().get("data", {}).get("token") or r.json().get("token")
                if token:
                    self._session.headers["Authorization"] = f"Bearer {token}"
                csrf = r.headers.get("X-CSRF-Token")
                if csrf:
                    self._session.headers["X-CSRF-Token"] = csrf
                return
            if r.status_code == 401:
                body = r.json() if r.content else {}
                if body.get("twoFactorRequired") or body.get("errors", {}).get("totp"):
                    raise UnifiError(
                        "Controller has 2FA enabled. Generate an API key in UniFi OS → "
                        "Settings → Integrations and use API Key auth mode instead."
                    )
        except UnifiError:
            raise
        except requests.RequestException:
            pass

        # Fall back to legacy UniFi Network Server endpoint
        r = self._session.post(
            f"{self.base_url}/api/login",
            json={"username": self.username, "password": self.password},
            timeout=10,
        )
        if r.status_code != 200:
            raise UnifiError(f"Login failed: HTTP {r.status_code} - {r.text[:200]}")
        self._logged_in = True

    def _ensure_login(self):
        if not self._logged_in:
            self._login()

    def _self_hosted_api_url(self, site: str, path: str) -> str:
        if self._is_unifi_os:
            return f"{self.base_url}/proxy/network/api/s/{site}/{path.lstrip('/')}"
        return f"{self.base_url}/api/s/{site}/{path.lstrip('/')}"

    def _get(self, site: str, path: str) -> dict:
        self._ensure_login()
        r = self._session.get(self._self_hosted_api_url(site, path), timeout=15)
        _raise_for_status(r)
        return r.json()

    def _post(self, site: str, path: str, payload: dict) -> dict:
        self._ensure_login()
        r = self._session.post(self._self_hosted_api_url(site, path), json=payload, timeout=15)
        _raise_for_status(r)
        return r.json()

    # ── Cloud: Site Manager + connector to the Integration API ─────────────

    def _cloud_site(self, site_id: str) -> tuple[str, str]:
        """Resolve a Site Manager siteId (what Atrium stores) to the connector
        base URL for its console and the console's own Integration API site id.
        Site Manager's meta.name is the site's internal name ("default"), which
        the Integration API exposes as internalReference."""
        if site_id in self._cloud_sites:
            return self._cloud_sites[site_id]

        r = self._session.get(f"{self.base_url}/ea/sites", timeout=15)
        _raise_for_status(r)
        sm_site = next((s for s in r.json().get("data", []) if s.get("siteId") == site_id), None)
        if sm_site is None:
            raise UnifiError(f"Site {site_id} is not visible to this Site Manager API key")
        host_id = sm_site["hostId"]
        internal_ref = (sm_site.get("meta") or {}).get("name") or "default"

        base = f"{self.base_url}/v1/connector/consoles/{host_id}/proxy/network/integration/v1"
        r = self._session.get(
            f"{base}/sites", params={"filter": f"internalReference.eq('{internal_ref}')"}, timeout=20,
        )
        _raise_for_status(r)
        matches = r.json().get("data", [])
        if not matches:
            raise UnifiError(f"Console has no Network site with internal name '{internal_ref}'")

        self._cloud_sites[site_id] = (base, matches[0]["id"])
        return self._cloud_sites[site_id]

    def _integration_list(self, url: str, params: Optional[dict] = None) -> list[dict]:
        """GET every page of an Integration API list endpoint."""
        items: list[dict] = []
        offset = 0
        while True:
            r = self._session.get(
                url, params={**(params or {}), "offset": offset, "limit": _INTEGRATION_PAGE_SIZE}, timeout=20,
            )
            _raise_for_status(r)
            body = r.json()
            page = body.get("data", [])
            items.extend(page)
            offset += len(page)
            if not page or offset >= body.get("totalCount", 0):
                return items

    def _cloud_client_id(self, site_id: str, mac: str) -> str:
        base, isite = self._cloud_site(site_id)
        r = self._session.get(
            f"{base}/sites/{isite}/clients",
            params={"filter": f"macAddress.eq('{mac.lower()}')"},
            timeout=20,
        )
        _raise_for_status(r)
        matches = r.json().get("data", [])
        if not matches:
            raise UnifiError(
                f"Device {mac.lower()} is not connected to the site. Site Manager controllers "
                "can only change guest access for devices that are currently connected."
            )
        return matches[0]["id"]

    def _cloud_client_action(self, site_id: str, mac: str, payload: dict) -> dict:
        base, isite = self._cloud_site(site_id)
        client_id = self._cloud_client_id(site_id, mac)
        r = self._session.post(
            f"{base}/sites/{isite}/clients/{client_id}/actions", json=payload, timeout=20,
        )
        _raise_for_status(r)
        return r.json() if r.content else {}

    # ── Public API (normalised across both types) ───────────────────────────

    @property
    def reports_client_ssid(self) -> bool:
        """Whether get_active_clients() includes each client's SSID (essid).
        The Integration API used for cloud controllers doesn't expose it."""
        return not self._is_cloud

    def get_sites(self) -> list[dict]:
        """Return sites as [{"name": <site_id>, "desc": <display_name>}, ...]."""
        if self._is_cloud:
            r = self._session.get(f"{self.base_url}/ea/sites", timeout=15)
            _raise_for_status(r)
            items = r.json().get("data", [])
            return [
                {"name": item["siteId"], "desc": item.get("meta", {}).get("desc", item["siteId"])}
                for item in items
            ]
        else:
            self._ensure_login()
            if self._is_unifi_os:
                url = f"{self.base_url}/proxy/network/api/self/sites"
            else:
                url = f"{self.base_url}/api/self/sites"
            r = self._session.get(url, timeout=15)
            _raise_for_status(r)
            return r.json().get("data", [])

    def authorize_guest(
        self,
        site_id: str,
        mac: str,
        minutes: int = 60,
        up_kbps: Optional[int] = None,
        down_kbps: Optional[int] = None,
    ) -> dict:
        if self._is_cloud:
            payload: dict = {"action": "AUTHORIZE_GUEST_ACCESS"}
            if minutes:
                payload["timeLimitMinutes"] = minutes
            # rx/tx are from the client's side: rx = download, tx = upload.
            if down_kbps:
                payload["rxRateLimitKbps"] = _clamp_rate(down_kbps)
            if up_kbps:
                payload["txRateLimitKbps"] = _clamp_rate(up_kbps)
            return self._cloud_client_action(site_id, mac, payload)

        payload = {"cmd": "authorize-guest", "mac": mac.lower(), "minutes": minutes}
        if up_kbps:
            payload["up"] = up_kbps
        if down_kbps:
            payload["down"] = down_kbps
        return self._post(site_id, "cmd/stamgr", payload)

    def unauthorize_guest(self, site_id: str, mac: str) -> dict:
        if self._is_cloud:
            return self._cloud_client_action(site_id, mac, {"action": "UNAUTHORIZE_GUEST_ACCESS"})
        return self._post(site_id, "cmd/stamgr", {"cmd": "unauthorize-guest", "mac": mac.lower()})

    def get_devices(self, site_id: str) -> list[dict]:
        """Return network devices (APs, switches, etc.) for a site, each with
        at least "mac", "name" and "model"."""
        if self._is_cloud:
            base, isite = self._cloud_site(site_id)
            return [
                {
                    "mac": (d.get("macAddress") or "").lower(),
                    "name": d.get("name"),
                    "model": d.get("model"),
                    "id": d.get("id"),
                }
                for d in self._integration_list(f"{base}/sites/{isite}/devices")
            ]
        return self._get(site_id, "stat/device").get("data", [])

    def get_active_clients(self, site_id: str) -> list[dict]:
        """Connected clients, in the internal API's field names (mac, hostname,
        ip, essid, ap_mac, uptime, authorized, is_guest, is_wired). Cloud
        controllers leave essid and signal unset - see reports_client_ssid."""
        if not self._is_cloud:
            return self._get(site_id, "stat/sta").get("data", [])

        base, isite = self._cloud_site(site_id)
        ap_macs = {d["id"]: d["mac"] for d in self.get_devices(site_id) if d.get("id")}
        now = datetime.now(timezone.utc)
        clients = []
        for c in self._integration_list(f"{base}/sites/{isite}/clients"):
            access = c.get("access") or {}
            clients.append({
                "mac": (c.get("macAddress") or "").lower(),
                "hostname": c.get("name"),
                "ip": c.get("ipAddress"),
                "essid": None,
                "ap_mac": ap_macs.get(c.get("uplinkDeviceId")),
                "uptime": _seconds_since(c.get("connectedAt"), now),
                "signal": None,
                "authorized": bool(access.get("authorized")),
                "is_guest": access.get("type") == "GUEST",
                "is_wired": c.get("type") == "WIRED",
            })
        return clients

    def get_wlans(self, site_id: str) -> list[dict]:
        """WLANs as [{"name", "is_guest", "enabled"}, ...] (plus the internal
        API's other fields on self-hosted). On cloud, a WLAN counts as guest
        when it has a hotspot configuration (Hotspot Portal enabled)."""
        if self._is_cloud:
            base, isite = self._cloud_site(site_id)
            return [
                {
                    "name": b.get("name"),
                    "is_guest": "hotspotConfiguration" in b,
                    "enabled": bool(b.get("enabled")),
                }
                for b in self._integration_list(f"{base}/sites/{isite}/wifi/broadcasts")
            ]
        return self._get(site_id, "rest/wlanconf").get("data", [])

    def get_ssid_names(self, site_id: str) -> list[str]:
        return sorted({w["name"] for w in self.get_wlans(site_id) if w.get("name")})

    def get_guest_ssid_names(self, site_id: str) -> list[str]:
        """SSIDs flagged as guest networks (UniFi's "Guest Policy" on
        self-hosted, a Hotspot Portal on cloud). Callers should treat an empty
        result as "unknown", not "no guest SSIDs"."""
        return sorted({w["name"] for w in self.get_wlans(site_id) if w.get("name") and w.get("is_guest")})


def _clamp_rate(kbps: int) -> int:
    return max(_MIN_RATE_KBPS, min(_MAX_RATE_KBPS, int(kbps)))


def _seconds_since(iso_ts: Optional[str], now: datetime) -> Optional[int]:
    if not iso_ts:
        return None
    try:
        return max(0, int((now - datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))).total_seconds()))
    except ValueError:
        return None


def _raise_for_status(r: requests.Response):
    if r.status_code >= 400:
        raise UnifiError(f"Unifi API error: HTTP {r.status_code} - {r.text[:300]}")
