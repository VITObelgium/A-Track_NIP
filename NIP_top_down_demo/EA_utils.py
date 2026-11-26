# Author: Alexandra Evans <alexandra.evans@vito.be>
# Copyright © 2026 VITO
#
# SPDX-FileCopyrightText: 2026 VITO
# SPDX-License-Identifier: MIT
#
# Please acknowledge the author and copyright holder in outputs produced using these scripts.
#
# Licensed under the MIT License.
# See LICENCE-SCRIPTS.md in the repository root for the licence terms.

"""Helper functions for the A-Track demo on ecosystem accounting for business (extent, transformations, conversion,
connectivity). Used by all Ecosystem_* scripts."""
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import rasterio
from matplotlib.patches import Patch
from rasterio.features import shapes as rio_shapes
from rasterio.mask import mask
from rasterio.warp import reproject, Resampling
from scipy.ndimage import label as ndlabel
from scipy.spatial import cKDTree, distance_matrix
from shapely.geometry import LineString, box, shape as shapely_shape
from skimage.measure import regionprops

def get_pixel_resolution(raster_path):
    """Get pixel resolution from raster metadata (average if pixels are not square)."""
    with rasterio.open(raster_path) as src:
        pixel_width = abs(src.transform.a)
        pixel_height = abs(src.transform.e)
    if not math.isclose(pixel_width, pixel_height):
        print(f"Warning: Non-square pixels detected ({pixel_width} x {pixel_height}). Using average.")
        return (pixel_width + pixel_height) / 2
    return pixel_width

def validate_geometry_within_raster(geometry_gdf, raster_path, geometry_name="Geometry"):
    """Check that a GeoDataFrame's geometry falls fully within the raster extent (checked in the raster's CRS)."""
    with rasterio.open(raster_path) as src:
        raster_bounds = box(*src.bounds)
        geometry = geometry_gdf.to_crs(src.crs).geometry.union_all()
    if not raster_bounds.intersects(geometry):
        raise ValueError(f"{geometry_name} does not intersect with the extent of {Path(raster_path).name}")
    if not raster_bounds.covers(geometry):
        raise ValueError(f"{geometry_name} extends beyond the extent of {Path(raster_path).name}. "
                         f"Please provide a larger raster or reduce the buffer size.")

def clip_raster_to_geometry(raster_path, gdf):
    """Clip a single-band raster to the geometry in a GeoDataFrame.

    Returns the clipped data (2D masked array, nodata/outside-polygon pixels masked) and the output profile.
    """
    with rasterio.open(raster_path) as src:
        if src.count != 1:
            raise ValueError(f"{Path(raster_path).name} has {src.count} bands, a single-band habitat map is expected")
        shapes = gdf.to_crs(src.crs).geometry
        clipped, transform = mask(src, shapes, crop=True, filled=False)
        values = np.ma.getdata(clipped[0])
        invalid = np.ma.getmaskarray(clipped[0])
        if src.nodata is not None:
            nodata = src.nodata
        else:
            # No nodata defined in the file: 0 is treated as nodata
            print(f"Note: {Path(raster_path).name} has no nodata value defined; treating 0 as nodata")
            nodata = 0
        data = np.ma.masked_array(values, mask=invalid | (values == nodata))
        profile = src.profile.copy()
        profile.update(height=data.shape[0], width=data.shape[1], transform=transform, nodata=nodata, count=1)
    return data, profile

def calculate_pixel_stats(clipped_array, pixel_resolution):
    """Calculate habitat areas (ha) per raster value from a clipped masked array."""
    values, counts = np.unique(clipped_array.compressed(), return_counts=True)
    return pd.DataFrame({
        'raster_value': values.astype(int),
        'area_ha': counts * (pixel_resolution ** 2) / 10000
    })

def load_lut(lut_path, sep, value_col, code_col, name_col, level_col, map_level=3):
    """Read the LUT and return (lookup for the map level, names per level).

    - Lookup: DataFrame with 'raster_value' and 'eunis_code', used to label the map, which is at `map_level` (3 by
      default; a level 2 map needs 2). Only rows of that level (and childless classes of coarser levels) are used,
      so classes repeated on several levels in the LUT (e.g. a level 1 class without children that is listed on
      levels 1-3) are counted once.
    - Names per level: {level: {code: name}}, built from all rows, used to name the level 1, 2 and 3 output tables.
    Leading/trailing spaces are removed from the code and name columns.
    """
    lut = pd.read_csv(lut_path, sep=sep, dtype=str, keep_default_na=False)
    print("LUT columns:", lut.columns.tolist())
    missing = {value_col, code_col, name_col, level_col} - set(lut.columns)
    if missing:
        raise ValueError(f"LUT is missing column(s): {sorted(missing)}. Available: {lut.columns.tolist()}")
    for col in (code_col, name_col):
        lut[col] = lut[col].str.strip()
    lut[level_col] = lut[level_col].str.strip()
    lut[value_col] = pd.to_numeric(lut[value_col].str.strip(), errors='raise').astype(int)

    names = {int(level): dict(zip(grp[code_col], grp[name_col]))
             for level, grp in lut.groupby(lut[level_col].astype(int))}
    names.setdefault(3, {})['Unknown'] = 'Unknown'

    # Rows of the map level, plus classes listed on a coarser level that have no child classes in the LUT (e.g. the
    # level 1 class M in a level 2 map): they are mapped as they are, like C and J. Repeats are counted once.
    all_codes = lut[code_col].str.replace('.', '', regex=False)
    has_children = all_codes.map(lambda c: (all_codes.str.startswith(c) & (all_codes != c)).any())
    level_num = lut[level_col].astype(int)
    keep = (level_num == map_level) | ((level_num < map_level) & ~has_children)
    lut3 = lut.loc[keep, [value_col, code_col]].drop_duplicates()
    lut3.columns = ['raster_value', 'eunis_code']
    if lut3['raster_value'].duplicated().any():
        dup = lut3.loc[lut3['raster_value'].duplicated(), 'raster_value'].unique().tolist()
        raise ValueError(f"LUT has duplicated level {map_level} raster values: {dup}")
    return lut3, names

def add_eunis_codes(stats_df, lut, year_label):
    """Merge EUNIS codes from the LUT into the stats and sum the areas per EUNIS code."""
    merged = stats_df.merge(lut[['raster_value', 'eunis_code']], on='raster_value', how='left')
    unmapped = merged.loc[merged['eunis_code'].isna(), 'raster_value'].tolist()
    if unmapped:
        print(f"Warning: {year_label} raster values not in the LUT (reported as 'Unknown'): {unmapped}")
    merged['eunis_code'] = merged['eunis_code'].fillna('Unknown')
    # Several raster values may map to the same code, so sum per code to avoid duplicated rows
    return merged.groupby('eunis_code', as_index=False)['area_ha'].sum()

def eunis_code_at_level(code, level):
    """Return the parent code of a (level 3) EUNIS code at the requested level.

    EUNIS codes are hierarchical by prefix: level 1 is the first character (e.g. 'T'), level 2 the first two
    (e.g. 'T1'), level 3 the first three (e.g. 'T11'). Dots (older EUNIS format, e.g. 'C1.1') are ignored when
    taking the prefix. Level 3 codes are returned unchanged.
    """
    if code == 'Unknown' or level >= 3:
        return code
    return code.replace('.', '')[:level]

def aggregate_to_level(combined, level, names, area_columns):
    """Aggregate the level 3 table to a coarser level; each level 3 row falls in exactly one parent (no double counting).

    names is the {level: {code: name}} dict returned by load_lut.
    """
    table = combined.copy()
    table['EUNIS_code'] = table['EUNIS_code'].map(lambda c: eunis_code_at_level(c, level))
    table = table.groupby('EUNIS_code', as_index=False)[area_columns].sum()
    table.insert(1, 'EUNIS_name', table['EUNIS_code'].map(names.get(level, {})).fillna(''))
    return table.round(2)

def read_qml_palette(qml_path):
    """Read a QGIS paletted-raster style (.qml) and return {raster_value: (hex colour, label)}."""
    root = ET.parse(qml_path).getroot()
    return {int(e.get('value')): (e.get('color'), e.get('label'))
            for e in root.iter('paletteEntry')}

def add_scale_bar(ax, shape, pixel_size_m):
    """Draw a scale bar (rounded to 1, 2 or 5 x 10^n m, up to ~20% of the map width) in the bottom-left corner."""
    target = shape[1] * pixel_size_m * 0.2
    magnitude = 10 ** math.floor(math.log10(target))
    length_m = max(m * magnitude for m in (1, 2, 5, 10) if m * magnitude <= target)
    length_px = length_m / pixel_size_m
    x0, y0 = shape[1] * 0.03, shape[0] * 0.97
    ax.plot([x0, x0 + length_px], [y0, y0], color='black', linewidth=3, solid_capstyle='butt')
    label = f"{length_m / 1000:g} km" if length_m >= 1000 else f"{length_m:g} m"
    ax.text(x0 + length_px / 2, y0 - shape[0] * 0.015, label, ha='center', va='bottom', fontsize=8)

def export_map_image(data, palette, out_path, title, pixel_size_m, names=None, dpi=200):
    """Save a clipped habitat map (2D masked array) as an image coloured with the QGIS palette, with a legend.

    pixel_size_m sets the scale bar length. names is an optional {code: name} dict used to extend the legend labels.
    Values not in the palette are
    drawn grey and reported.
    """
    values = np.ma.getdata(data)
    rgb = np.ones(values.shape + (3,))  # white background = nodata / outside polygon
    present = np.unique(data.compressed())
    handles = []
    unstyled = []
    for val in present:
        colour, label = palette.get(int(val), ('#999999', None))
        if label is None:
            unstyled.append(int(val))
            label = str(int(val))
        rgb[(values == val) & ~np.ma.getmaskarray(data)] = matplotlib.colors.to_rgb(colour)
        text = f"{label} - {names[label][:40]}" if names and label in names else label
        handles.append(Patch(facecolor=colour, edgecolor='none', label=text))
    if unstyled:
        print(f"Warning: raster values not in the legend file (drawn grey): {unstyled}")

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.imshow(rgb, interpolation='nearest')
    ax.set_title(title)
    add_scale_bar(ax, values.shape, pixel_size_m)
    ax.axis('off')
    ax.legend(handles=sorted(handles, key=lambda h: h.get_label()), loc='center left', bbox_to_anchor=(1.01, 0.5),
              fontsize=6, frameon=False, ncol=1 if len(handles) <= 30 else 2)
    fig.savefig(out_path, dpi=dpi, bbox_inches='tight', pil_kwargs={'quality': 90})
    plt.close(fig)


def load_threat_lookup(threat_csv, sep=";", encoding="latin-1", code_col="Code", threat_col="Threat"):
    """Read the EUNIS threat status table and return {eunis_code: threat_status} (codes without a status are dropped)."""
    threat = pd.read_csv(threat_csv, sep=sep, encoding=encoding, dtype=str, keep_default_na=False)
    threat.columns = threat.columns.str.strip()
    threat[code_col] = threat[code_col].str.strip()
    threat[threat_col] = threat[threat_col].str.strip()
    threat = threat[threat[threat_col] != ""]
    if threat[code_col].duplicated().any():
        dup = threat.loc[threat[code_col].duplicated(), code_col].tolist()
        print(f"Warning: duplicated codes in threat table, keeping first: {dup}")
        threat = threat.drop_duplicates(code_col)
    return dict(zip(threat[code_col], threat[threat_col]))

def aggregate_by_threat_status(lvl3_table, threat_lookup, area_columns, threat_order):
    """Sum level 3 areas per threat status. Returns (table in threat_order, codes without a status)."""
    table = lvl3_table.copy()
    table['threat_status'] = table['EUNIS_code'].map(threat_lookup)
    no_status = table.loc[table['threat_status'].isna(), ['EUNIS_code', 'EUNIS_name'] + area_columns]
    agg = table.dropna(subset=['threat_status']).groupby('threat_status')[area_columns].sum()
    return agg.reindex(threat_order).fillna(0).rename_axis('threat_status').reset_index(), no_status

def plot_level1_summary(lvl1_table, natural_groups, other_groups, colours, area_columns, year_labels, out_path,
                        natural_label="Natural habitats", dpi=200):
    """Bar chart of level 1 class areas for two years, laid out to show what makes up 'natural habitats'.

    Left: one bar pair per natural class, then the natural habitats total as stacked bars (same colours as the
    classes, so the stack visibly adds up the classes to its left). Right, after a gap: the other (non-natural)
    classes. natural_groups / other_groups are ordered {display label: level 1 code}; colours is {label: colour}.
    The first year is drawn paler than the second.
    """
    area = lvl1_table.set_index('EUNIS_code')[area_columns]
    get = lambda code: area.loc[code] if code in area.index else pd.Series(0.0, index=area_columns)
    alphas = (0.5, 1.0)
    width = 0.38
    offsets = (-width / 2, width / 2)

    n_nat = len(natural_groups)
    pos_nat = np.arange(n_nat)
    pos_total = n_nat + 0.8
    pos_other = pos_total + 1.8 + np.arange(len(other_groups))

    fig, ax = plt.subplots(figsize=(11, 6))
    for pos, (label, code) in zip(pos_nat, natural_groups.items()):
        for off, col, alpha in zip(offsets, area_columns, alphas):
            ax.bar(pos + off, get(code)[col], width, color=colours[label], alpha=alpha, linewidth=0)
    for off, col, alpha in zip(offsets, area_columns, alphas):
        bottom = 0.0
        for label, code in natural_groups.items():
            ax.bar(pos_total + off, get(code)[col], width, bottom=bottom, color=colours[label], alpha=alpha,
                   linewidth=0)
            bottom += get(code)[col]
    for pos, (label, code) in zip(pos_other, other_groups.items()):
        for off, col, alpha in zip(offsets, area_columns, alphas):
            ax.bar(pos + off, get(code)[col], width, color=colours[label], alpha=alpha, linewidth=0)

    ax.set_xticks(list(pos_nat) + [pos_total] + list(pos_other))
    ax.set_xticklabels(list(natural_groups) + [natural_label] + list(other_groups), rotation=45, ha='right')
    for tick, bold in zip(ax.get_xticklabels(), [False] * n_nat + [True] + [False] * len(other_groups)):
        tick.set_fontweight('bold' if bold else 'normal')
    ax.set_ylabel('Area (ha)')
    ax.grid(axis='y', alpha=0.3)
    ax.set_axisbelow(True)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)

    # Group headers with brackets above the bars
    ymax = ax.get_ylim()[1]
    ax.set_ylim(0, ymax * 1.12)
    y = ymax * 1.03
    for x0, x1, text in ((pos_nat[0] - 0.4, pos_nat[-1] + 0.4, 'Natural classes'),
                         (pos_total - 0.4, pos_total + 0.4, 'Total'),
                         (pos_other[0] - 0.4, pos_other[-1] + 0.4, 'Non-natural classes')):
        ax.plot([x0, x1], [y, y], color='black', linewidth=1)
        ax.text((x0 + x1) / 2, y + ymax * 0.01, text, ha='center', va='bottom', fontsize=10)
    ax.annotate('', xy=(pos_total - 0.45, ymax * 0.5), xytext=(pos_nat[-1] + 0.45, ymax * 0.5),
                arrowprops=dict(arrowstyle='->', color='grey'))
    ax.text((pos_nat[-1] + pos_total) / 2, ymax * 0.52, 'sum', ha='center', va='bottom', color='grey', fontsize=9)

    ax.legend(handles=[Patch(facecolor='#444444', alpha=a, label=lab) for a, lab in zip(alphas, year_labels)],
              loc='upper left', bbox_to_anchor=(0.0, 0.9), frameon=False)
    fig.savefig(out_path, dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)

def plot_threat_status(agg, area_columns, year_labels, out_path, dpi=200):
    """Grouped bar chart of area per Red List threat status for two years."""
    x = np.arange(len(agg))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.bar(x - width / 2, agg[area_columns[0]], width, label=year_labels[0], color='#002060')
    ax.bar(x + width / 2, agg[area_columns[1]], width, label=year_labels[1], color='#ED7D31')
    ax.set_xticks(x)
    ax.set_xticklabels(agg['threat_status'], fontsize=11)
    ax.set_xlabel('Red List threat status', fontsize=12)
    ax.set_ylabel('Area (ha)', fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(axis='y', alpha=0.3)
    ax.set_axisbelow(True)
    fig.savefig(out_path, dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)


# ==========================================================================
# Setup helpers
# ==========================================================================

def habitat_raster_values(lut3, codes, level):
    """Raster values of the level 3 LUT classes whose code, at `level`, is in `codes` (e.g. level 2, ['R1', 'R2'])."""
    parent = lut3['eunis_code'].map(lambda c: eunis_code_at_level(c, level))
    selected = lut3[parent.isin(codes)]
    missing = set(codes) - set(parent[parent.isin(codes)])
    if missing:
        print(f"Warning: no level 3 classes in the LUT belong to {sorted(missing)} (level {level})")
    return selected['raster_value'].tolist()

def buffer_geodataframe(gdf, distance_m):
    """Buffer a GeoDataFrame by a distance in meters (via an estimated UTM CRS if the CRS is geographic)."""
    if distance_m <= 0:
        return gdf.copy()
    out = gdf.copy()
    if gdf.crs.is_geographic:
        out = gdf.to_crs(gdf.estimate_utm_crs())
        out['geometry'] = out.geometry.buffer(distance_m)
        return out.to_crs(gdf.crs)
    out['geometry'] = out.geometry.buffer(distance_m)
    return out

def check_landscape_coverage(gdf_landscape, raster_path, radius_m):
    """Warn if the raster does not cover the whole landscape (site + radius). Returns True if fully covered."""
    with rasterio.open(raster_path) as src:
        covered = box(*src.bounds).covers(gdf_landscape.to_crs(src.crs).geometry.union_all())
    if not covered:
        print(f"Warning: {raster_path.name} does not cover the full {radius_m} m landscape around the site - "
              f"the landscape analysis is limited to the raster extent")
    return covered


# ==========================================================================
# Patches
# ==========================================================================

def extract_patches(habitat_mask, pixel_area_m2, min_area_ha):
    """Label 4-connected habitat patches (no diagonal joins) and drop those below the minimum mapping unit."""
    labeled, _ = ndlabel(habitat_mask)
    min_px = math.ceil(min_area_ha * 10_000 / pixel_area_m2)
    keep = [p.label for p in regionprops(labeled) if p.area >= min_px]
    labeled_f, n = ndlabel(np.isin(labeled, keep).astype(np.uint8))
    return labeled_f, n

def patch_table(labeled, transform, pixel_area_m2):
    """Per-patch area, perimeter, shape index (1 = circle) and centroid (map coordinates)."""
    pixel_size = abs(transform.a)
    records = []
    for p in regionprops(labeled):
        area_ha = p.area * pixel_area_m2 / 10_000
        perimeter = p.perimeter * pixel_size
        shape_index = perimeter / (2 * np.sqrt(np.pi * p.area * pixel_area_m2))
        cy, cx = p.centroid
        x, y = transform * (cx + 0.5, cy + 0.5)  # +0.5: centre of the pixel
        records.append(dict(patch_id=p.label, area_ha=round(area_ha, 4), perimeter_m=round(perimeter, 1),
                            shape_index=round(shape_index, 3), centroid_x=x, centroid_y=y))
    return pd.DataFrame(records, columns=['patch_id', 'area_ha', 'perimeter_m', 'shape_index', 'centroid_x',
                                          'centroid_y'])

def edge_distance_matrix(labeled, transform, patches, max_dist):
    """Edge-to-edge distances (m) between patches.

    Pairs whose bounding boxes are within max_dist of each other get the pixel-to-pixel gap (pixels as squares).
    For other pairs, which are further apart than max_dist anyway, the distance only has to be correct in being larger
    than max_dist: a circle approximation (centroid distance minus both radii), never below the bounding box gap
    (a true lower bound; the circle approximation alone can underestimate for elongated patches).
    """
    pixel = abs(transform.a)
    props = regionprops(labeled)
    ids = patches['patch_id'].values
    centroids = patches[['centroid_x', 'centroid_y']].values
    radii = np.sqrt(patches['area_ha'].values * 10_000 / np.pi)
    dist = np.maximum(0.0, distance_matrix(centroids, centroids) - radii[:, None] - radii[None, :])

    bbox = np.array([p.bbox for p in props], dtype=float) * pixel   # (min_row, min_col, max_row, max_col) in m
    coords = [p.coords * pixel for p in props]
    trees = [cKDTree(c) for c in coords]
    for i in range(len(props)):
        gap_rows = np.maximum(0, np.maximum(bbox[i, 0] - bbox[i + 1:, 2], bbox[i + 1:, 0] - bbox[i, 2]))
        gap_cols = np.maximum(0, np.maximum(bbox[i, 1] - bbox[i + 1:, 3], bbox[i + 1:, 1] - bbox[i, 3]))
        bbox_gap = np.hypot(gap_rows, gap_cols)
        dist[i, i + 1:] = dist[i + 1:, i] = np.maximum(dist[i, i + 1:], bbox_gap)
        for offset in np.where(bbox_gap <= max_dist)[0]:
            j = i + 1 + offset
            # nearest pixel centre pairs -> gap between the pixel squares
            d, idx = trees[i].query(coords[j])
            delta = np.abs(coords[j] - trees[i].data[idx])
            gap = np.hypot(np.maximum(0, delta[:, 0] - pixel), np.maximum(0, delta[:, 1] - pixel)).min()
            dist[i, j] = dist[j, i] = gap
    np.fill_diagonal(dist, 0.0)
    return pd.DataFrame(np.round(dist, 1), index=ids, columns=ids)

def patch_polygons(labeled, transform, crs, patches):
    """Patch outlines as a GeoDataFrame with the patch metrics attached."""
    polys = [{'patch_id': int(val), 'geometry': shapely_shape(geom)}
             for geom, val in rio_shapes(labeled.astype(np.int32), transform=transform) if val != 0]
    return gpd.GeoDataFrame(polys, crs=crs).merge(patches, on='patch_id', how='left')


# ==========================================================================
# Connectivity metrics
# ==========================================================================

def build_graph(patches, dist, max_dist):
    """Graph with a node per patch and an edge between patches whose gap is <= max_dist."""
    ids = patches['patch_id'].tolist()
    graph = nx.Graph()
    graph.add_nodes_from(ids)
    d = dist.values
    rows, cols = np.where(np.triu(d <= max_dist, k=1))
    for r, c in zip(rows, cols):
        graph.add_edge(ids[r], ids[c], weight=d[r, c])
    return graph

def calc_iic(areas, graph, landscape_ha):
    """Integral Index of Connectivity (Pascual-Hortal & Saura 2006).

    IIC = sum over all patch pairs (i, j, including i = j) of a_i * a_j / (1 + nl_ij) / A_L^2, with nl_ij the number of
    links in the shortest path (unreachable pairs contribute 0). A_L is the total landscape area (not only the habitat
    area), so values are comparable between years.
    """
    if landscape_ha <= 0 or graph.number_of_nodes() == 0:
        return 0.0
    a = areas.to_dict()
    total = 0.0
    for source, lengths in nx.all_pairs_shortest_path_length(graph):
        for target, links in lengths.items():
            total += a[source] * a[target] / (1 + links)
    return total / landscape_ha ** 2

def calc_iic_without(areas, graph, remove, landscape_ha):
    """IIC after removing patches; A_L is unchanged so it is comparable with the full-landscape IIC."""
    reduced = graph.copy()
    reduced.remove_nodes_from(remove)
    return calc_iic(areas, reduced, landscape_ha)

def effective_mesh_size(areas, landscape_ha):
    """Effective mesh size (Jaeger 2000), mEff = sum(a_i^2) / A_L in ha, and the splitting index A_L^2 / sum(a_i^2)."""
    sum_a2 = float((areas ** 2).sum())
    if landscape_ha <= 0 or sum_a2 == 0:
        return 0.0, np.nan
    return sum_a2 / landscape_ha, landscape_ha ** 2 / sum_a2

def nearest_neighbour_gaps(dist):
    """Gap (m) from each patch to its nearest other patch (NaN if there is only one patch)."""
    if len(dist) < 2:
        return np.array([np.nan])
    d = dist.values.astype(float)
    np.fill_diagonal(d, np.inf)
    return d.min(axis=1)


# ==========================================================================
# Exports
# ==========================================================================

def graph_geodataframes(patches, graph, crs):
    """Patch centroids (points) and graph edges (lines) as GeoDataFrames."""
    points = gpd.GeoDataFrame(patches.copy(), geometry=gpd.points_from_xy(patches['centroid_x'], patches['centroid_y']),
                              crs=crs)
    xy = patches.set_index('patch_id')[['centroid_x', 'centroid_y']]
    records = [{'from_patch': u, 'to_patch': v, 'distance_m': data['weight'],
                'geometry': LineString([tuple(xy.loc[u]), tuple(xy.loc[v])])}
               for u, v, data in graph.edges(data=True)]
    edges = gpd.GeoDataFrame(records, geometry='geometry', crs=crs) if records else None
    return points, edges


# ==========================================================================
# Plots
# ==========================================================================

def plot_patch_comparison(site_data, summaries, year_labels, habitat_label, out_path, dpi=150):
    """Side-by-side maps of the site's habitat patches (each patch its own colour), one panel per year."""
    fig, axes = plt.subplots(1, len(year_labels), figsize=(7 * len(year_labels), 6), facecolor='white')
    cmap = plt.colormaps['tab20']
    for ax, year in zip(np.atleast_1d(axes), year_labels):
        d = site_data[year]
        rgb = np.ones(d['labeled'].shape + (3,))          # white = outside the site
        rgb[d['valid']] = 0.88                              # grey = non-habitat
        for pid in range(1, d['n_patches'] + 1):
            rgb[d['labeled'] == pid] = cmap(pid % 20 / 20)[:3]
        ax.imshow(rgb, interpolation='nearest')
        s = summaries[year]
        ax.set_title(f"{year}\n{s['habitat_ha']} ha {habitat_label.lower()}  -  {s['n_patches']} patches\n"
                     f"largest patch {s['largest_patch_ha']} ha  -  IIC = {s['IIC']:.3f}", fontsize=11,
                     fontweight='bold')
        ax.axis('off')
    fig.legend(handles=[Patch(facecolor=cmap(0.15)[:3], label=f"{habitat_label} patch (each colour = 1 patch)"),
                        Patch(facecolor='#e0e0e0', label=f"Non-{habitat_label.lower()}")],
               loc='lower center', ncol=2, fontsize=10, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle(f"{habitat_label} patches within the site", fontsize=13, fontweight='bold', y=1.01)
    fig.tight_layout(pad=1.5)
    fig.savefig(out_path, dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)

def plot_landscape_map(patches, graph, site_ids, site_outline, title, habitat_label, out_path, dpi=150):
    """Landscape map: on-site patches (orange) vs off-site patches (grey) and the links within the dispersal distance."""
    fig, ax = plt.subplots(figsize=(10, 10), facecolor='white')
    ax.set_facecolor('#f5f5f5')
    xy = patches.set_index('patch_id')[['centroid_x', 'centroid_y']]
    for u, v in graph.edges():
        ax.plot([xy.loc[u, 'centroid_x'], xy.loc[v, 'centroid_x']], [xy.loc[u, 'centroid_y'], xy.loc[v, 'centroid_y']],
                color='#b0b0b0', alpha=0.3, lw=0.5, zorder=1)
    off = patches[~patches['patch_id'].isin(site_ids)]
    on = patches[patches['patch_id'].isin(site_ids)]
    if len(off):
        ax.scatter(off['centroid_x'], off['centroid_y'], s=off['area_ha'].clip(upper=50) * 3, c='#cccccc',
                   edgecolors='#999999', linewidths=0.3, alpha=0.6, zorder=2, label=f"Off-site {habitat_label.lower()}")
    if len(on):
        ax.scatter(on['centroid_x'], on['centroid_y'], s=on['area_ha'].clip(upper=50) * 6, c='#e8760a',
                   edgecolors='#8b4513', linewidths=0.8, alpha=0.9, zorder=3, label=f"Site {habitat_label.lower()}")
    site_outline.boundary.plot(ax=ax, color='#e8760a', linewidth=2, linestyle='--', zorder=4)
    ax.plot([], [], color='#e8760a', lw=2, ls='--', label='Site (incl. buffer)')
    ax.set_aspect('equal')
    ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.axis('off')
    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)


# ==========================================================================
# Productivity (TPROD)
# ==========================================================================

def gdf_bounds_wgs84(gdfs):
    """Bounding box [minx, miny, maxx, maxy] in EPSG:4326 covering all the GeoDataFrames in gdfs."""
    b = np.array([g.to_crs(4326).total_bounds for g in gdfs])
    return [float(b[:, 0].min()), float(b[:, 1].min()), float(b[:, 2].max()), float(b[:, 3].max())]


def select_tprod_results(results, year):
    """Keep the HDA search results that are the season-1 TPROD tile of the given year, as {tile file name: result}.

    The name is looked for in the result id and in its properties (title / name), as WEkEO does not guarantee which one
    holds the file name. Season 1 only, as in the demo tiles (VPP_{year}_S2_T??????-010m_V???_s1_TPROD.tif).
    """
    pattern = re.compile(rf"VPP_{year}_S2_T\w+-010m_V\d+_s1_TPROD(\.tif)?", re.IGNORECASE)
    selected = {}
    for result in results:
        props = result.get("properties", {}) or {}
        for text in (result.get("id"), props.get("title"), props.get("name"), props.get("location")):
            match = pattern.search(str(text or ""))
            if match:
                selected[match.group(0).rsplit('.', 1)[0] + ".tif"] = result
                break
    return selected


def download_tprod_tiles(gdfs, years, tprod_dir, dataset_id="EO:EEA:DAT:CLMS_HRVPP_VPP"):
    """Download the Copernicus HR-VPP TPROD tiles that intersect the GeoDataFrames in gdfs, for each year, to tprod_dir.

    Uses the WEkEO HDA service (package 'hda'); credentials come from ~/.hdarc or the HDA_USER / HDA_PASSWORD
    environment variables. Tiles already in tprod_dir are skipped. Returns the list of tile files now in tprod_dir
    for these years.
    """
    import shutil
    import zipfile
    from hda import Client

    tprod_dir = Path(tprod_dir)
    tprod_dir.mkdir(parents=True, exist_ok=True)
    bbox = gdf_bounds_wgs84(gdfs)
    client = Client()
    tiles = []
    for year in years:
        query = {"dataset_id": dataset_id, "productType": "TPROD", "bbox": bbox,
                 "startdate": f"{year}-01-01T00:00:00.000Z", "enddate": f"{year}-12-31T23:59:59.999Z",
                 "itemsPerPage": 200, "startIndex": 0}
        found = client.search(query)
        wanted = select_tprod_results(found.results, year)
        print(f"\n{year}: {len(found.results)} search results, {len(wanted)} are season-1 TPROD tiles: {sorted(wanted)}")
        if not wanted:
            sample = [str(r.get("id")) for r in found.results[:5]]
            raise RuntimeError(f"No TPROD tile found for {year}. First result ids returned by WEkEO: {sample}")
        for name, result in wanted.items():
            if (tprod_dir / name).exists():
                print(f"  {name}: already downloaded, skipped")
            else:
                print(f"  {name}: downloading ...")
                tmp = tprod_dir / "_download"
                tmp.mkdir(exist_ok=True)
                found[found.results.index(result)].download(download_dir=str(tmp))
                for zipped in tmp.glob("*.zip"):
                    with zipfile.ZipFile(zipped) as z:
                        z.extractall(tmp)
                    zipped.unlink()
                for tif in tmp.rglob("*TPROD*.tif"):
                    shutil.move(str(tif), str(tprod_dir / tif.name))
                shutil.rmtree(tmp, ignore_errors=True)
                if not (tprod_dir / name).exists():
                    raise RuntimeError(f"{name} was not found after the download; check {tprod_dir}")
            tiles.append(tprod_dir / name)
    return tiles

def find_tprod_tiles(tprod_dir, year, gdf):
    """TPROD tiles (VPP_{year}_S2_*_TPROD.tif) in tprod_dir whose extent intersects the geometry in gdf."""
    tiles = sorted(Path(tprod_dir).glob(f"VPP_{year}_S2_*_TPROD.tif"))
    if not tiles:
        raise FileNotFoundError(f"No TPROD tiles for {year} found in {tprod_dir}")
    selected = []
    for tile in tiles:
        with rasterio.open(tile) as src:
            if box(*src.bounds).intersects(gdf.to_crs(src.crs).geometry.union_all()):
                selected.append(tile)
    if not selected:
        raise ValueError(f"None of the {year} TPROD tiles in {tprod_dir} intersects the area")
    return selected


def tprod_on_grid(tile_paths, transform, shape, crs, scale):
    """Resample TPROD tiles onto a target grid and return a float32 array (NaN = no data).

    The tile nodata value (65535 for Copernicus VPP) is excluded; 0 is a valid value. Where tiles overlap, the valid
    values are averaged. Nearest neighbour resampling avoids mixing values with nodata. The scale factor is applied.
    """
    total = np.zeros(shape, dtype=np.float64)
    count = np.zeros(shape, dtype=np.int32)
    for tile in tile_paths:
        with rasterio.open(tile) as src:
            resampled = np.full(shape, np.nan, dtype=np.float32)
            reproject(source=rasterio.band(src, 1), destination=resampled, src_nodata=src.nodata,
                      dst_transform=transform, dst_crs=crs, dst_nodata=np.nan, resampling=Resampling.nearest)
        valid = np.isfinite(resampled)
        total[valid] += resampled[valid]
        count[valid] += 1
    out = np.full(shape, np.nan, dtype=np.float32)
    has_data = count > 0
    out[has_data] = (total[has_data] / count[has_data] * scale).astype(np.float32)
    return out


def tprod_statistics(tprod, habitat_mask, pixel_area_ha):
    """Statistics of the TPROD values (NaN = no data) on the habitat pixels, as a dict."""
    values = tprod[habitat_mask & np.isfinite(tprod)].astype(np.float64)
    n_habitat = int(habitat_mask.sum())
    stats = dict(area_ha=n_habitat * pixel_area_ha, n_pixels=n_habitat, n_pixels_with_tprod=len(values))
    if len(values) == 0:
        return {**stats, **{k: np.nan for k in ('mean_tprod', 'median_tprod', 'std_tprod', 'min_tprod', 'max_tprod',
                                                'q25_tprod', 'q75_tprod', 'total_tprod')}}
    return {**stats, 'mean_tprod': values.mean(), 'median_tprod': np.median(values), 'std_tprod': values.std(),
            'min_tprod': values.min(), 'max_tprod': values.max(), 'q25_tprod': np.percentile(values, 25),
            'q75_tprod': np.percentile(values, 75), 'total_tprod': values.sum()}


def plot_tprod_comparison(stats, areas, codes, years, colours, output_path):
    """Grouped bars of the mean pixel TPROD per habitat code: one panel per year, one bar per area."""
    fig, axes = plt.subplots(1, len(years), figsize=(6 * len(years), 5), sharey=True, squeeze=False)
    width = 0.8 / len(areas)
    x = np.arange(len(codes))
    for ax, year in zip(axes[0], years):
        for i, area in enumerate(areas):
            sub = stats[(stats['year'] == year) & (stats['area'] == area)].set_index('habitat_code')['mean_tprod']
            means = [sub.get(code, np.nan) for code in codes]
            ax.bar(x + (i - (len(areas) - 1) / 2) * width, np.nan_to_num(means), width, label=area,
                   color=colours[i % len(colours)])
        ax.set_title(str(year), fontsize=16, fontweight='bold')
        ax.set_xlabel('EUNIS codes')
        ax.set_xticks(x)
        ax.set_xticklabels(codes)
        ax.set_ylim(0, None)
        ax.grid(axis='y', alpha=0.3)
        ax.set_axisbelow(True)
    axes[0][0].set_ylabel('Mean pixel total primary productivity')
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper right', bbox_to_anchor=(0.98, 0.95), frameon=True, edgecolor='gray')
    fig.tight_layout(rect=[0, 0, 0.9, 1])
    fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
