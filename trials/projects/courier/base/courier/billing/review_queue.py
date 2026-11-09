"""Invoices that need a person to look at them."""

from typing import List

from ..models import ReviewItem


def add_to_review(store, invoice_id: str, reason: str, clock) -> ReviewItem:
    item = ReviewItem(invoice_id=invoice_id, reason=reason, created_at=clock.now())
    store.review_items.append(item)
    return item


def pending_reviews(store) -> List[ReviewItem]:
    return [item for item in store.review_items if not item.resolved]


def resolve_review(item: ReviewItem, resolution: str) -> ReviewItem:
    item.resolved = True
    item.resolution = resolution
    return item
