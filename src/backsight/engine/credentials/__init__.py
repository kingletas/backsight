"""What this machine can authenticate as, without ever holding a secret.

The rule the whole layer is built around: **no long-lived cloud credential is
ever read, returned, logged or stored by this application** — FR-SEC-02. So
nothing here answers "what is the key"; it answers "is there one, what kind is
it, and what would it let you do". That is everything the interface needs in
order to stop guessing, and it is a boundary that cannot leak what it never
holds.
"""
