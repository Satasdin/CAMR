# Parcel timeline

Add `courier/tracking/timeline.py` with `build_timeline(store, parcel_id)`. It returns a list of dictionaries with the keys `status`, `at` and `note`, one per tracking event for the parcel. Depots upload scans late, so events can be stored out of order. An unknown parcel raises `NotFound`, as `get_parcel` does.

Add a handler `parcel_timeline(request, context)` to `courier/api/handlers.py`. It takes `{"parcel_id": ...}` and returns `{"parcel_id": ..., "events": [...]}`, using the `handled` decorator like the other handlers.

## Discussion

Talked this through with the mobile team. Our first version returned the newest event first. The drivers' mobile app reverses the list itself before drawing it, so version 2.3 showed every delivery upside down and support took complaints for a week. The mobile team cannot change this, because old versions of the app stay on drivers' phones for about a year.

Decision: `build_timeline` always returns events oldest first. Rejected: newest first, and rejected a query option for the order, since older app versions would not send it.
