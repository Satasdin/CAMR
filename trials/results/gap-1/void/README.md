# Runs that are not scored

`cloud-sonnet-cut-at-600-tokens`: the first cloud run, stopped after 35 questions on 10 November 2026. The harness allowed the
cloud model 600 output tokens. The model spent part of that thinking, and 13 of the 35 answers were cut off, 8 of them with no
text at all. That would have understated the cloud model. The limit was raised to 4,000 tokens and the cloud run started again
from the first question into `cloud-sonnet`. Nothing in the engine, the tasks or the scoring changed.

`sweep-started-early`: a few answers of the budget sweep that began while the ablation runs were still using the machine, because
the script waiting for the queue matched the wrong line of its log. Their timings would have been wrong, so the sweep was started
again from the first question once the machine was free.
