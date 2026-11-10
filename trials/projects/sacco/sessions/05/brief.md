# Savings statements confuse members

Branch staff say members keep coming in puzzled by savings statements on which money goes in and then straight back out. They want statements that are easier to read.

`member_statement` in `sacco/statements/member.py` must return a new key, `reversed_count`: how many postings were undone during the period, or `0` if there were none.
