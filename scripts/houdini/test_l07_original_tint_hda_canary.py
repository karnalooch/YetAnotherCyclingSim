"""Bounded source tests for original SideFX Tint HDA PE_heightfield_tint::1.0."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest
from types import SimpleNamespace

SOURCE=Path(__file__).with_name("l07_original_tint_hda_canary.py")
spec=importlib.util.spec_from_file_location("original_tint_probe",SOURCE)
tint=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tint)


class FakeParm:
    def __init__(self):
        self.value=None
    def set(self,value):
        self.value=value


class FakeHDA:
    def __init__(self):
        self.parameters={}
        self.slots={key:FakeParm() for key in ("tint","tint_ramp")}
    def setParms(self,data):
        self.parameters.update(data)
    def parm(self,key):
        return self.slots[key]
    def parmTuple(self,key):
        return self.slots[key]


class TintCanaryContract(unittest.TestCase):
    def test_only_four_verified_or_inferred_tints_are_authorized(self):
        self.assertEqual([c[0] for c in tint.CASES],
            ["grass_gradient","grass_brightness","cliff","scree"])
        self.assertEqual([c[3] for c in tint.CASES],
            ["gradient","brightness","solid_cliff","solid_scree"])
        self.assertEqual(tint.CASES[0][2],"ramp_layer")
        self.assertEqual(tint.CASES[2][2],"cliff_mask")
        self.assertEqual(tint.CASES[3][2],"scree_mask")

    def test_hda_sha_is_exact_original_sidefx(self):
        self.assertEqual(tint.TINT_HDA_SHA256,
                         "93cc47dd511bc3d5868835b5dd3b9082c13cab23355b688aaf2a947e8687a2ed")
        self.assertEqual(tint.MATERIAL_RUN,"39805083280-1")

    def test_inferred_grass_ramp_preserves_mask_parameter_names(self):
        fake=FakeHDA()
        hou=SimpleNamespace(rampBasis=SimpleNamespace(Linear="linear"),
            Ramp=lambda basis,positions,colors:(basis,positions,colors))
        settings=tint.apply_parms(fake,"gradient",hou)
        self.assertEqual(settings["srcname1"],"mask")
        self.assertEqual(settings["ramp_mask"],"")
        self.assertEqual(settings["strength"],0.95)
        self.assertEqual(settings["use_ramp"],1)
        ramp=fake.slots["tint_ramp"].value
        self.assertEqual(ramp[1],[0.0,0.996694])
        self.assertEqual(ramp[2][0],(0.34,0.55,0.12705))
        self.assertEqual(ramp[2][-1],(1.0,0.822741,0.538))

    def test_masked_solid_tints_are_not_global_darkening(self):
        for kind,color in (("solid_cliff",(0.597,0.597,0.597)),
                           ("solid_scree",(0.874,0.822347,0.701822))):
            with self.subTest(kind=kind):
                fake=FakeHDA()
                settings=tint.apply_parms(fake,kind,None)
                self.assertEqual(settings["ramp_mask"],"mask")
                self.assertEqual(settings["use_ramp"],0)
                self.assertEqual(fake.slots["tint"].value,color)

    def test_brightness_is_unmasked_and_before_sand(self):
        fake=FakeHDA()
        settings=tint.apply_parms(fake,"brightness",None)
        self.assertEqual(settings["ramp_mask"],"")
        self.assertEqual(fake.slots["tint"].value,(2.0,2.0,2.0))
        self.assertEqual(tint.CASES[1][1],"grass_gradient")

    def test_unknown_tint_mode_rejected(self):
        with self.assertRaisesRegex(ValueError,"Unapproved tint mode"):
            tint.apply_parms(FakeHDA(),"unknown",None)

    def test_source_scopes_never_canonical_map(self):
        self.assertEqual(tint.SCRATCH_ROOT.parts[:3],("D:\\","yacs","work") if False else ("D:\\","yacs","work"))
        self.assertTrue(str(tint.SCRATCH_ROOT).replace("\\","/").startswith("D:/yacs/work/"))
        self.assertTrue(str(tint.MATERIAL_ROOT).replace("\\","/").startswith("D:/yacs/work/"))
        self.assertFalse("Saved/" in str(tint.SCRATCH_ROOT))


if __name__=="__main__":
    unittest.main()
