import sys, json, numpy as np, warnings
if not hasattr(np, "in1d"): np.in1d = np.isin
from pysheds.grid import Grid
from PIL import Image
warnings.filterwarnings("ignore")
WORK, SITE = sys.argv[1], sys.argv[2]
grid = Grid.from_raster(WORK + "/dem_nd.tif"); dem = grid.read_raster(WORK + "/dem_nd.tif")
demc = grid.read_raster(WORK + "/dem_cond.tif")
inf = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(demc)))
fdir = np.asarray(grid.flowdir(inf)); acc = np.asarray(grid.accumulation(grid.flowdir(inf)))
z = np.asarray(dem); valid = z > -9000
H, W = fdir.shape
# dirmap pysheds: N=64 NE=128 E=1 SE=2 S=4 SW=8 W=16 NW=32  -> codigo 1..8
DM = {64: (1, -1, 0), 128: (2, -1, 1), 1: (3, 0, 1), 2: (4, 1, 1), 4: (5, 1, 0), 8: (6, 1, -1), 16: (7, 0, -1), 32: (8, -1, -1)}
code = np.zeros((H, W), "uint8"); dr = np.zeros((H, W), "int8"); dc = np.zeros((H, W), "int8")
for k, (c, a, b) in DM.items():
    m = (fdir == k) & valid; code[m] = c; dr[m] = a; dc[m] = b
rr, cc = np.indices((H, W))
nr, nc = rr + dr, cc + dc
inb = (nr >= 0) & (nr < H) & (nc >= 0) & (nc < W)
down = np.full(H * W, -1, "int64")
ok = valid & (code > 0) & inb
ok[ok] = valid[nr[ok], nc[ok]]
down[ok.ravel()] = (nr * W + nc)[ok]
code[valid & ~ok] = 0
# velocidades assumidas (m/s): encosta 0,3 | arroio (>=1 km2) 1,0 | rio (>=50 km2) 1,5
akm = acc * 900 / 1e6
v = np.where(akm >= 50, 1.5, np.where(akm >= 1, 1.0, 0.3))
L = np.where((dr != 0) & (dc != 0), 30 * np.sqrt(2), 30.0)
step = (L / v).ravel()  # s
# tempo ate a saida: ordem topologica por acumulacao crescente reversa (de jusante para montante)
order = np.argsort(-acc.ravel(), kind="stable")
t = np.zeros(H * W)
vflat = valid.ravel()
for i in order:
    if not vflat[i]: continue
    d = down[i]
    t[i] = step[i] + (t[d] if d >= 0 else 0.0)
th = t.reshape(H, W) / 3600.0
print("tempo max h", round(th[valid].max(), 1), "mediana", round(np.median(th[valid]), 1))
outlet = int(np.argmax(acc)); print("foz", divmod(outlet, W), "acc km2", round(akm.ravel()[outlet], 1))
G = np.clip(np.log10(np.maximum(acc, 1)) * 40, 0, 255).astype("uint8")
B = np.clip(np.round(th * 10), 0, 254).astype("uint8"); B[~valid] = 255
R = code.copy()
Image.fromarray(np.dstack([R, G, B])).save(SITE + "/fluxo.png", optimize=True)
meta = json.load(open(SITE + "/meta.json", encoding="utf-8"))
meta["fluxo"] = {"foz": outlet, "vel": {"encosta": 0.3, "arroio": 1.0, "rio": 1.5}, "t_max_h": round(float(th[valid].max()), 1)}
json.dump(meta, open(SITE + "/meta.json", "w", encoding="utf-8"), ensure_ascii=False)
# checa consistencia: quantas celulas chegam na foz
seen = 0
print("pixels validos", int(valid.sum()))
