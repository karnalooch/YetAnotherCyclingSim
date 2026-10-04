from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from world_data_service_evidence import metric_wfs
from world_data_service_evidence import feature_collection, mvt_layers


class ServiceEvidenceTests(unittest.TestCase):
    def test_p1_selection_never_invokes_heavy_producers(self):
        import contextlib
        import importlib.util
        import io
        import json
        import sys
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('acquisition_test', Path(__file__).with_name('acquire_sa_calobra_world_data.py'))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'requests': SimpleNamespace(), 'acquisition_test': module}):
            spec.loader.exec_module(module)
            with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
                root = Path(folder)
                selected = ['btn_vector_context', 'siose_2014_wfs', 'catastro_buildings_wfs']
                manifest = Path(__file__).resolve().parents[2] / 'worldgen/terrain/benchmarks/sa_calobra/world_data/working_space_sources.json'
                args = SimpleNamespace(manifest=manifest, persistent_root=root/'raw',
                                       receipt_out=root/'receipt', force=False, sources=selected)
                with patch.object(module, 'parse_args', return_value=args), patch.object(module, 'session', return_value=object()), \
                     patch.object(module, 'acquire_btn', return_value={'status':'downloaded'}), \
                     patch.object(module, 'acquire_siose', return_value={'status':'downloaded'}), \
                     patch.object(module, 'acquire_catastro', return_value={'status':'downloaded'}), \
                     patch.object(module, 'acquire_ortho', side_effect=AssertionError('P0 producer invoked')), \
                     patch.object(module, 'acquire_cnig_product', side_effect=AssertionError('CNIG producer invoked')):
                    module.main()
                receipt = json.loads((root/'receipt/world-data-acquisition-receipt.json').read_text())
                self.assertEqual(set(receipt['sources']), set(selected))

    def test_wrong_edition_fails_without_querying_provider(self):
        import hashlib
        import json
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            out = root / 'siose_2014_wfs'
            out.mkdir()
            (out / 'GetCapabilities.xml').write_text('<WFS_Capabilities xmlns="http://www.opengis.net/wfs/2.0" xmlns:o="http://www.opengis.net/ows/1.1"><o:Abstract>SIOSE HR 2017</o:Abstract><FeatureTypeList><FeatureType><Name>lcv:LandCoverUnit</Name><OtherCRS>urn:ogc:def:crs:EPSG::25831</OtherCRS></FeatureType></FeatureTypeList></WFS_Capabilities>')
            helper = SimpleNamespace(sha256=lambda p: hashlib.sha256(p.read_bytes()).hexdigest(), json=json,
                                     write_text=lambda p, text: p.write_text(text))
            result = metric_wfs(helper, object(), {'id':'siose_2014_wfs','product':'SIOSE 2014',
                               'service_url':'https://example.invalid','expected_edition':'2014'},
                               [0,0,1,1], root, False, ['LandCoverUnit'], [[0,0,1,1]])
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['admitted_file_count'], 0)
            self.assertIn('edition mismatch', result['errors'][0])

    def test_http_200_exception_is_not_data(self):
        with self.assertRaisesRegex(ValueError, 'Area of extension'):
            feature_collection(b'<ExceptionReport><ExceptionText>Area of extension out of limits</ExceptionText></ExceptionReport>')

    def test_partial_collection_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'Partial WFS'):
            feature_collection(b'<FeatureCollection xmlns="http://www.opengis.net/wfs/2.0" numberMatched="2" numberReturned="1"><member/></FeatureCollection>')

    def test_unknown_count_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'Unproven completeness'):
            feature_collection(b'<FeatureCollection xmlns="http://www.opengis.net/wfs/2.0" numberMatched="unknown" numberReturned="0"/>')

    def test_empty_complete_collection_is_explicit(self):
        result = feature_collection(b'<FeatureCollection xmlns="http://www.opengis.net/wfs/2.0" numberMatched="0" numberReturned="0"/>')
        self.assertEqual(result['feature_count'], 0)

    def test_next_page_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'next page'):
            feature_collection(b'<FeatureCollection xmlns="http://www.opengis.net/wfs/2.0" numberMatched="0" numberReturned="0" next="next"/>')

    def test_mvt_layer_inventory(self):
        # Tile.layers contains one named layer and two empty feature messages.
        self.assertEqual(mvt_layers(b'\x1a\x07\x0a\x01x\x12\x00\x12\x00'), {'x': 2})

    def test_html_is_not_mvt(self):
        with self.assertRaises(ValueError):
            mvt_layers(b'<html>provider error</html>')

    def test_truncated_mvt_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            mvt_layers(b'\x1a\xff')


if __name__ == '__main__':
    unittest.main()
