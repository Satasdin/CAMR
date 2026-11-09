# Handle gateway timeouts in checkout

`charge_invoice` in `courier/billing/checkout.py` lets `GatewayTimeout` escape, so the customer gets a server error and the invoice stays open.

When the gateway times out, `charge_invoice` should:

- set the invoice's status to `pending_review` (`INVOICE_PENDING_REVIEW` in `courier/models.py`),
- add it to the review queue with `add_to_review` and the reason `gateway timeout`,
- save the invoice and return it.

## Discussion

From the payments meeting on 12 March. Until February this function retried the charge up to three times after a timeout. The gateway had often already taken the money when it timed out, and customer 4411 was charged three times for one invoice. Passing the invoice reference does not protect us, because the gateway does not enforce uniqueness of references on charges.

Rejected: any automatic retry of a charge. Decision: one call to the gateway's `charge` per checkout attempt, and a timed-out charge goes to a person.
