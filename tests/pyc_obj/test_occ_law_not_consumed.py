"""An occurrence law declared as data survives being used.

Pure pydantic -- no PycSystem involved.

``TransitionModel.sanitize_occ_law`` expands the short wire form
(``{"cls": "delay", ...}``) into the model's own class name. It used to write
that expansion into the CALLER's mapping, and ``ObjCOD3S.from_dict`` then
popped ``cls`` off the same mapping, so a declaration kept as data was emptied
by its first use: ``{"cls": "delay", "time": 14}`` came back ``{"time": 14}``
and the second transition raised ``Missing attribute 'cls'``, naming a key
still plainly visible in the source the caller wrote.

That is the regime of anything holding its declarations rather than writing
them inline -- a knowledge base raised twice, a study sweeping a parameter, an
importer replaying a platform export.
"""

import pytest

from cod3s.pycatshoo.automaton import PycTransition, TransitionModel


class TestSanitizeOccLaw:
    def test_the_mapping_is_unchanged(self):
        law = {"cls": "delay", "time": 5.0}

        TransitionModel.sanitize_occ_law(law)

        assert law == {"cls": "delay", "time": 5.0}

    def test_it_still_expands_the_short_form(self):
        built = TransitionModel.sanitize_occ_law({"cls": "delay", "time": 5.0})

        assert type(built).__name__ == "DelayOccDistribution"
        assert built.time == 5.0

    def test_a_law_without_cls_is_still_refused(self):
        with pytest.raises(AttributeError, match="cls"):
            TransitionModel.sanitize_occ_law({"time": 5.0})

    def test_an_already_built_law_passes_through(self):
        built = TransitionModel.sanitize_occ_law({"cls": "exp", "rate": 0.1})

        assert TransitionModel.sanitize_occ_law(built) is built

    def test_none_passes_through(self):
        assert TransitionModel.sanitize_occ_law(None) is None


class TestTransitionsBuiltFromOneDeclaration:
    def test_two_transitions_share_one_law_mapping(self):
        law = {"cls": "exp", "rate": 0.1}

        first = PycTransition(name="t1", source="a", target="b", occ_law=law)
        second = PycTransition(name="t2", source="b", target="a", occ_law=law)

        assert law == {"cls": "exp", "rate": 0.1}
        assert first.occ_law.rate == second.occ_law.rate == 0.1

    def test_a_law_shared_between_two_transitions_is_not_shared_after(self):
        """Each transition gets its own built law, so one is retunable alone."""
        law = {"cls": "delay", "time": 2.0}

        first = PycTransition(name="t1", source="a", target="b", occ_law=law)
        second = PycTransition(name="t2", source="b", target="a", occ_law=law)

        assert first.occ_law is not second.occ_law
