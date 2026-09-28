#!/usr/bin/env python3
"""Unit tests for the Cortina 2 m official-source discovery contract."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("probe_passo_giau_cortina_2m.py")
SPEC = importlib.util.spec_from_file_location("cortina_2m_probe", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)

WMS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
  <Capability>
    <Layer>
      <Title>root</Title>
      <Layer>
        <Name>rv:dtm_2m_cortina</Name>
        <Title>DTM_2m_Cortina</Title>
        <CRS>EPSG:7795</CRS>
        <EX_GeographicBoundingBox>
          <westBoundLongitude>11.90</westBoundLongitude>
          <eastBoundLongitude>12.20</eastBoundLongitude>
          <southBoundLatitude>46.35</southBoundLatitude>
          <northBoundLatitude>46.60</northBoundLatitude>
        </EX_GeographicBoundingBox>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

WCS_CAPS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<wcs:Capabilities xmlns:wcs="http://www.opengis.net/wcs/2.0"
 xmlns:ows="http://www.opengis.net/ows/2.0">
  <wcs:Contents>
    <wcs:CoverageSummary>
      <wcs:CoverageId>rv__dtm_2m_cortina</wcs:CoverageId>
      <ows:Title>DTM_2m_Cortina</ows:Title>
    </wcs:CoverageSummary>
  </wcs:Contents>
</wcs:Capabilities>
"""

DESCRIBE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<wcs:CoverageDescriptions xmlns:wcs="http://www.opengis.net/wcs/2.0"
 xmlns:gml="http://www.opengis.net/gml/3.2">
  <wcs:CoverageDescription>
    <gml:boundedBy>
      <gml:Envelope srsName="http://www.opengis.net/def/crs/EPSG/0/7795">
        <gml:lowerCorner>730000 5147000</gml:lowerCorner>
        <gml:upperCorner>739000 5157000</gml:upperCorner>
      </gml:Envelope>
    </gml:boundedBy>
    <gml:domainSet>
      <gml:RectifiedGrid dimension="2">
        <gml:offsetVector srsName="http://www.opengis.net/def/crs/EPSG/0/7795">2 0</gml:offsetVector>
        <gml:offsetVector srsName="http://www.opengis.net/def/crs/EPSG/0/7795">0 -2</gml:offsetVector>
      </gml:RectifiedGrid>
    </gml:domainSet>
  </wcs:CoverageDescription>
</wcs:CoverageDescriptions>
"""


class Cortina2mProbeTests(unittest.TestCase):
    def test_wms_layer_is_discovered_by_exact_normalized_label(self) -> None:
        root = probe.parse_xml(WMS_XML, "test WMS")
        matches = probe.flatten_wms_layers(root)
        self.assertEqual(1, len(matches))
        self.assertEqual("rv:dtm_2m_cortina", matches[0]["name"])
        self.assertEqual("DTM_2m_Cortina", matches[0]["title"])
        self.assertIn("EPSG:7795", matches[0]["crs"])

    def test_passo_giau_is_inside_advertised_extent(self) -> None:
        root = probe.parse_xml(WMS_XML, "test WMS")
        bbox = probe.flatten_wms_layers(root)[0]["geographic_bbox_wgs84"]
        lon, lat = probe.PASSO_GIAU_WGS84
        self.assertTrue(probe.point_inside_bbox(lon, lat, bbox))

    def test_wcs_coverage_matches_wms_name_or_title(self) -> None:
        root = probe.parse_xml(WCS_CAPS_XML, "test WCS")
        matches = probe.wcs_coverage_candidates(
            root,
            wms_name="rv:dtm_2m_cortina",
        )
        self.assertEqual(
            [{"identifier": "rv__dtm_2m_cortina", "title": "DTM_2m_Cortina"}],
            matches,
        )

    def test_describe_coverage_proves_two_meter_grid(self) -> None:
        root = probe.parse_xml(DESCRIBE_XML, "test DescribeCoverage")
        description = probe.parse_describe_coverage(root)
        self.assertEqual([2.0, 2.0], probe.validate_resolution(description))
        self.assertEqual(
            "http://www.opengis.net/def/crs/EPSG/0/7795",
            description["envelope"]["srs_name"],
        )

    def test_resolution_contract_rejects_non_two_meter_grid(self) -> None:
        description = {"offset_magnitudes": [5.0, 5.0]}
        with self.assertRaisesRegex(RuntimeError, "not proven as a 2 m grid"):
            probe.validate_resolution(description)

    def test_endpoint_candidate_extraction_keeps_download_contracts(self) -> None:
        body = """
        this.url = "../download/layerSearch/findLayer";
        location.href = "../download/layerDownload/downloadLayer?id=" + row.id;
        var unrelated = "hello";
        """
        self.assertEqual(
            [
                "../download/layerSearch/findLayer",
                "../download/layerDownload/downloadLayer?id=",
            ],
            probe.extract_endpoint_candidates(body),
        )

    def test_ambiguous_wms_matches_remain_visible_to_fail_closed_caller(self) -> None:
        duplicate = WMS_XML.replace(
            b"</Layer>\n    </Layer>",
            b"</Layer><Layer><Name>other:dtm_2m_cortina</Name>"
            b"<Title>DTM_2m_Cortina</Title></Layer>\n    </Layer>",
        )
        root = probe.parse_xml(duplicate, "test duplicate WMS")
        self.assertEqual(2, len(probe.flatten_wms_layers(root)))


if __name__ == "__main__":
    unittest.main()
