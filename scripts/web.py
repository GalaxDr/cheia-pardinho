import sys, os, json, zipfile, numpy as np, rasterio, geopandas as gpd, warnings
from rasterio.warp import reproject, Resampling
from rasterio.features import rasterize
from PIL import Image
warnings.filterwarnings("ignore")
IN, WORK, MB, REGZIP, OUT = sys.argv[1:6]
os.makedirs(OUT, exist_ok=True)
dem = rasterio.open(IN + "/DEM_Subbacia_Rio_Pardinho.tif"); z = dem.read(1).astype("float64"); T = dem.transform
H, W = z.shape; valid = np.isfinite(z)
Ha = np.load(WORK + "/hand_arroios.npy"); Hr = np.load(WORK + "/hand_rios.npy")
# uso do solo na grade do DEM
mb = rasterio.open(MB); lu = np.zeros((H, W), "uint8")
reproject(mb.read(1), lu, src_transform=mb.transform, src_crs=mb.crs, dst_transform=T, dst_crs=dem.crs, resampling=Resampling.nearest, src_nodata=0, dst_nodata=0)
GR = {3:1, 9:2, 11:3, 12:3, 15:4, 21:5, 39:6, 40:6, 41:6, 48:6, 24:7, 25:7, 33:8}
lug = np.zeros_like(lu); 
for k, v in GR.items(): lug[lu == k] = v
# regioes homogeneas (v4, suavizadas)
zf = zipfile.ZipFile(REGZIP); tmp = WORK + "/reg"; zf.extractall(tmp)
gp = [os.path.join(r, f) for r, _, fs in os.walk(tmp) for f in fs if f.endswith(".gpkg")][0]
reg = gpd.read_file(gp, layer="regioes_suavizadas").to_crs(dem.crs)
rid = rasterize(zip(reg.geometry, reg.regiao), out_shape=(H, W), transform=T, fill=0, dtype="uint8")
# hillshade
gy, gx = np.gradient(np.where(valid, z, np.nanmean(z)), 30)
slope = np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
az, alt = np.radians(315), np.radians(45)
hs = np.sin(alt)*np.cos(slope) + np.cos(alt)*np.sin(slope)*np.cos(az - aspect)
hs = np.clip(hs, 0, 1)
# reduz para 60 m (blocos 2x2)
f = 1; H2, W2 = H//f, W//f
def blk(a, how):
    a = a[:H2*f, :W2*f].reshape(H2, f, W2, f).transpose(0, 2, 1, 3).reshape(H2, W2, f*f)
    if how == "mean": return np.nanmean(a, axis=2)
    if how == "first": return a[:, :, 0]
    if how == "mode":
        out = np.zeros((H2, W2), a.dtype)
        for v in np.unique(a):
            if v == 0: continue
            c = (a == v).sum(2); m = c > (out_c if 'out_c' in dir() else 0)
        return a[:, :, 0]
v2 = blk(valid.astype(float), "mean") >= 0.5
def enc(Hh):
    h = blk(Hh, "mean")
    q = np.where(np.isfinite(h), np.clip(np.round(h*10), 0, 254), 254)
    q[np.isfinite(h) & (h > 25.3)] = 254
    q[~v2] = 255
    return q.astype("uint8")
R = enc(Ha); G = enc(Hr)
# canais de corrego: marca celulas de canal (HAND==0 na resolucao original) para desenho
sa = np.load(WORK + "/streams_arroios.npy"); sr = np.load(WORK + "/streams_rios.npy")
acc = np.load(WORK + "/acc.npy")
B = blk(lug, "first").astype("uint8"); B[~v2] = 0
# canal: 1 = arroio, 2 = rio (>=50 km2); guardado nos bits altos do canal B (B<16 sempre)
ch = np.maximum(blk(sa.astype(float), "mean") > 0, 0).astype("uint8") + (blk(sr.astype(float), "mean") > 0).astype("uint8")
B = (B | (ch << 4)).astype("uint8")
Image.fromarray(np.dstack([R, G, B])).save(OUT + "/dados.png", optimize=True)
hs2 = (blk(hs, "mean")*255).astype("uint8"); hs2[~v2] = 0
rg = blk(rid, "first").astype("uint8")
Image.fromarray(np.dstack([hs2, rg, (v2*255).astype("uint8")])).save(OUT + "/base.png", optimize=True)
# contornos das regioes em coordenadas de pixel (60 m), simplificados
inv = ~T
def tocoords(geom):
    paths = []
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    for p in polys:
        p = p.simplify(60)
        for ring in [p.exterior] + list(p.interiors):
            pts = [inv * (c[0], c[1]) for c in ring.coords]
            paths.append("M" + "L".join(f"{c/f:.1f},{r/f:.1f}" for c, r in pts) + "Z")
    return "".join(paths)
cent = reg.geometry.apply(lambda g: g.representative_point())
regs = [{"id": int(r.regiao), "d": tocoords(r.geometry), "x": round((inv*(c.x, c.y))[0]/f, 1), "y": round((inv*(c.x, c.y))[1]/f, 1),
         "desc": r.descricao} for (_, r), c in zip(reg.iterrows(), cent)]
bac = gpd.read_file(IN + "/Subbacia_Rio Pardinho.gpkg").to_crs(dem.crs)
meta = {"w": int(W2), "h": int(H2), "px_m": 30*f, "regioes": regs, "bacia": tocoords(bac.union_all()),
        "area_bacia_km2": round(float(v2.sum())*(30*f)**2/1e6, 1)}
json.dump(meta, open(OUT + "/meta.json", "w", encoding="utf-8"), ensure_ascii=False)
print(W2, H2, meta["area_bacia_km2"], [os.path.getsize(OUT + "/" + x)//1024 for x in ["dados.png", "base.png", "meta.json"]])
print("uso pixels", np.bincount(blk(lug,'first')[v2], minlength=9))
for lv in [1, 3, 5, 10]:
    print(lv, "m arroios km2", round(((R <= lv*10) & v2).sum()*0.0009, 1), "rios km2", round(((G <= lv*10) & v2).sum()*0.0009, 1))
