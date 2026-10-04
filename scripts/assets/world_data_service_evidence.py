"""Validate provider payloads before admitting bounded P1 context evidence."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

WFS = "http://www.opengis.net/wfs/2.0"


def feature_collection(data: bytes) -> dict[str, Any]:
    root = ET.fromstring(data)
    errors = [node.text or "" for node in root.iter()
              if node.tag.split("}")[-1] in {"ExceptionText", "ServiceException"}]
    if errors:
        raise ValueError("WFS exception: " + " | ".join(errors))
    if root.tag != f"{{{WFS}}}FeatureCollection":
        raise ValueError(f"Expected WFS 2.0 FeatureCollection, got {root.tag}")
    matched, returned = root.get("numberMatched"), root.get("numberReturned")
    members = root.findall(f"{{{WFS}}}member")
    if not matched or not matched.isdigit() or not returned or not returned.isdigit():
        raise ValueError(f"Unproven completeness: numberMatched={matched!r}, numberReturned={returned!r}")
    if int(matched) != int(returned) or int(returned) != len(members):
        raise ValueError(f"Partial WFS collection: matched={matched}, returned={returned}, members={len(members)}")
    if root.get("next"):
        raise ValueError(f"Unconsumed WFS next page: {root.get('next')}")
    return {"feature_count": len(members), "number_matched": int(matched),
            "number_returned": int(returned)}


def metric_wfs(acquisition: Any, s: Any, source: dict, bounds: list,
               root: Path, force: bool, local_names: list[str], quadrants: list[list]) -> dict:
    out = root / source["id"]
    files, errors = [], []
    service = source["service_url"]
    cap_path = out / "GetCapabilities.xml"
    if cap_path.exists() and not force:
        cap_rec = {"path": str(cap_path), "size_bytes": cap_path.stat().st_size,
                   "sha256": acquisition.sha256(cap_path), "reused": True}
    else:
        caps = acquisition.request_with_retry(s, "GET", service, params={
            "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetCapabilities"})
        cap_rec = acquisition.write_bytes(cap_path, caps.content, force)
    tree = ET.fromstring((out / "GetCapabilities.xml").read_bytes())
    types = tree.findall(f".//{{{WFS}}}FeatureType")
    names = [t.findtext(f"{{{WFS}}}Name") for t in types]
    abstracts = [node.text or '' for node in tree.iter() if node.tag.endswith('}Abstract')]
    edition_error = None
    if source.get('expected_edition') and not any(
        source['expected_edition'] in text for text in abstracts
    ):
        edition_error = f"Source edition mismatch: expected {source['expected_edition']}; advertised abstracts: {abstracts}"
        errors.append(edition_error)
    selected = []
    crs = "urn:ogc:def:crs:EPSG::25831"
    for local in local_names:
        matches = [t for t in types if (t.findtext(f"{{{WFS}}}Name") or '').split(':')[-1] == local]
        if len(matches) != 1:
            errors.append(f"Expected one advertised {local} typename; found {names}")
            continue
        t = matches[0]
        supported = [node.text for node in t if node.tag.split('}')[-1] in {'DefaultCRS', 'OtherCRS'}]
        advertised = [value for value in supported if value and value.endswith(('::25831', '/25831'))]
        if not advertised:
            errors.append(f"{local}: EPSG:25831 not advertised; axis order not guessed")
            continue
        crs = advertised[0]
        selected.append(t.findtext(f"{{{WFS}}}Name"))
    for qi, bbox in enumerate(quadrants):
        for name in selected:
            params = {"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
                      "TYPENAMES": name, "SRSNAME": crs,
                      "BBOX": ','.join(map(str, bbox)) + ',' + crs, "COUNT": "10000"}
            path = out / f"q{qi}_{name.replace(':', '_')}.gml"
            rec = {"typename": name, "quadrant": qi, "bbox_epsg25831": bbox,
                   "request": params, "admitted": False}
            try:
                if path.exists() and not force:
                    rec.update({"path": str(path), "size_bytes": path.stat().st_size,
                                "sha256": acquisition.sha256(path), "reused": True})
                elif edition_error:
                    raise ValueError(edition_error)
                else:
                    response = s.get(service, params=params, timeout=30)
                    rec.update(acquisition.write_bytes(path, response.content, force))
                    rec["http"] = acquisition.response_record(response)
                    response.raise_for_status()
                rec.update(feature_collection(path.read_bytes()))
                if edition_error:
                    raise ValueError(edition_error)
                rec["admitted"] = True
            except Exception as exc:
                rec["error"] = str(exc)
                errors.append(f"q{qi} {name}: {exc}")
            files.append(rec)
    result = {"status": "partial" if errors else "downloaded", "source": source['product'],
              "capabilities": cap_rec, "advertised_feature_types": names,
              "selected_feature_types": selected, "request_crs": crs,
              "aoi_bounds_epsg25831": bounds, "files": files, "errors": errors,
              "admitted_file_count": sum(bool(f['admitted']) for f in files)}
    acquisition.write_text(out / "extract.json", acquisition.json.dumps(result, indent=2) + '\n')
    return result


def protobuf_fields(data: bytes):
    """Read wire fields needed for MVT layer identity/count, rejecting malformed framing."""
    pos = 0
    def varint():
        nonlocal pos
        value = 0
        for shift in range(0, 70, 7):
            if pos >= len(data):
                raise ValueError("Truncated protobuf varint")
            byte = data[pos]; pos += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise ValueError("Oversized protobuf varint")
    while pos < len(data):
        key = varint(); field, wire = key >> 3, key & 7
        if field == 0:
            raise ValueError("Invalid protobuf field zero")
        if wire == 0:
            value = varint()
        elif wire in {1, 2, 5}:
            size = varint() if wire == 2 else (8 if wire == 1 else 4)
            if pos + size > len(data):
                raise ValueError("Truncated protobuf field")
            value = data[pos:pos + size]; pos += size
        else:
            raise ValueError(f"Unsupported protobuf wire type {wire}")
        yield field, wire, value


def mvt_layers(data: bytes) -> dict[str, int]:
    layers = {}
    for field, wire, value in protobuf_fields(data):
        if field != 3 or wire != 2:
            raise ValueError("Expected MVT Tile.layers framing")
        fields = list(protobuf_fields(value))
        names = [v.decode('utf-8') for f, w, v in fields if f == 1 and w == 2]
        if len(names) != 1 or names[0] in layers:
            raise ValueError("Missing/duplicate MVT layer name")
        layers[names[0]] = sum(f == 2 and w == 2 for f, w, v in fields)
    if not layers:
        raise ValueError("No MVT layers; coverage is unproven")
    return layers
