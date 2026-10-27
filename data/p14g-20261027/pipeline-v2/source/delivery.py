"""Source publisher with persistent host-poll period; no per-step random delay.
Interval zones live in partition.py; a representative is not its whole tube.
"""
from p14r.delivery import Delivery,Word
# Reused source gap-exit, latest-slot and timer ancestry are unchanged. The
# extra6/10ms periods are legal only under explicitly assumed host service bound.
