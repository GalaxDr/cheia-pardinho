import sys, numpy as np, rasterio, geopandas as gpd
from rasterio.features import rasterize
IN, WORK = sys.argv[1], sys.argv[2]
src = rasterio.open(WORK + "/dem_nd.tif"); z = src.read(1); T = src.transform
valid = z > -9000
rios = gpd.read_file(IN + "/Rios_Subbacia.gpkg").to_crs(src.crs)
hid = gpd.read_file(IN + "/Hidrografia Rio Pardinho_Tipo.gpkg").to_crs(src.crs)
r1 = rasterize(((g, 1) for g in hid.geometry), out_shape=z.shape, transform=T, fill=0, all_touched=True, dtype="uint8").astype(bool)
r2 = rasterize(((g, 1) for g in rios.geometry), out_shape=z.shape, transform=T, fill=0, all_touched=True, dtype="uint8").astype(bool)
zb = z.copy()
zb[r1 & valid] -= 5.0     # arroios mapeados
zb[r2 & valid] -= 20.0    # rios principais mapeados
print("celulas gravadas: arroios", int((r1 & valid).sum()), "rios", int((r2 & valid).sum()))
p = src.profile
with rasterio.open(WORK + "/dem_cond.tif", "w", **p) as d: d.write(zb, 1)
