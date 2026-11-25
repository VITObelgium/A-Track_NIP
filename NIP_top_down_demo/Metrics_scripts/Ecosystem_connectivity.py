"""DEMONSTRATION ONLY: tailored to one site/case, experimental input maps. See LIMITATIONS_AND_CAVEATS.md before use.

Ecosystem connectivity (step 1.4, Assessing habitat connectivity): connectivity of the priority habitat patches
(grassland by default) as an ecosystem condition indicator, for the opening and closing year.

  1. Site connectivity (the site polygon): number and size of patches, internal connectivity (IIC, Integral Index of
     Connectivity; mean nearest neighbour distance) and effective mesh size.
  2. Landscape role (the site plus LANDSCAPE_RADIUS_M): the site's importance as a stepping stone (dIIC: the % drop in
     landscape IIC if the site's patches were removed; betweenness) and the habitat reachable from the site.
  3. The change between the opening and closing year.

In the document the landscape is 10 km; for size constraints only the 500 m buffer raster is provided, so the
demo landscape is 500 m (set LANDSCAPE_RADIUS_M and larger maps to widen it).

IIC uses the total area as the denominator (comparable between years). Patches are 4-connected and gaps are measured
edge to edge. Dispersal distances (100, 200 and 500 m by default) are run as a sensitivity analysis, since species
differ in dispersal capability; the headline distance is the main figure. The same metrics can also be calculated in
FRAGSTATS.

All settings (site polygon, rasters, LUT, habitat, dispersal distances, landscape radius, output folder) are in
EA_setup.py. The script clips the rasters itself, so Ecosystem_extent.py does not need to be run first. Output (in
connectivity_output_dir): summary csv, text report, patch/graph GeoPackages, patch detail csv and maps.
"""
# %% Imports - run this block first when running block by block
import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from rasterio.features import rasterize

from EA_setup import (
    connectivity_output_dir, site_polygon_path, site_raster_level, raster_opening_path, raster_closing_path, year_labels, habitat_label,
    habitat_codes, habitat_code_level, MIN_AREA_HA, DISPERSAL_THRESHOLDS, HEADLINE_THRESHOLD, LANDSCAPE_RADIUS_M,
    lut_path, lut_separator, lut_value_column, lut_code_column, lut_name_column, lut_level_column,
)
from EA_utils import (
    clip_raster_to_geometry, load_lut,
    habitat_raster_values, buffer_geodataframe, check_landscape_coverage, extract_patches, patch_table,
    edge_distance_matrix, patch_polygons, build_graph, calc_iic, calc_iic_without, effective_mesh_size,
    nearest_neighbour_gaps, graph_geodataframes, plot_patch_comparison, plot_landscape_map,
)

# %%
# ==========================================================================
# STEP 1: Habitat raster values, site polygon and rasters
# ==========================================================================
# Reads the LUT, the habitat raster values to analyse (habitat_codes), the site polygon and the landscape (site polygon +
# LANDSCAPE_RADIUS_M), and clips the maps. Creates: raster_values, gdf_site, gdf_landscape and data (site and landscape
# windows per year). Warns if the rasters do not cover the full landscape.

if raster_closing_path is None:
    raise ValueError("Connectivity change needs both an opening and a closing raster")
if HEADLINE_THRESHOLD not in DISPERSAL_THRESHOLDS:
    raise ValueError("HEADLINE_THRESHOLD must be one of DISPERSAL_THRESHOLDS")
connectivity_output_dir.mkdir(parents=True, exist_ok=True)
raster_paths = (raster_opening_path, raster_closing_path)

lut3, _ = load_lut(lut_path, lut_separator, lut_value_column, lut_code_column, lut_name_column, lut_level_column,
                  map_level=site_raster_level)
raster_values = habitat_raster_values(lut3, habitat_codes, habitat_code_level)
print(f"Raster values for {habitat_label} (level {habitat_code_level} {habitat_codes}): {raster_values}")

gdf_site = gpd.read_file(site_polygon_path)
if gdf_site.crs is None:
    raise ValueError("Site polygon has no CRS defined")
gdf_landscape = buffer_geodataframe(gdf_site, LANDSCAPE_RADIUS_M)

for path in raster_paths:
    check_landscape_coverage(gdf_landscape, path, LANDSCAPE_RADIUS_M)

# Clip the site and landscape windows per year (masked arrays: outside the polygon / nodata are masked)
data = {}
for year, raster_path in zip(year_labels, raster_paths):
    site_arr, site_profile = clip_raster_to_geometry(raster_path, gdf_site)
    land_arr, land_profile = clip_raster_to_geometry(raster_path, gdf_landscape)
    data[year] = dict(
        site_arr=site_arr, site_tf=site_profile['transform'], site_crs=site_profile['crs'],
        land_arr=land_arr, land_tf=land_profile['transform'], land_crs=land_profile['crs'],
    )
    print(f"{year}: site window {site_arr.shape}, landscape window {land_arr.shape}")

# %%
# ==========================================================================
# STEP 2: Internal connectivity (site)
# ==========================================================================
# Site analysis per year: extracts habitat patches (min. area MIN_AREA_HA), computes edge-to-edge distances and, for each
# dispersal distance, the IIC, number of components and other metrics. Creates: site_results, site_data. Prints the
# results per year and distance and saves the site patches as GeoPackage.
# Patches and the distance matrix are computed once per year; only the graph changes with the dispersal distance.

site_results = {}   # (year, threshold) -> dict
site_data = {}      # year -> arrays for the plots

for year in year_labels:
    d = data[year]
    valid = ~np.ma.getmaskarray(d['site_arr'])
    habitat = np.isin(np.ma.getdata(d['site_arr']), raster_values) & valid
    pixel_m2 = abs(d['site_tf'].a * d['site_tf'].e)
    site_ha = valid.sum() * pixel_m2 / 10_000
    habitat_ha = habitat.sum() * pixel_m2 / 10_000

    labeled, n_patches = extract_patches(habitat.astype(np.uint8), pixel_m2, MIN_AREA_HA)
    site_data[year] = dict(labeled=labeled, valid=valid, n_patches=n_patches)
    print(f"\n{year}: {habitat_ha:.1f} ha {habitat_label.lower()} ({100 * habitat_ha / site_ha:.0f}% of the site) "
          f"-> {n_patches} patches")

    base = dict(year=year, habitat_ha=round(habitat_ha, 2), site_ha=round(site_ha, 2), n_patches=n_patches)
    if n_patches == 0:
        for max_d in DISPERSAL_THRESHOLDS:
            site_results[(year, max_d)] = dict(**base, threshold_m=max_d, n_components=0, IIC=0.0, mEff_ha=0.0,
                                               splitting_index=np.nan, mean_nn_m=np.nan, mean_patch_ha=0.0,
                                               largest_patch_ha=0.0)
        continue

    patches = patch_table(labeled, d['site_tf'], pixel_m2)
    dist = edge_distance_matrix(labeled, d['site_tf'], patches, max(DISPERSAL_THRESHOLDS))
    areas = patches.set_index('patch_id')['area_ha']
    mean_nn = float(np.nanmean(nearest_neighbour_gaps(dist)))
    meff, splitting = effective_mesh_size(areas, site_ha)

    for max_d in DISPERSAL_THRESHOLDS:
        graph = build_graph(patches, dist, max_d)
        iic = calc_iic(areas, graph, site_ha)
        n_comp = nx.number_connected_components(graph)
        site_results[(year, max_d)] = dict(
            **base, threshold_m=max_d, n_components=n_comp, IIC=round(iic, 6), mEff_ha=round(meff, 3),
            splitting_index=round(splitting, 3), mean_nn_m=round(mean_nn, 1),
            mean_patch_ha=round(areas.mean(), 3), largest_patch_ha=round(areas.max(), 3))
        star = " *" if max_d == HEADLINE_THRESHOLD else ""
        print(f"  @{max_d:>4d} m: IIC = {iic:.4f}  |  {n_comp} component(s){star}")

    gdf_patches = patch_polygons(labeled, d['site_tf'], d['site_crs'], patches)
    gpkg_path = connectivity_output_dir / f"connectivity_site_patches_{year}_landscape{LANDSCAPE_RADIUS_M}m.gpkg"
    gdf_patches.to_file(gpkg_path, driver="GPKG")
    print(f"  Saved: {gpkg_path}")

# %%
# ==========================================================================
# STEP 3: Landscape role of the site
# ==========================================================================
# Landscape analysis per year: patches in the site + radius, which of them are on the site, and per dispersal distance the
# IIC without the site's patches (dIIC), betweenness and reachable habitat. Creates: landscape_results. Saves the patch
# detail (csv), the graph (GeoPackage) and a map for the headline distance.
# A patch counts as 'on site' if it overlaps the site polygon (not only if its centroid is inside).

landscape_results = {}   # (year, threshold) -> dict

for year in year_labels:
    d = data[year]
    valid = ~np.ma.getmaskarray(d['land_arr'])
    habitat = np.isin(np.ma.getdata(d['land_arr']), raster_values) & valid
    pixel_m2 = abs(d['land_tf'].a * d['land_tf'].e)
    landscape_ha = valid.sum() * pixel_m2 / 10_000

    labeled, n_patches = extract_patches(habitat.astype(np.uint8), pixel_m2, MIN_AREA_HA)
    patches = patch_table(labeled, d['land_tf'], pixel_m2)

    site_geoms = gdf_site.to_crs(d['land_crs']).geometry
    site_mask = rasterize([(g, 1) for g in site_geoms], out_shape=labeled.shape, transform=d['land_tf'],
                          fill=0, dtype='uint8').astype(bool)
    site_ids = set(np.unique(labeled[site_mask & (labeled > 0)]).tolist())
    off_ids = set(patches['patch_id']) - site_ids
    print(f"\n{year}: {len(site_ids)} site patches among {n_patches} patches in the landscape "
          f"({landscape_ha:.0f} ha)")

    if not site_ids:
        print("  No site patches in the landscape graph")
        for max_d in DISPERSAL_THRESHOLDS:
            landscape_results[(year, max_d)] = dict(
                n_nearby=n_patches, n_on_site=0, landscape_ha=round(landscape_ha, 1), IIC_landscape=np.nan,
                IIC_without=np.nan, site_dIIC_pct=0.0, bc_site=np.nan, bc_all=np.nan, nearest_offsite_min_m=np.nan,
                nearest_offsite_mean_m=np.nan, reachable_ha=0.0, reachable_offsite_ha=0.0, n_landscape_networks=0)
        continue

    dist = edge_distance_matrix(labeled, d['land_tf'], patches, max(DISPERSAL_THRESHOLDS))
    areas = patches.set_index('patch_id')['area_ha']
    if off_ids:
        gaps = dist.loc[sorted(site_ids), sorted(off_ids)].min(axis=1)
        nn_min, nn_mean = round(float(gaps.min()), 0), round(float(gaps.mean()), 0)
    else:
        nn_min = nn_mean = np.nan

    for max_d in DISPERSAL_THRESHOLDS:
        graph = build_graph(patches, dist, max_d)
        iic = calc_iic(areas, graph, landscape_ha)
        iic_without = calc_iic_without(areas, graph, site_ids, landscape_ha)
        diic = 100 * (iic - iic_without) / iic if iic > 0 else 0.0

        bc = nx.betweenness_centrality(graph, normalized=False)
        # Habitat in the networks (connected components) that the site's patches belong to, and the number of separate networks the site takes part in
        components = {frozenset(nx.node_connected_component(graph, pid)) for pid in site_ids}
        reachable = set().union(*components)
        reachable_ha = float(areas.loc[sorted(reachable)].sum())
        reachable_off_ha = float(areas.loc[sorted(reachable - site_ids)].sum())

        landscape_results[(year, max_d)] = dict(
            n_nearby=n_patches, n_on_site=len(site_ids), landscape_ha=round(landscape_ha, 1),
            IIC_landscape=round(iic, 6), IIC_without=round(iic_without, 6), site_dIIC_pct=round(diic, 4),
            bc_site=round(float(np.mean([bc[p] for p in site_ids])), 6),
            bc_all=round(float(np.mean(list(bc.values()))), 6),
            nearest_offsite_min_m=nn_min, nearest_offsite_mean_m=nn_mean,
            reachable_ha=round(reachable_ha, 2), reachable_offsite_ha=round(reachable_off_ha, 2),
            n_landscape_networks=len(components))
        star = " *" if max_d == HEADLINE_THRESHOLD else ""
        print(f"  @{max_d:>4d} m: dIIC = {diic:.1f}%  |  reachable {reachable_ha:.0f} ha  |  "
              f"{len(components)} network(s){star}")

    # Detail, GIS layers and map for the headline distance only
    graph = build_graph(patches, dist, HEADLINE_THRESHOLD)
    bc = nx.betweenness_centrality(graph, normalized=False)
    detail = patches[patches['patch_id'].isin(site_ids)].copy()
    detail['betweenness'] = detail['patch_id'].map(bc)
    detail['bc_x_area'] = detail['betweenness'] * detail['area_ha']
    detail['nearest_offsite_m'] = detail['patch_id'].map(gaps) if off_ids else np.nan
    detail_path = connectivity_output_dir / f"connectivity_site_patch_detail_{year}_landscape{LANDSCAPE_RADIUS_M}m.csv"
    detail.to_csv(detail_path, index=False, float_format="%.4f")

    points, edges = graph_geodataframes(
        patches.assign(on_site=patches['patch_id'].isin(site_ids), betweenness=patches['patch_id'].map(bc)),
        graph, d['land_crs'])
    gpkg_path = connectivity_output_dir / f"connectivity_landscape_graph_{year}_landscape{LANDSCAPE_RADIUS_M}m.gpkg"
    points.to_file(gpkg_path, layer="patches", driver="GPKG")
    if edges is not None:
        edges.to_file(gpkg_path, layer="edges", driver="GPKG")
    print(f"  Saved: {detail_path}\n  Saved: {gpkg_path}")

    lres = landscape_results[(year, HEADLINE_THRESHOLD)]
    title = (f"Landscape connectivity - {year} (dispersal {HEADLINE_THRESHOLD} m)\n"
             f"{lres['n_on_site']} site patches among {lres['n_nearby']} nearby  -  dIIC = "
             f"{lres['site_dIIC_pct']:.1f}%  -  reachable {lres['reachable_ha']:.0f} ha")
    map_path = connectivity_output_dir / f"connectivity_landscape_map_{year}_landscape{LANDSCAPE_RADIUS_M}m.png"
    plot_landscape_map(patches, graph, site_ids, gdf_site.to_crs(d['land_crs']), title, habitat_label, map_path)
    print(f"  Saved: {map_path}")

# %%
# ==========================================================================
# STEP 4: Site patch map comparison
# ==========================================================================
# Map comparing the site's habitat patches in the opening and closing year (headline dispersal distance).

headline_site = {year: site_results[(year, HEADLINE_THRESHOLD)] for year in year_labels}
map_path = connectivity_output_dir / f"connectivity_site_comparison_landscape{LANDSCAPE_RADIUS_M}m.png"
plot_patch_comparison(site_data, headline_site, year_labels, habitat_label, map_path)
print(f"\nSaved: {map_path}")

# %%
# ==========================================================================
# STEP 5: Summary
# ==========================================================================
# Prints and saves the text report and the summary csv (site and landscape metrics, all distances, both years).

y0, y1 = year_labels
H = HEADLINE_THRESHOLD
arrow = lambda a, b: "up" if b > a else ("down" if b < a else "unchanged")
s0, s1 = site_results[(y0, H)], site_results[(y1, H)]
l0, l1 = landscape_results[(y0, H)], landscape_results[(y1, H)]

lines = []
def out(text=""):
    lines.append(text)
    print(text)

out(f"\n{'=' * 64}")
out(f"  {habitat_label.upper()} CONNECTIVITY - {y0} vs {y1} (landscape radius {LANDSCAPE_RADIUS_M} m, dispersal {H} m)")
out(f"{'=' * 64}")
out(f"\n  1. Site: {s1['habitat_ha']} ha {habitat_label.lower()} in {s1['n_patches']} patches - IIC {s1['IIC']:.3f} "
    f"({arrow(s0['IIC'], s1['IIC'])} from {s0['IIC']:.3f} in {y0}); effective mesh size {s1['mEff_ha']:.2f} ha "
    f"(from {s0['mEff_ha']:.2f} ha)")
out(f"  2. Landscape role: removing the site's patches would reduce landscape connectivity by "
    f"{l1['site_dIIC_pct']:.1f}% ({arrow(l0['site_dIIC_pct'], l1['site_dIIC_pct'])} from "
    f"{l0['site_dIIC_pct']:.1f}% in {y0})")
out(f"  3. Network: {l1['reachable_ha']:.0f} ha of {habitat_label.lower()} is in the connected network(s) of the site "
    f"({arrow(l0['reachable_ha'], l1['reachable_ha'])} from {l0['reachable_ha']:.0f} ha in {y0})")

out(f"\n  Sensitivity to the dispersal distance (headline {H} m marked *)")
out(f"  {'-' * 62}")
out(f"  {'Distance':>10s}  {'IIC (site)':>18s}  {'dIIC %':>14s}  {'Reachable ha':>16s}")
for t in DISPERSAL_THRESHOLDS:
    a0, a1 = site_results[(y0, t)], site_results[(y1, t)]
    b0, b1 = landscape_results[(y0, t)], landscape_results[(y1, t)]
    star = " *" if t == H else "  "
    out(f"  {t:>7d} m{star}  {a0['IIC']:.4f} -> {a1['IIC']:.4f}  "
        f"{b0['site_dIIC_pct']:>5.1f} -> {b1['site_dIIC_pct']:<5.1f}  {b0['reachable_ha']:>6.0f} -> {b1['reachable_ha']:<6.0f}")

direction = {np.sign(site_results[(y1, t)]['IIC'] - site_results[(y0, t)]['IIC']) for t in DISPERSAL_THRESHOLDS}
if direction == {1.0}:
    out(f"\n  Site IIC increased at all dispersal distances")
elif direction == {-1.0}:
    out(f"\n  Site IIC decreased at all dispersal distances")
else:
    out(f"\n  Site IIC does not change in the same direction at all dispersal distances")

report_path = connectivity_output_dir / f"connectivity_report_landscape{LANDSCAPE_RADIUS_M}m.txt"
report_path.write_text("\n".join(lines), encoding="utf-8")

rows = [{**site_results[(y, t)], **{f"landscape_{k}": v for k, v in landscape_results[(y, t)].items()}}
        for y in year_labels for t in DISPERSAL_THRESHOLDS]
summary_path = connectivity_output_dir / f"connectivity_summary_landscape{LANDSCAPE_RADIUS_M}m.csv"
pd.DataFrame(rows).to_csv(summary_path, index=False, float_format="%.6f")
print(f"\nSaved: {report_path}\nSaved: {summary_path}")
