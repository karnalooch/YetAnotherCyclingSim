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

WCS10_CAPS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<WCS_Capabilities xmlns="http://www.opengis.net/wcs" version="1.0.0">
  <ContentMetadata>
    <CoverageOfferingBrief>
      <name>rv:DTM_2m_clip</name>
      <label>DTM_2m_clip</label>
    </CoverageOfferingBrief>
  </ContentMetadata>
</WCS_Capabilities>
"""

CSW_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<csw:GetRecordsResponse xmlns:csw="http://www.opengis.net/cat/csw/2.0.2"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dct="http://purl.org/dc/terms/">
  <csw:SearchResults numberOfRecordsMatched="1" numberOfRecordsReturned="1">
    <csw:Record>
      <dc:identifier>rv:dtm-cortina-2m</dc:identifier>
      <dc:title>DTM_2m_Cortina</dc:title>
      <dct:references>https://example.test/cortina.tif</dct:references>
    </csw:Record>
  </csw:SearchResults>
</csw:GetRecordsResponse>
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

    def test_wcs10_coverage_parser_supports_legacy_shape(self) -> None:
        root = probe.parse_xml(WCS10_CAPS_XML, "test WCS 1.0")
        matches = probe.wcs_coverage_candidates(
            root,
            wms_name="rv:DTM_2m_clip",
        )
        self.assertEqual(
            [{"identifier": "rv:DTM_2m_clip", "title": "DTM_2m_clip"}],
            matches,
        )

    def test_csw_filter_constraint_escapes_literal(self) -> None:
        constraint = probe.csw_filter_constraint('DTM & "Cortina"')
        self.assertIn("<ogc:PropertyName>csw:AnyText</ogc:PropertyName>", constraint)
        self.assertIn("%DTM &amp; &quot;Cortina&quot;%", constraint)
        self.assertNotIn("CQL_TEXT", constraint)

    def test_csw_parser_keeps_identifier_title_and_distribution(self) -> None:
        root = probe.parse_xml(CSW_XML, "test CSW")
        parsed = probe.parse_csw_records(root)
        self.assertEqual(1, parsed["matched"])
        self.assertEqual(1, parsed["returned"])
        self.assertEqual(
            ["rv:dtm-cortina-2m"],
            parsed["records"][0]["identifier"],
        )
        self.assertEqual(
            ["https://example.test/cortina.tif"],
            parsed["records"][0]["references"],
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

    def test_endpoint_candidate_extraction_does_not_cross_quote_boundaries(self) -> None:
        body = """var a = "download"; var b = '../rest/catalog'; var c = "safe";"""
        self.assertEqual(
            ["download", "../rest/catalog"],
            probe.extract_endpoint_candidates(body),
        )

    def test_json_catalog_matches_find_cortina_layer(self) -> None:
        payload = {
            "result": [
                {"id": 10, "name": "irrelevant"},
                {
                    "id": 11,
                    "name": "DTM_2m_clip",
                    "workspace": "rv",
                    "description": "Cortina terrain",
                },
            ]
        }
        matches = probe.json_catalog_matches(payload)
        self.assertEqual(1, len(matches))
        self.assertEqual("$.result[1]", matches[0]["path"])
        self.assertEqual("DTM_2m_clip", matches[0]["item"]["name"])

    def test_query_url_preserves_existing_query(self) -> None:
        url = probe.query_url(
            "https://example.test/ows?",
            {"service": "WCS", "request": "GetCapabilities"},
        )
        self.assertIn("?&service=WCS", url)
        self.assertIn("request=GetCapabilities", url)

    def test_wcs_endpoint_candidates_include_described_and_workspace(self) -> None:
        candidates = probe.wcs_endpoint_candidates(
            [{"owsURL": "https://example.test/geoserver/ows?"}]
        )
        self.assertIn(probe.WCS_ENDPOINT, candidates)
        self.assertIn("https://example.test/geoserver/ows?", candidates)
        self.assertIn(
            "https://idt2-geoserver.regione.veneto.it/geoserver/rv/wcs",
            candidates,
        )

    def test_direct_coverage_ids_prefer_exact_wms_name_and_aliases(self) -> None:
        self.assertEqual(
            [
                "rv:DTM_2m_clip",
                "DTM_2m_clip",
                "DTM_2m_Cortina",
            ],
            probe.direct_coverage_ids("rv:DTM_2m_clip"),
        )

    def test_direct_describe_can_prove_unadvertised_wcs_coverage(self) -> None:
        original = probe.fetch_coverage_description

        def fake_fetch(endpoint: str, version: str, coverage_id: str):
            if version == "1.0.0" and coverage_id == "rv:DTM_2m_clip":
                return (
                    "https://example.test/describe",
                    {"offset_magnitudes": [2.0, 2.0]},
                    [2.0, 2.0],
                )
            raise RuntimeError("not exposed")

        probe.fetch_coverage_description = fake_fetch
        try:
            result = probe.probe_direct_wcs_descriptions(
                "rv:DTM_2m_clip",
                ["https://example.test/wcs"],
            )
        finally:
            probe.fetch_coverage_description = original

        self.assertEqual(1, len(result["proven"]))
        self.assertEqual("rv:DTM_2m_clip", result["proven"][0]["coverage_id"])
        self.assertEqual("1.0.0", result["proven"][0]["version"])
        self.assertEqual([2.0, 2.0], result["proven"][0]["proven_native_resolution_m"])

    def test_direct_describe_stops_after_terminal_wcs_disabled_error(self) -> None:
        original = probe.fetch_coverage_description
        calls = []

        def fake_fetch(endpoint: str, version: str, coverage_id: str):
            calls.append((endpoint, version, coverage_id))
            raise RuntimeError(
                "WCS DescribeCoverage exception: Service WCS is disabled"
            )

        probe.fetch_coverage_description = fake_fetch
        try:
            result = probe.probe_direct_wcs_descriptions(
                "rv:DTM_2m_clip",
                [
                    "https://example.test/wcs",
                    "https://example.test/rv/wcs",
                ],
            )
        finally:
            probe.fetch_coverage_description = original

        self.assertEqual(2, len(calls))
        self.assertEqual(2, len(result["attempts"]))
        self.assertTrue(
            all(item.get("terminal_endpoint_error") for item in result["attempts"])
        )
        self.assertEqual([], result["proven"])

    def test_olympic_viewer_contract_uses_webgis_86(self) -> None:
        self.assertEqual(
            "https://idt2.regione.veneto.it/idt/webgis/viewer?webgisId=86",
            probe.VIEWER_URL,
        )

    def test_legacy_describe_layer_endpoint_is_normalized_to_https(self) -> None:
        endpoint = probe.normalize_service_endpoint(
            "http://idt2-geoserver.regione.veneto.it:80/geoserver/wcs?"
        )
        self.assertEqual(
            "https://idt2-geoserver.regione.veneto.it/geoserver/wcs",
            endpoint,
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
