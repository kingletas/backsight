"""Every word a person reads, in one place.

A string typed straight into a window is a string the terminal and any later
front end will eventually contradict.
"""

from __future__ import annotations

# Plan actions: the word, the mark and the tone, in one table.
#
# NFR-15 says destroy and replace may never be told apart by colour alone, so
# every row carries a mark and a word as well. The mark is what Terraform's own
# output uses, so it is already familiar to the person reading it.
ACTIONS = {
    "create": ("Add", "+", "add"),
    "update": ("Change in place", "~", "change"),
    "replace": ("Replace", "±", "replace"),
    "delete": ("Destroy", "-", "destroy"),
    "no-op": ("No change", " ", "none"),
    "read": ("Read", "<", "none"),
}

ACTION_LABELS = {name: label for name, (label, _, _) in ACTIONS.items()}

# FR-SIM-06: a sandbox run is a correctness gate, never a prediction. These are
# the words that may never appear near a convergence result.
FORBIDDEN_IN_VERDICTS = ("will happen", "predicts", "guarantees", "proves safe")
