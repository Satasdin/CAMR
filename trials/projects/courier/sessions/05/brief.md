# Support needs to see where a parcel is right now

Support staff look up parcels all day with `parcel_timeline`. They say that what they want, the parcel's situation right now, sits at the bottom of a long list they have to scroll through.

Make the response easier for them. It must have a new key, `current`, holding the status of the parcel's most recent event, or `None` if it has no events yet.
