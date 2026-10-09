"""
get_lawn_data.py - download and clip the base layers for one small State College area.

Outputs (all in one CRS, EPSG:26918 / UTM 18N, meters) to ./data/:
  naip.tif           NAIP aerial imagery (4 bands: R, G, B, NIR), ~0.6 m
  chesapeake_lc.tif  Chesapeake Bay Program 1 m land cover (tree canopy etc.)  [optional]
  buildings.gpkg     Overture Maps building footprints
  parcels.gpkg       County parcels from an ArcGIS REST layer                  [optional]

Usage:
  python get_lawn_data.py                       # default bbox
  python get_lawn_data.py --bbox -77.875 40.785 -77.860 40.795
  python get_lawn_data.py --parcels-url "https://.../FeatureServer/0"

All sources are free and need no API key (Planetary Computer signs URLs anonymously).
"""
import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import planetary_computer
import pystac_client
import requests
import rioxarray  # noqa: F401  (registers .rio accessor)
from rioxarray.merge import merge_arrays
from shapely.geometry import box

TARGET_CRS = "EPSG:26918"  # NAD83 / UTM zone 18N - State College is in zone 18
DEFAULT_BBOX = (-77.875, 40.785, -77.860, 40.795)  # lon/lat, ~1.3 km x 1.1 km, downtown-ish State College
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
OUT = Path("data")


def log(msg):
    print(f"[lawn] {msg}", flush=True)


def stac_client():
    return pystac_client.Client.open(PC_STAC, modifier=planetary_computer.sign_inplace)


def fetch_raster(collection, bbox, asset_key, out_path, newest=True, resolution=None):
    """Search a Planetary Computer collection, clip every intersecting tile to bbox,
    mosaic, reproject to TARGET_CRS, and write a COG-style GeoTIFF."""
    items = list(stac_client().search(collections=[collection], bbox=bbox).items())
    if not items:
        raise RuntimeError(f"no {collection} items found for bbox {bbox}")
    # keep only the most recent acquisition year so we don't mix seasons/years
    years = sorted({(it.datetime or it.properties.get("start_datetime", "")).__str__()[:4] for it in items})
    keep = years[-1] if newest else years[0]
    items = [it for it in items if str(it.datetime or it.properties.get("start_datetime", ""))[:4] == keep]
    log(f"{collection}: {len(items)} tile(s) from {keep}")

    pieces = []
    for it in items:
        href = it.assets[asset_key].href
        da = rioxarray.open_rasterio(href, masked=False)
        try:
            da = da.rio.clip_box(*bbox, crs="EPSG:4326")
        except Exception:  # tile touches bbox only at an edge
            continue
        pieces.append(da)
    if not pieces:
        raise RuntimeError(f"{collection}: tiles found but none overlap bbox after clipping")
    mosaic = merge_arrays(pieces) if len(pieces) > 1 else pieces[0]
    kw = {"resolution": resolution} if resolution else {}
    mosaic = mosaic.rio.reproject(TARGET_CRS, **kw)
    mosaic.rio.to_raster(out_path, compress="deflate", tiled=True)
    log(f"wrote {out_path}  shape={tuple(mosaic.shape)}  res={mosaic.rio.resolution()}")
    return out_path


def fetch_buildings(bbox, out_path):
    from overturemaps import core

    reader = core.record_batch_reader("building", bbox)
    if reader is None:
        raise RuntimeError("overturemaps returned no reader")
    table = reader.read_all()
    df = table.to_pandas()
    if df.empty:
        raise RuntimeError("no Overture buildings in bbox")
    from shapely import wkb

    geom = gpd.GeoSeries(df["geometry"].apply(wkb.loads), crs="EPSG:4326")
    gdf = gpd.GeoDataFrame(df[["id"]].copy(), geometry=geom).to_crs(TARGET_CRS)
    gdf.to_file(out_path, driver="GPKG")
    log(f"wrote {out_path}  {len(gdf)} buildings")
    return out_path


def fetch_parcels(url, bbox, out_path):
    """Query an ArcGIS REST FeatureServer/MapServer layer for features in bbox."""
    params = {
        "where": "1=1",
        "geometry": ",".join(map(str, bbox)),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "outSR": 4326,
        "f": "geojson",
        "resultRecordCount": 2000,
    }
    feats, offset = [], 0
    while True:
        params["resultOffset"] = offset
        r = requests.get(url.rstrip("/") + "/query", params=params, timeout=60)
        r.raise_for_status()
        batch = r.json().get("features", [])
        feats += batch
        if len(batch) < params["resultRecordCount"]:
            break
        offset += len(batch)
    if not feats:
        raise RuntimeError("parcel service returned 0 features for bbox")
    gdf = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326").to_crs(TARGET_CRS)
    gdf.to_file(out_path, driver="GPKG")
    log(f"wrote {out_path}  {len(gdf)} parcels")
    return out_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", nargs=4, type=float, default=DEFAULT_BBOX,
                    metavar=("WEST", "SOUTH", "EAST", "NORTH"), help="lon/lat bounding box")
    ap.add_argument("--parcels-url", default=None,
                    help="ArcGIS REST layer URL for county parcels (skipped if omitted)")
    ap.add_argument("--skip-chesapeake", action="store_true")
    args = ap.parse_args()
    bbox = tuple(args.bbox)
    OUT.mkdir(exist_ok=True)
    gpd.GeoDataFrame(geometry=[box(*bbox)], crs="EPSG:4326").to_crs(TARGET_CRS).to_file(OUT / "aoi.gpkg")

    failures = []
    steps = [
        ("naip", lambda: fetch_raster("naip", bbox, "image", OUT / "naip.tif")),
        ("buildings", lambda: fetch_buildings(bbox, OUT / "buildings.gpkg")),
    ]
    if not args.skip_chesapeake:
        # 1 m land cover incl. tree canopy; collection may be older than NAIP - check the year printed
        steps.append(("chesapeake", lambda: fetch_raster("chesapeake-lc-13", bbox, "data",
                                                         OUT / "chesapeake_lc.tif", resolution=1.0)))
    if args.parcels_url:
        steps.append(("parcels", lambda: fetch_parcels(args.parcels_url, bbox, OUT / "parcels.gpkg")))
    else:
        log("parcels skipped (no --parcels-url given)")

    for name, fn in steps:
        try:
            fn()
        except Exception as e:  # keep going so one bad source doesn't block the rest
            log(f"FAILED {name}: {type(e).__name__}: {e}")
            failures.append(name)

    if (OUT / "chesapeake_lc.tif").exists():
        import rasterio
        with rasterio.open(OUT / "chesapeake_lc.tif") as src:
            vals, counts = np.unique(src.read(1), return_counts=True)
        log("chesapeake class counts: " + ", ".join(f"{v}:{c}" for v, c in zip(vals, counts)))

    log("done" if not failures else f"done with failures: {failures}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
