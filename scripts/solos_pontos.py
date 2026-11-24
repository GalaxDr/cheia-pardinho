import sys, json, re, numpy as np, rasterio, geopandas as gpd, warnings
from rasterio.features import rasterize
from shapely.geometry import Point
from PIL import Image
warnings.filterwarnings("ignore")
IN, IN3, SITE = sys.argv[1:4]
dem = rasterio.open(IN + "/DEM_Subbacia_Rio_Pardinho.tif"); T, H, W = dem.transform, dem.height, dem.width
so = gpd.read_file(IN + "/Classe de solo - subbacia Rio Pardinho.gpkg").to_crs(dem.crs)
so["k"] = so.legenda.str.split(" - ").str[0]
# grupo hidrologico (SCS) adaptado a solos brasileiros (Sartori, Lombardi Neto e Genovez, 2005): 1=A 2=B 3=C 4=D
GH = {"RLm": 4, "NBa": 2, "NVef": 2, "PVa": 3, "PBACal": 3, "CYve": 3, "TXo": 3}
print(so.groupby("k").size().to_dict())
g = rasterize(((geom, GH.get(k, 3)) for geom, k in zip(so.geometry, so.k)), out_shape=(H, W), transform=T, fill=3, dtype="uint8")
Image.fromarray(g).save(SITE + "/solo.png", optimize=True)
inv = ~T
def px(geom):
    p = geom.representative_point() if geom.geom_type != "Point" else geom
    c, r = inv * (p.x, p.y); return round(c, 1), round(r, 1)
meta = json.load(open(SITE + "/meta.json", encoding="utf-8"))
pc = gpd.read_file(IN3 + "/pontos.gpkg").to_crs(dem.crs).sort_values("Ordem")
tr = gpd.read_file(IN3 + "/trechos.gpkg").to_crs(dem.crs)
psa = gpd.read_file(IN3 + "/kmz/doc.kml", driver="KML") if False else None
# KML (pontos do PSA): le coordenadas sem guardar nomes
k = open(IN3 + "/kmz/doc.kml", encoding="utf-8", errors="ignore").read()
pts = re.findall(r"<Point>.*?<coordinates>\s*([-\d.]+),([-\d.]+)", k, flags=re.S)
psa = gpd.GeoDataFrame(geometry=[Point(float(x), float(y)) for x, y in pts], crs=4326).to_crs(dem.crs)
bac = gpd.read_file(IN + "/Subbacia_Rio Pardinho.gpkg").to_crs(dem.crs).union_all()
meta["pontos"] = {
  "coleta": [{"n": r.Name, "xy": px(r.geometry)} for r in pc.itertuples()],
  "trechos": [{"n": r.id, "xy": px(r.geometry)} for r in tr.itertuples()],
  "psa": [{"n": f"PSA {i+1}", "xy": px(gm)} for i, gm in enumerate(psa.geometry) if bac.contains(gm)],
}
print("coleta", len(meta["pontos"]["coleta"]), "trechos", len(meta["pontos"]["trechos"]), "psa na bacia", len(meta["pontos"]["psa"]), "de", len(psa))
json.dump(meta, open(SITE + "/meta.json", "w", encoding="utf-8"), ensure_ascii=False)
