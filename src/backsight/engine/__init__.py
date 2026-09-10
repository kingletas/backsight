"""Everything Backsight knows, with no toolkit attached.

Nothing under here may import `gi`. That is what lets the engine be tested
headlessly, and what makes the companion service in BRD §12 possible without a
rewrite. `tests/architecture/test_layering.py` is what makes it true.
"""
