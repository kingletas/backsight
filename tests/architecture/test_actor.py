"""User is not actor, and the type exists so that nothing has to remember it.

BRD §12 has a service acting for a person in v2. The distinction is cheap now
and is a rewrite of every call site later.
"""

import pytest

from backsight.engine.actor import Actor, ActorKind


def test_a_person_is_answerable_for_their_own_action():
    actor = Actor(kind=ActorKind.PERSON, identifier="j.okafor")
    assert actor.responsible == "j.okafor"


def test_a_service_names_the_person_it_acted_for():
    actor = Actor(kind=ActorKind.SERVICE, identifier="hub", on_behalf_of="j.okafor")
    assert actor.responsible == "j.okafor"
    assert actor.identifier == "hub"


def test_a_person_cannot_act_on_behalf_of_somebody_else():
    with pytest.raises(ValueError):
        Actor(kind=ActorKind.PERSON, identifier="j.okafor", on_behalf_of="a.rivera")


def test_an_actor_needs_an_identifier():
    with pytest.raises(ValueError):
        Actor(kind=ActorKind.PERSON, identifier="")
