# Fewer invoices stuck in review after a timeout

Support says that most invoices sitting in the review queue with the reason `gateway timeout` were in fact paid: the customer's money was taken and only the answer got lost. Staff spend every morning matching these up by hand.

Change `charge_invoice` in `courier/billing/checkout.py` so that when the payment did go through, the invoice ends up paid with its receipt, the same way as after a normal successful charge, and nobody has to review it. If there is no sign of the payment, the invoice goes to review as it does now.
