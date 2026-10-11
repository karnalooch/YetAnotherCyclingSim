"""Offline #459 analysis; writes only the selected output directory, never source/UE."""
from pathlib import Path
import csv
import hashlib
import json
import math
import statistics
import struct

def configure_cli():
    """Relocate exact pinned inputs and outputs; analysis math is unchanged."""
    import argparse
    global OUT, NATIVE, CUT, MANIFEST, LIDAR, LIDAR_RECEIPT, PROFILE, PINS
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('native-receipt', 'cut-patch', 'cut-manifest', 'lidar-csv',
                 'lidar-receipt', 'profile', 'output-dir'):
        parser.add_argument('--' + flag, type=Path, required=True)
    args = parser.parse_args()
    OUT = args.output_dir.resolve()
    NATIVE = args.native_receipt.resolve()
    CUT = args.cut_patch.resolve()
    MANIFEST = args.cut_manifest.resolve()
    LIDAR = args.lidar_csv.resolve()
    LIDAR_RECEIPT = args.lidar_receipt.resolve()
    PROFILE = args.profile.resolve()
    PINS = {
        NATIVE: '2139bd0a735f4d7222bc4293db99b89dd95adacd44f8becb22e3a8767db32feb',
        CUT: 'cabf471cf108017a1a15624880dd8ca531f880ddfeaf747bd0769b05abb75642',
        MANIFEST: '5ccfd9ece2c8cdf8140b47b4a771e5a530d7aa4835554771824bf9fd1d23404f',
        LIDAR: '6af3704cc525bcc7282989e74beb061ba6fdec9f3c7492ee6d428ca3b603fb0d',
        LIDAR_RECEIPT: 'f7bcf44f948672f70f22f055fd4781d50622ccdfa0ae8840e35ef4136449e13d',
        PROFILE: 'c0ca612dd5af5a311d1917e41d66f44aa83a9d40eed5e9e784432e06e2a52253',
    }
    OUT.mkdir(parents=True, exist_ok=True)


def verify_inputs():
    for path, expected in PINS.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path


def describe(values):
    return {'min': min(values), 'median': statistics.median(values), 'max': max(values)}


def write_json(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def main():
    verify_inputs()
    receipt = json.loads(NATIVE.read_text())
    wall = receipt['support_wall_contact']
    assert receipt['exact_sha'] == 'b9fddea3f6023239da98bec7a5107ed1124cf52e'
    assert wall['status'] == 'NATIVE_WALL_AND_SOURCE_CUT_OBSERVED'
    assert wall['source_rows_inclusive'] == [1560, 1880]
    assert wall['segments_without_matched_wall'] == []
    assert len(wall['wall_triangles']) == 640
    assert receipt['restoration']['support_triangle_sha256'] == wall['full_native_triangle_sha256']
    raw, cut_manifest = CUT.read_bytes(), json.loads(MANIFEST.read_text())
    rect = cut_manifest['rect']

    def node(ix, iy):
        assert rect['min_x'] <= ix <= rect['max_x']
        assert rect['min_y'] <= iy <= rect['max_y']
        offset = 4 * ((iy - rect['min_y']) * rect['width'] + ix - rect['min_x'])
        return struct.unpack_from('<f', raw, offset)[0]

    # Independent byte and positional check of every native-retained CUT node.
    for ix, iy, offset, raw4, x, y, z in wall['cut_source']['nodes']:
        assert x == ix * 50 and y == iy * 50
        assert node(ix, iy) == z and raw[offset:offset + 4].hex() == raw4

    def source_height(x, y, diagonal='a_d'):
        fx, fy = x / 50, y / 50
        ix, iy = math.floor(fx), math.floor(fy)
        u, v = fx - ix, fy - iy
        a, b, c, d = [node(ix + i, iy + j) for i, j in [(0, 0), (1, 0), (0, 1), (1, 1)]]
        if diagonal == 'a_d':
            return (1-u)*a + (u-v)*b + v*d if u >= v else (1-v)*a + (v-u)*c + u*d
        if diagonal == 'b_c':
            return (1-u-v)*a + u*b + v*c if u+v <= 1 else (1-v)*b + (1-u)*c + (u+v-1)*d
        return (1-u)*(1-v)*a + u*(1-v)*b + (1-u)*v*c + u*v*d

    rows = {}
    for i in range(0, 640, 2):
        first, second = wall['wall_triangles'][i:i+2]
        row = first[0]
        assert row == second[0]
        assert first[2:5] == second[2:5] and first[8:11] == second[5:8]
        for index, top, bottom in [(row, first[2:5], second[8:11]), (row+1, first[5:8], first[8:11])]:
            assert top[:2] == bottom[:2]
            if index in rows:
                assert rows[index] == (top, bottom)
            rows[index] = (top, bottom)
    assert len(rows) == 321

    # A-D was established independently in the earlier native DTM diagnostic;
    # retaining both other models here prevents conflating bilinear with mesh.
    endpoint_rows = []
    for r, (top, bottom) in sorted(rows.items()):
        endpoint_rows.append({
            'source_row': r, 'source_station_key_m': r / 8,
            'outer_top_xyz_cm': top, 'native_bottom_xyz_cm': bottom,
            'wall_height_m': (top[2] - bottom[2]) / 100,
            **{f'bottom_minus_source_{mode}_m': (bottom[2] - source_height(*bottom[:2], mode)) / 100
               for mode in ('a_d', 'b_c', 'bilinear')},
        })

    crossings = []
    envelope = []
    for r in range(1560, 1880):
        top_a, a = rows[r]
        top_b, b = rows[r+1]
        knots = {0., 1.}
        # Every x grid line, y grid line and A-D diagonal; this partitions
        # the original linear bottom into exact source-plane intervals.
        for va, vb in [(a[0]/50, b[0]/50), (a[1]/50, b[1]/50),
                       ((a[0]-a[1])/50, (b[0]-b[1])/50)]:
            if va == vb:
                continue
            for integer in range(math.floor(min(va, vb))+1, math.ceil(max(va, vb))):
                t = (integer - va) / (vb - va)
                if 0 < t < 1:
                    knots.add(t)

        def at(t):
            p = [a[k] + (b[k]-a[k])*t for k in range(3)]
            h = source_height(*p[:2])
            return {'source_segment_row': r, 't': t, 'xy_cm': p[:2],
                    'original_bottom_cm': p[2], 'source_cut_ad_cm': h,
                    'source_gap_m': (p[2]-h)/100}

        original_knots = sorted(knots)
        crossings.extend(at(t) for t in original_knots)
        # min(original line, source A-D) is a downward-only hypothetical
        # contact envelope. Add exact sign roots to preserve existing burial.
        for t0, t1 in zip(original_knots, original_knots[1:]):
            q0, q1 = at(t0), at(t1)
            g0, g1 = q0['source_gap_m'], q1['source_gap_m']
            if g0 * g1 < 0:
                knots.add(t0 - g0 * (t1-t0) / (g1-g0))
        segment = []
        for t in sorted(knots):
            q = at(t)
            q['proposed_bottom_cm'] = min(q['original_bottom_cm'], q['source_cut_ad_cm'])
            q['proposed_downward_delta_m'] = (q['proposed_bottom_cm'] - q['original_bottom_cm']) / 100
            q['unchanged_top_cm'] = top_a[2] + (top_b[2]-top_a[2])*t
            segment.append(q)
        # Dense independent checks verify the candidate piecewise lines have
        # no source gap; they do not claim current native terrain contact.
        for q0, q1 in zip(segment, segment[1:]):
            for alpha in (0.25, 0.5, 0.75):
                t = q0['t'] + (q1['t']-q0['t'])*alpha
                z = q0['proposed_bottom_cm'] + (q1['proposed_bottom_cm']-q0['proposed_bottom_cm'])*alpha
                check = at(t)
                assert z <= check['source_cut_ad_cm'] + 1e-7
                assert z <= check['original_bottom_cm'] + 1e-7
        envelope.extend(segment)

    clouds = list(csv.DictReader(LIDAR.open()))
    source_frames = json.loads(LIDAR_RECEIPT.read_text())['transects']
    transects = []
    for f in source_frames:
        r = f['profile_section_index']
        top, bottom = rows[r]
        easting, northing = 483000.25 + bottom[0]/100, 4409516.25 - bottom[1]/100
        nearby = [p for p in clouds if int(p['profile_section_index']) == r
                  and p['classification'] == '2'
                  and math.hypot(float(p['easting_m'])-easting, float(p['northing_m'])-northing) <= .5]
        zz = [float(p['z_m']) for p in nearby]
        transects.append({
            'station_key_m': r/8, 'row': r,
            'pavement_edge0_m': f['source_samples'][0]['frozen_pavement_m'],
            'outer_top_m': top[2]/100, 'native_bottom_m': bottom[2]/100,
            'source_cut_ad_m': source_height(*bottom[:2])/100,
            'wall_height_m': (top[2]-bottom[2])/100,
            'lidar_class2_xy_ball_radius_m': .5,
            'lidar_class2_xy_ball_count': len(zz),
            'lidar_class2_z_range_m': [min(zz), max(zz)] if zz else None,
            'bottom_minus_class2_median_m': bottom[2]/100 - statistics.median(zz) if zz else None,
            'lidar_point_ids': [[p['tile'], int(p['point_index'])] for p in nearby],
            'interpretation': 'raw ground observations, not a surveyed wall-foot target',
        })

    summary = {
        'status': 'OFFLINE_NATIVE_WALL_SOURCE_COMPARISON', 'issue': 459,
        'native_sha': receipt['exact_sha'], 'source_sha': receipt['source_road_sha'],
        'source_rows': [1560, 1880], 'station_keys_m': [195, 235],
        'source_diagonal_basis': 'a_d; docs/WORLD_BUILDING_BIBLE.md historical native proof and scripts/ue/ma2141_road_preview.py',
        'inputs': [{'path': str(p), 'sha256': sha, 'size_bytes': p.stat().st_size} for p, sha in PINS.items()],
        'native_payload_sha256': wall['payload_sha256'],
        'retained_cut_nodes_verified': len(wall['cut_source']['nodes']),
        'endpoint_count': len(rows),
        'wall_height_m': describe([p['wall_height_m'] for p in endpoint_rows]),
        'endpoint_bottom_minus_source_ad_m': describe([p['bottom_minus_source_a_d_m'] for p in endpoint_rows]),
        'facet_crossing_count': sum(0 < q['t'] < 1 for q in crossings),
        'source_gap_extrema': {'minimum': min(crossings, key=lambda q: q['source_gap_m']),
                              'maximum': max(crossings, key=lambda q: q['source_gap_m'])},
        'segments_source_gap_over_1cm': sorted({q['source_segment_row'] for q in crossings if q['source_gap_m'] > .01}),
        'segments_source_burial_over_1cm': sorted({q['source_segment_row'] for q in crossings if q['source_gap_m'] < -.01}),
        'hypothetical_downward_only_envelope': {
            'formula': 'min(original line, authenticated source CUT A-D triangles)',
            'bottom_polyline_records_with_shared_endpoints': len(envelope),
            'delta_m': describe([q['proposed_downward_delta_m'] for q in envelope]),
            'source_gap_removed_analytically': True, 'existing_burial_preserved': True,
            'top_xyz_unchanged': True, 'road_xyz_unchanged': True,
            'candidate_applied': False, 'terrain_updated': False,
            'must_be_recomputed_against_actual_final_native_surface': True,
        },
        'final_native_landscape_height_observed': False,
        'actual_rendered_landscape_lod': 'UNKNOWN',
        'owner_visual_pass': False, 'geometry_repair_applied': False,
        'remaining_essential_measurement': 'Existing Landscape-only owner-verified collision readback at endpoint/crossing XY on final composed consumer; matching render/wireframe at worst crossing. Raw source CUT is not final Landscape.',
        'transects': transects,
    }
    write_json('native-wall-source-comparison.json', summary)
    write_json('native-wall-endpoints.json', endpoint_rows)
    write_json('source-facet-crossings.json', crossings)
    write_json('hypothetical-bottom-envelope.json', envelope)
    with (OUT / 'wall-transects.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=[k for k in transects[0] if k not in ('lidar_point_ids','interpretation')])
        writer.writeheader()
        writer.writerows({k:v for k,v in row.items() if k in writer.fieldnames} for row in transects)

    # Scientific review figure. Original images and point exports stay intact.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    profile = json.loads(PROFILE.read_text())
    assert profile['origin_epsg_m'] == [483000.25, 4409516.25]
    native_shoulders = {}
    pavement_edges = {q[0]: q[1:] for q in wall['pavement_edge_rows_cm']}
    for offset in range(0, len(wall['native_top_triangles']), 2):
        first, second = wall['native_top_triangles'][offset:offset+2]
        r = 1560 + offset // 2
        assert first[4:7] == second[1:4] and first[7:10] == second[7:10]
        for index, outer, inner in [(r, first[1:4], first[4:7]),
                                     (r+1, first[7:10], second[4:7])]:
            assert outer == rows[index][0]
            assert inner[:2] == pavement_edges[index][:2]
            assert abs(pavement_edges[index][2] - inner[2] - 8.0) < 1e-7
            if index in native_shoulders:
                assert native_shoulders[index] == (outer, inner)
            native_shoulders[index] = (outer, inner)
    fig, axes = plt.subplots(3, 3, figsize=(15, 11), sharex=True, sharey=True)
    for ax, frame in zip(axes.flat, source_frames, strict=True):
        r = frame['profile_section_index']
        center_e, center_n = frame['center_epsg25831_m']
        lateral = frame['lateral_unit']
        top, bottom = rows[r]
        datum = frame['source_samples'][0]['frozen_pavement_m']

        def lateral_at(x, y):
            return (483000.25 + x - center_e)*lateral[0] + (4409516.25-y-center_n)*lateral[1]

        samples = [p for p in clouds if int(p['profile_section_index']) == r]
        for is_ground, color, label in [(False, '#888888', 'Other original LiDAR classes'),
                                         (True, '#238443', 'LiDAR class 2')]:
            selected = [p for p in samples if (p['classification'] == '2') == is_ground]
            ax.scatter([float(p['lateral_m']) for p in selected],
                       [float(p['z_m'])-datum for p in selected], s=9, c=color, alpha=.65, label=label)
        station = profile['stations'][r]
        px = [lateral_at(*xy) for xy in station['xy_local_m']]
        pz = [z+.04-datum for z in station['candidate_ground_m']]
        ax.plot(px, pz, color='#292929', lw=2, label='Frozen pavement cross-section')
        tx = lateral_at(top[0]/100, top[1]/100)
        shoulder_outer, shoulder_inner = native_shoulders[r]
        shoulder_x = [lateral_at(p[0]/100, p[1]/100) for p in (shoulder_outer, shoulder_inner)]
        shoulder_z = [p[2]/100-datum for p in (shoulder_outer, shoulder_inner)]
        ax.plot(shoulder_x, shoulder_z, color='#b8860b', lw=2, label='Native shoulder top')
        ax.plot([shoulder_x[1], px[0]], [shoulder_z[1], pz[0]], color='#292929', lw=2,
                label='Pavement side (8 cm)')
        ax.plot([tx, tx], [bottom[2]/100-datum, top[2]/100-datum], color='#be3030', lw=2.5,
                marker='o', markersize=3, label='Native wall')
        xx = [-4.5 + i*.05 for i in range(181)]
        yy = [source_height((center_e-483000.25+d*lateral[0])*100,
                            (4409516.25-center_n-d*lateral[1])*100)/100-datum for d in xx]
        ax.plot(xx, yy, color='#2b6cb0', lw=1.25, ls='--', label='Source CUT A-D surface')
        ax.set_title(f'Source station key {r/8:.0f} m | row {r}')
        ax.set_xlim(-4.5, 4.5)
        ax.set_ylim(-3, 1.5)
        ax.grid(alpha=.2)
    fig.supxlabel('Source transverse coordinate (m); LiDAR strip retains |along| ≤ 1 m', y=.082)
    fig.supylabel('Height relative to frozen pavement edge 0 (m)')
    fig.suptitle('Hairpin 0081: actual native wall vs retained source CUT and raw LiDAR\n'
                 'Local detail; source CUT is not a measurement of the final composed Landscape', fontsize=14)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=3, bbox_to_anchor=(.5, .006))
    fig.tight_layout(rect=(.015, .12, 1, .94))
    fig.savefig(OUT/'native-wall-source-transects.png', dpi=140, bbox_inches='tight')
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].plot([q['source_station_key_m'] for q in endpoint_rows],
                 [q['wall_height_m'] for q in endpoint_rows], color='#be3030', lw=1.5)
    axes[0].set_ylabel('Actual wall height (m)')
    axes[1].plot([q['source_segment_row']/8+q['t']/8 for q in crossings],
                 [q['source_gap_m']*1000 for q in crossings], color='#2b6cb0', lw=1)
    axes[1].axhline(0, color='#555555', lw=.7)
    axes[1].set_ylabel('Bottom minus source CUT (mm)')
    axes[1].set_xlabel('Source station key (m); not cumulative wall chainage')
    for ax in axes:
        ax.grid(alpha=.2)
    fig.suptitle('Native wall endpoints match source facets; linear spans cross facet breaks\n'
                 'b9fddea / frozen source c5573b3 / final native Landscape contact remains unmeasured')
    fig.tight_layout()
    fig.savefig(OUT/'native-wall-facet-contact.png', dpi=150)
    plt.close(fig)
    verify_inputs()
    print(json.dumps({k:summary[k] for k in ('wall_height_m', 'endpoint_bottom_minus_source_ad_m',
                    'facet_crossing_count', 'source_gap_extrema', 'hypothetical_downward_only_envelope', 'transects')}, indent=2))


if __name__ == '__main__':
    configure_cli()
    main()
