"""Modules somebody already wrote, so nobody writes them again.

The catalog is a directory of Terraform modules — a cloned repository, a shared
folder, or a path inside this workspace. Each one is read for its variables and
outputs, which is enough to describe it, to generate a call to it, and to say
what it needs before anybody runs a plan.

Nothing is fetched. A registry needs network and credentials, and a directory on
disk is what a platform team can actually hand somebody today.
"""
