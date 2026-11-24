import sys, json, numpy as np, rasterio
from pyproj import Transformer
d = sys.argv[1]
dem = rasterio.open(d + "/in/DEM_Subbacia_Rio_Pardinho.tif"); inv = ~dem.transform
tr = Transformer.from_crs(4326, dem.crs, always_xy=True)
lon, lat = np.meshgrid(np.linspace(-52.9, -52.1, 30), np.linspace(-30.05, -29.05, 30))
x, y = tr.transform(lon.ravel(), lat.ravel()); col, row = inv * (np.asarray(x), np.asarray(y))
L0, B0 = -52.5, -29.55; u, v = lon.ravel() - L0, lat.ravel() - B0
A = np.c_[np.ones(u.size), u, v, u*u, u*v, v*v]
cc, *_ = np.linalg.lstsq(A, col, rcond=None); cr, *_ = np.linalg.lstsq(A, row, rcond=None)
m = json.load(open(d + "/site/meta.json", encoding="utf-8"))
m["geo"] = {"l0": L0, "b0": B0, "col": [float(t) for t in cc], "row": [float(t) for t in cr]}
m.get("pontos", {}).pop("psa", None)
json.dump(m, open(d + "/site/meta.json", "w", encoding="utf-8"), ensure_ascii=False)
print("meta:", list(m.keys()))
