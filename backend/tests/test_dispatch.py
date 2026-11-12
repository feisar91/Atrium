"""Portal dispatch from UniFi's hotspot redirect (/guest/s/<site>/?...).

UniFi puts the console's internal site name in the path. Self-hosted
controllers store that as unifi_site_id; Site Manager (cloud) controllers
store the Site Manager siteId there, so dispatch also matches internal_name.
"""
import uuid
from unittest.mock import MagicMock

from app.extensions import db
from app.models import AccessPoint
from app.models.controller import ControllerType
from tests.factories import make_controller, make_portal, make_site


def _name() -> str:
    # Unique per test: rows can leak between tests (see test_settings.py).
    return f"site-{uuid.uuid4().hex[:8]}"


def _cloud_site(internal_name, **kwargs):
    controller = make_controller(controller_type=ControllerType.CLOUD)
    return make_site(controller, unifi_site_id=uuid.uuid4().hex[:24], internal_name=internal_name, **kwargs)


def _dispatched_slug(client, site_name, **params):
    resp = client.get(f"/guest/s/{site_name}/", query_string={"id": "aa:bb:cc:00:00:01", **params})
    assert resp.status_code == 302, resp.get_data(as_text=True)
    return resp.headers["Location"].split("?")[0].rstrip("/").rsplit("/", 1)[-1]


def test_cloud_site_wide_portal_resolved_by_internal_name(client, db_session):
    name = _name()
    site = _cloud_site(name)
    portal = make_portal(site, ssids=[])

    assert _dispatched_slug(client, name, ssid="Anything") == portal.slug


def test_cloud_ssid_portal_preferred_over_site_wide(client, db_session):
    name = _name()
    site = _cloud_site(name)
    make_portal(site, ssids=[])
    guest_portal = make_portal(site, ssids=["Captive Test"])

    assert _dispatched_slug(client, name, ssid="Captive Test") == guest_portal.slug


def test_same_internal_name_on_two_consoles_resolved_by_ap(client, db_session):
    name = _name()
    site_a = _cloud_site(name)
    site_b = _cloud_site(name)
    make_portal(site_a, ssids=[])
    portal_b = make_portal(site_b, ssids=[])
    ap_mac = f"11:22:33:{uuid.uuid4().hex[:2]}:{uuid.uuid4().hex[:2]}:{uuid.uuid4().hex[:2]}"
    db.session.add(AccessPoint(mac_address=ap_mac, site_id=site_b.id, name="AP"))
    db.session.commit()

    assert _dispatched_slug(client, name, ap=ap_mac.upper()) == portal_b.slug


def test_self_hosted_still_resolved_by_unifi_site_id(client, db_session):
    name = _name()
    site = make_site(make_controller(), unifi_site_id=name)  # internal_name unset
    portal = make_portal(site, ssids=[])

    assert _dispatched_slug(client, name) == portal.slug


def test_sync_records_internal_name(db_session):
    from app.api.controllers import _do_sync

    cloud = make_controller(controller_type=ControllerType.CLOUD)
    sm_id = uuid.uuid4().hex[:24]
    name = _name()
    mock = MagicMock()
    mock.get_sites.return_value = [{"name": sm_id, "desc": "Main", "internal_name": name}]
    mock.get_devices.return_value = []
    _do_sync(cloud, mock)

    self_hosted = make_controller()
    sh_name = _name()
    mock.get_sites.return_value = [{"name": sh_name, "desc": "Branch"}]
    _do_sync(self_hosted, mock)

    from app.models import UnifiSite
    cloud_site = UnifiSite.query.filter_by(controller_id=cloud.id).one()
    assert (cloud_site.unifi_site_id, cloud_site.internal_name) == (sm_id, name)
    sh_site = UnifiSite.query.filter_by(controller_id=self_hosted.id).one()
    assert sh_site.internal_name == sh_name
