import sys, os, numpy as np, rasterio, warnings
if not hasattr(np, "in1d"): np.in1d = np.isin
from pysheds.grid import Grid
warnings.filterwarnings("ignore")
IN, OUT = sys.argv[1], sys.argv[2]
src = rasterio.open(IN); z = src.read(1).astype("float64")
valid = np.isfinite(z)
prof = src.profile.copy(); prof.update(dtype="float64", nodata=-9999.0)
zz = np.where(valid, z, -9999.0)
with rasterio.open(OUT + "/dem_nd.tif", "w", **prof) as d: d.write(zz, 1)
grid = Grid.from_raster(OUT + "/dem_nd.tif")
dem = grid.read_raster(OUT + "/dem_nd.tif")
import subprocess; subprocess.run([sys.executable, "-I", os.path.dirname(os.path.abspath(__file__)) + "/burn.py", os.path.dirname(IN), OUT], check=True)
demc = grid.read_raster(OUT + "/dem_cond.tif")
pit = grid.fill_pits(demc); flo = grid.fill_depressions(pit); inf = grid.resolve_flats(flo)
fdir = grid.flowdir(inf)
acc = grid.accumulation(fdir)
A = np.asarray(acc)
print("acc max cells", A.max(), "km2", A.max()*900/1e6)
res = {}
for nome, km2 in [("arroios", 1.0), ("rios", 50.0)]:
    streams = acc > km2*1e6/900
    hand = grid.compute_hand(fdir, dem, streams)
    H = np.asarray(hand, dtype="float64")
    H[~valid] = np.nan
    print(nome, "stream cells", int(np.asarray(streams).sum()), "HAND pct", np.nanpercentile(H, [5, 25, 50, 75, 95]).round(1), "nan%", round(np.isnan(H[valid]).mean()*100, 2))
    np.save(OUT + f"/hand_{nome}.npy", H)
    np.save(OUT + f"/streams_{nome}.npy", np.asarray(streams))
np.save(OUT + "/acc.npy", A)
