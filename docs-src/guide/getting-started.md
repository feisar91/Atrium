---
title: Getting Started
description: Connect a UniFi controller, sync its sites, and build your first portal.
---

# Getting Started

This walks through connecting a UniFi controller, syncing its sites into
Atrium, and building your first portal. Once a portal exists, see
[Configure UniFi](/guide/configure-unifi) to point guest WiFi at it.

## 1. Add a controller

Under **Controllers → Add Controller**, choose:

- **Self-hosted** - a UniFi Network Application you run yourself, reached by
  URL.
- **UniFi Site Manager** (cloud) - Ubiquiti's hosted controller.

For self-hosted controllers, authenticate with either a username/password or
an API key generated in **UniFi OS → Integrations** (API keys bypass 2FA on
the controller account, which is usually the more convenient option for an
integration like this).

For **UniFi Site Manager**, create an API key at **unifi.ui.com → Settings →
API Keys** with an account that owns the console. Atrium reaches the console
through Site Manager's connector to UniFi Network's official Integration API,
so the console needs a recent UniFi Network version (9.1 or later).

::: warning Site Manager limitations
UniFi only lets Site Manager keys reach the Integration API, which is more
limited than a self-hosted connection:

- **Active Devices can't filter by SSID.** UniFi doesn't report which SSID a
  device is on, so a portal shows every guest device on its site. If you run
  more than one guest portal per site, use a self-hosted connection instead.
- **Guest access can only be changed for connected devices.** Reconnecting
  or deauthorizing a guest who has already left the network fails until
  they're back in range.
- **No signal strength** on the Active Devices page.
:::

A controller can be **platform-owned** (visible to superadmins only) or
**tenant-owned** - assigning a controller to a tenant grants every user in
that tenant visibility of every site on it. Set an automatic sync interval
(hourly out to every 7 days) or leave it on manual.

![Controllers page showing a connected UniFi controller, its auth mode, owner, and sync schedule](/assets/screenshots/controllers.png)

Saving the controller runs an initial sync, pulling in its sites and access
points.

## 2. Assign sites to tenants

Every UniFi site synced from a controller shows up under **Sites**. Assign
each one to the tenant it belongs to - a tenant isn't limited to a single
site, so an MSP managing several client locations just assigns each of that
client's sites to their tenant.

![Sites page showing multiple UniFi sites across different tenants, each assignable and each with their own portals](/assets/screenshots/sites.png)

## 3. Build a portal for the site

Create a portal under **Portals**, pointed at the site. By default a portal
applies to every SSID on that site - to run different portals on different
SSIDs (staff WiFi, guest WiFi, a lobby kiosk network), set the **SSID
filter** on each portal to the specific SSID(s) it should handle.

Once the portal exists, head to [Configure UniFi](/guide/configure-unifi) to
point guest WiFi at it.
