from app.extensions import db
from datetime import datetime, timezone


class UnifiSite(db.Model):
    __tablename__ = "unifi_sites"

    id = db.Column(db.Integer, primary_key=True)

    # The site's ID on its controller: the internal site name (e.g. "default")
    # for self-hosted controllers, the Site Manager siteId for cloud ones.
    unifi_site_id = db.Column(db.String(100), nullable=False)
    # The internal site name UniFi uses in the hotspot redirect
    # (/guest/s/<internal_name>/). Equals unifi_site_id on self-hosted
    # controllers; set by sync. Dispatch matches on either.
    internal_name = db.Column(db.String(100), nullable=True, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))

    controller_id = db.Column(db.Integer, db.ForeignKey("unifi_controllers.id"), nullable=False)
    controller = db.relationship("UnifiController", back_populates="sites")

    # Which tenant this site belongs to (always set, even for platform-controller sites)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True)
    tenant = db.relationship("Tenant", back_populates="sites")

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    portals = db.relationship("Portal", back_populates="site", lazy="dynamic")
    access_points = db.relationship("AccessPoint", back_populates="site", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("controller_id", "unifi_site_id", name="uq_controller_site"),
    )

    def __repr__(self):
        return f"<UnifiSite {self.name} ({self.unifi_site_id})>"
