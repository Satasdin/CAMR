"""The Long Haul: one scripted project, "Mama Njeri's Kitchen" in Nairobi, over 110 working days and 2 million
tokens, with probes planted early and asked late. Each probe has one answer a rule can check.

  build(seed)              the script, the probes and the manifest (``write`` puts them on disk)
  at_cut(probe, tokens)    the probe as asked after the first N tokens, or None if it cannot be asked yet
  sample(probes, cut, n)   a stratified sample of the probes askable at a cut
  grade(probe, answer)     right / wrong / stale / declined / false_memory, with a reason

Families: fact (400), changed (80 facts, each asked now and on a past date), two_hop (40), maths (40 problems, each
asked three ways), page (3), code (20), lookalike (30) and never (60). Cuts: 64K, 256K, 1M and 2M tokens.
"""

from camr_engine.bench.haul.grade import VERDICTS, Grade, grade
from camr_engine.bench.haul.sample import askable, at_cut, sample
from camr_engine.bench.haul.script import CUTS, Haul, build, load_events, load_probes, write

__all__ = ["CUTS", "VERDICTS", "Grade", "Haul", "askable", "at_cut", "build", "grade", "load_events", "load_probes",
           "sample", "write"]
