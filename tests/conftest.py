"""The suite runs on a display of its own.

Windows are constructed here in their hundreds and several actions present a
dialog, so without this the tests appear over whatever the person is doing and
take the pointer with them.

This has to happen **before anything imports `gi`**, because GTK connects to a
display when it is initialised. A conftest at the root of the suite is the
first thing pytest imports, which is why it lives here rather than in a
fixture.
"""

from __future__ import annotations

from backsight.app.offscreen import use_a_private_display

DISPLAY = use_a_private_display()
