"""Unit tests for the ObjMode2S law specs (``cod3s.pycatshoo.mode_law``).

Pure pydantic — no PycSystem involved. Also pins the anti-drift
contract with the ``DegLaw*`` family (same ``cls`` tags, DegLaw fields
are a subset of the ModeLaw fields) until the deferred convergence.
"""

import pytest

from cod3s.pycatshoo.deg_mode import DegLawDelay, DegLawExp
from cod3s.pycatshoo.mode_law import (
    ModeLawDelay,
    ModeLawExp,
    ModeLawInst,
    parse_mode_law,
)


class TestValidation:
    def test_exp_negative_rate_rejected(self):
        with pytest.raises(ValueError, match=">= 0"):
            ModeLawExp(rate=-0.1)

    def test_exp_negative_rate_in_vector_rejected(self):
        with pytest.raises(ValueError, match=">= 0"):
            ModeLawExp(rate=[0.1, -0.2])

    def test_delay_negative_time_rejected(self):
        with pytest.raises(ValueError, match=">= 0"):
            ModeLawDelay(time=-1)

    def test_inst_prob_out_of_unit_interval_rejected(self):
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            ModeLawInst(prob=1.5)
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            ModeLawInst(prob=[0.3, -0.1])

    def test_zero_values_accepted(self):
        assert ModeLawExp(rate=0).values() == [0]
        assert ModeLawDelay(time=0).values() == [0]
        assert ModeLawInst(prob=0).values() == [0]

    @pytest.mark.parametrize("law_cls", [ModeLawExp, ModeLawDelay, ModeLawInst])
    def test_extra_fields_forbidden(self, law_cls):
        field = law_cls.param_field
        with pytest.raises(ValueError, match="(?i)extra|unexpected"):
            law_cls(**{field: 0.5, "bogus": 1})


class TestNormalization:
    def test_scalar_normalises_to_one_list(self):
        assert ModeLawExp(rate=0.1).values() == [0.1]

    def test_vector_kept(self):
        assert ModeLawExp(rate=[0.1, 0, 0.3]).values() == [0.1, 0, 0.3]

    def test_values_returns_a_copy(self):
        law = ModeLawExp(rate=[0.1, 0.2])
        law.values().append(99)
        assert law.values() == [0.1, 0.2]


class TestActivity:
    def test_exp_active_iff_positive_rate(self):
        law = ModeLawExp(rate=[0.1, 0])
        assert law.is_active_value(0.1) is True
        assert law.is_active_value(0) is False

    def test_delay_always_active(self):
        # time 0 is a valid deterministic delay, not a disabled law
        # (matches ObjFMDelay, which has no is_occ_law_*_active override).
        assert ModeLawDelay(time=0).is_active_value(0) is True

    def test_inst_always_active(self):
        # prob 0 is a valid never-drawing mode (native rule; the
        # ObjFMInst façade keeps its historical gamma > 0 drop rule
        # through its own activity hooks).
        assert ModeLawInst(prob=0).is_active_value(0) is True


class TestBackendLaw:
    def test_exp_to_bkd(self):
        assert ModeLawExp(rate=0.1).to_bkd_law(0.1) == {"cls": "exp", "rate": 0.1}

    def test_delay_to_bkd(self):
        assert ModeLawDelay(time=5).to_bkd_law(5) == {"cls": "delay", "time": 5}

    def test_inst_to_bkd_raises(self):
        with pytest.raises(NotImplementedError, match="inst draw"):
            ModeLawInst(prob=0.3).to_bkd_law(0.3)


class TestParseModeLaw:
    def test_dict_round_trip(self):
        law = parse_mode_law({"cls": "exp", "rate": 0.2})
        assert isinstance(law, ModeLawExp)
        assert law.model_dump() == {"cls": "exp", "rate": 0.2}

    def test_default_cls_requires_tag(self):
        with pytest.raises(ValueError, match="Invalid occ_law"):
            parse_mode_law({"rate": 0.2}, what="occ_law")

    def test_unknown_cls_rejected(self):
        with pytest.raises(ValueError, match="Invalid law"):
            parse_mode_law({"cls": "weibull", "shape": 2})

    def test_spec_instance_passthrough(self):
        law = ModeLawDelay(time=3)
        assert parse_mode_law(law) is law

    def test_non_dict_non_spec_rejected(self):
        with pytest.raises(ValueError, match="expected a ModeLaw"):
            parse_mode_law(42)


class TestDegLawAntiDrift:
    """DegLaw* must stay a schema subset of ModeLaw* (same cls tags,
    same parameter field names) until the deferred convergence."""

    def test_exp_fields_subset(self):
        assert set(DegLawExp.model_fields) <= set(ModeLawExp.model_fields)
        assert (
            DegLawExp.model_fields["cls"].default
            == ModeLawExp.model_fields["cls"].default
        )

    def test_delay_fields_subset(self):
        assert set(DegLawDelay.model_fields) <= set(ModeLawDelay.model_fields)
        assert (
            DegLawDelay.model_fields["cls"].default
            == ModeLawDelay.model_fields["cls"].default
        )

    def test_same_rejection_behaviour_on_negatives(self):
        with pytest.raises(ValueError):
            DegLawExp(rate=-1)
        with pytest.raises(ValueError):
            ModeLawExp(rate=-1)
