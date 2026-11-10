# Passengers with a lot of luggage pay more

Charge KES 20 for each bag after the first. It should appear as a quote line named `luggage`. A passenger with no bags or one bag has no such line.

The extras live in `matatu/fares/extras.py`, and `quote_fare` in `matatu/fares/quote.py` already receives the number of bags.
