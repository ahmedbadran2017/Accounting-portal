# Copyright (c) 2026, Justyol
# One row per Cathedis parcel: the carrier's own word on delivery, collection
# and funding. Written only by api/cathedis_sync.py (nightly, open parcels
# only); read by the cycle radar (api/radar.py).
from frappe.model.document import Document


class CathedisParcel(Document):
    pass
