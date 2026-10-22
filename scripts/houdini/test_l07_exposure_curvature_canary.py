"""Original Pegasus Exposure/Curvature MaskByFeature and Tint HDA source contract.

Tests use no native runtime and do not claim full source video or geo results.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from types import SimpleNamespace

SOURCE=Path(__file__).with_name("l07_exposure_curvature_canary.py")
spec=importlib.util.spec_from_file_location("l07_exposure",SOURCE)
x=importlib.util.module_from_spec(spec)
spec.loader.exec_module(x)


class FakeEnum:
    def __init__(self):
        self.chosen=None
    def parmTemplate(self):
        return SimpleNamespace(menuItems=lambda:("0","1","2"),
                               menuLabels=lambda:("No Change","Default Tinting","Visualize Height"))
    def set(self,val):
        self.chosen=val


class FakeParm:
    def __init__(self):
        self.set_value=None
    def set(self,val):
        self.set_value=val


class FakeNode:
    def __init__(self,parms):
        self.parameters={}
        self.parms={key:FakeParm() for key in parms}
    def parm(self,name):
        return self.parms.get(name)
    def setParms(self,values):
        self.parameters.update(values)


class ExposureCurvatureContract(unittest.TestCase):
    def test_source_exposure_distance_and_16_searches(self):
        self.assertEqual(x.EXPOSURE_MASK_PARMS["viewdistance"],145)
        self.assertEqual(x.EXPOSURE_MASK_PARMS["numsearches"],16)
        self.assertEqual(x.EXPOSURE_MASK_PARMS["maskbyocclusion"],1)
        self.assertEqual(x.EXPOSURE_MASK_PARMS["maskbycurvature"],0)
        self.assertEqual(x.EXPOSURE_MASK_PARMS["combine"],0)
        self.assertEqual(x.EXPOSURE_MASK_PARMS["invertmask"],0)

    def test_curvature_feature_is_sourced_from_mask12(self):
        self.assertEqual(x.CURVATURE_MASK_PARMS["maskbycurvature"],1)
        self.assertEqual(x.CURVATURE_MASK_PARMS["max_curvature"],0.18)
        self.assertEqual(x.CURVATURE_MASK_PARMS["maskbyocclusion"],0)
        source=SOURCE.read_text(encoding="utf-8")
        self.assertIn("curvature_mask.setInput(0,exposure_mask)",source)
        self.assertIn("tint5.setInput(1,exposure_mask)",source)
        self.assertIn("tint6.setInput(1,curvature_mask)",source)

    def test_real_tint_strength_and_mask_fields_are_distinct(self):
        self.assertEqual(x.EXPOSURE_TINT_PARMS["strength"],1)
        self.assertEqual(x.CURVATURE_TINT_PARMS["strength"],0.613)
        for item in (x.EXPOSURE_TINT_PARMS,x.CURVATURE_TINT_PARMS):
            self.assertEqual(item["ramp_mask"],"")
            self.assertEqual(item["srcname1"],"mask")
            self.assertEqual(item["use_ramp"],1)

    def test_incomplete_author_point_positions_explicitly_adapted(self):
        self.assertEqual(x.EXPOSURE_CANDIDATE[1],(0.93538,(0.651,0.651,0.651)))
        self.assertEqual(x.CURVATURE_CANDIDATE[-1],(1.0,(2.0,2.0,2.0)))
        self.assertTrue("final source HIP" in x.__doc__)
        self.assertIn("YACS_ADAPTATION",SOURCE.read_text(encoding="utf-8"))

    def test_native_parameter_menu_is_selected_from_real_labels(self):
        p=FakeEnum()
        self.assertEqual(x.enum_by_label(p,"Default Tinting"),"1")
        self.assertEqual(p.chosen,"1")
        with self.assertRaisesRegex(ValueError,"not unique"):
            x.enum_by_label(p,"Not an actual label")

    def test_maskbyfeature_branch_refuses_unverified_names(self):
        hou=SimpleNamespace(rampBasis=SimpleNamespace(Linear="linear"),
                            Ramp=lambda basis,position,value:(basis,position,value))
        for kind,params,ramptoken in (
            ("exposure",x.EXPOSURE_MASK_PARMS,"ramp"),
            ("curvature",x.CURVATURE_MASK_PARMS,"curvatureramp"),
        ):
            with self.subTest(kind=kind):
                n=FakeNode({*params,ramptoken})
                result=x.apply_feature(n,kind,hou)
                self.assertEqual(n.parameters,params)
                self.assertEqual(n.parms[ramptoken].set_value[1],[0.0,1.0])
                self.assertEqual(result["source_quality"],
                                 "SOURCE_VERIFIED_PARAMETERS_RAMP_KNOTS_YACS_ADAPTATION")
        with self.assertRaises(ValueError):
            x.apply_feature(FakeNode({}),"unsupported",hou)

    def test_source_pin_and_host_bounds(self):
        self.assertEqual(x.HDA_SHA,
                         "93cc47dd511bc3d5868835b5dd3b9082c13cab23355b688aaf2a947e8687a2ed")
        self.assertEqual(x.MATERIAL_RUN,"39808914161-1")
        self.assertTrue(str(x.SCRATCH).startswith("D:/yacs/work/"))


if __name__=="__main__":
    unittest.main()
