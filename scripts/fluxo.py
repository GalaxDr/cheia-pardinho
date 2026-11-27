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
vflat = valid.ravel()
outlet0 = int(np.argmax(np.where(valid, acc, -1)))
def raiz(down):
    # celula final de cada caminho (salto de ponteiros, vetorizado)
    P = np.where(down >= 0, down, np.arange(H * W)); 
    while True:
        Q = P[P]
        if np.array_equal(Q, P): return P
        P = Q
def seguir(down):
    R = raiz(down); return vflat & (R == outlet0)
# celulas planas da varzea sem direcao no D8 (o resolve_flats nao resolve todas): liga cada uma, pelo caminho
# mais curto, a celula vizinha mais proxima que ja chega na foz
from collections import deque
viz8 = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
COD = {(-1, 0): 1, (-1, 1): 2, (0, 1): 3, (1, 1): 4, (1, 0): 5, (1, -1): 6, (0, -1): 7, (-1, -1): 8}
reach = seguir(down)
borda = valid & ~(np.pad(valid, 1)[:-2, 1:-1] & np.pad(valid, 1)[2:, 1:-1] & np.pad(valid, 1)[1:-1, :-2] & np.pad(valid, 1)[1:-1, 2:])
term = np.flatnonzero(vflat & (down < 0) & ~borda.ravel() & ~reach); term = term[term != outlet0]
for s in term:
    if reach[s]: continue
    prev = {s: -1}; q = deque([s]); alvo = -1
    while q:
        c = q.popleft(); r0, c0 = divmod(c, W)
        if reach[c] and c != s: alvo = c; break
        for a, b in viz8:
            r1, c1 = r0 + a, c0 + b
            if 0 <= r1 < H and 0 <= c1 < W and valid[r1, c1] and (r1 * W + c1) not in prev:
                prev[r1 * W + c1] = c; q.append(r1 * W + c1)
    if alvo < 0: continue
    c = alvo
    while prev[c] != -1:
        p = prev[c]; pr, pc = divmod(p, W); cr, cc_ = divmod(c, W)
        down[p] = c; code[pr, pc] = COD[(cr - pr, cc_ - pc)]; dr[pr, pc] = cr - pr; dc[pr, pc] = cc_ - pc
        c = p
    reach = seguir(down)
print("planos religados:", len(term))
# tempo ate a saida (memo iterativo seguindo o caminho)
L = np.where((dr != 0) & (dc != 0), 30 * np.sqrt(2), 30.0)
step = (L / v).ravel()
S_ = np.where(vflat, step, 0.0); P = down.copy()
while (P >= 0).any():
    m = P >= 0
    S_[m] += S_[P[m]]
    Pn = np.full_like(P, -1); Pn[m] = P[P[m]]; P = Pn
t = S_
order = np.argsort(-acc.ravel(), kind="stable")
# celulas cujo caminho sai do recorte da bacia antes de chegar na foz (o divisor do MDE nao coincide
# com o contorno oficial nas bordas): nao contribuem para a foz -> codigo 253 no canal B
reach = reach.reshape(H, W)
print("nao chegam na foz: %.1f km2 (%.1f%%)" % ((valid & ~reach).sum() * 900 / 1e6, 100 * (valid & ~reach).sum() / valid.sum()))
th = t.reshape(H, W) / 3600.0
th[~reach] = np.nan
print("tempo max h", round(np.nanmax(th[valid]), 1), "mediana", round(np.nanmedian(th[valid]), 1))
outlet = int(np.argmax(acc)); print("foz", divmod(outlet, W), "acc km2", round(akm.ravel()[outlet], 1))
G = np.clip(np.log10(np.maximum(acc, 1)) * 40, 0, 255).astype("uint8")
B = np.clip(np.round(np.nan_to_num(th) * 10), 0, 252).astype("uint8"); B[valid & ~reach] = 253; B[~valid] = 255
R = code.copy()
Image.fromarray(np.dstack([R, G, B])).save(SITE + "/fluxo.png", optimize=True)
meta = json.load(open(SITE + "/meta.json", encoding="utf-8"))
meta["fluxo"] = {"foz": outlet, "vel": {"encosta": 0.3, "arroio": 1.0, "rio": 1.5}, "t_max_h": round(float(np.nanmax(th[valid])), 1)}
json.dump(meta, open(SITE + "/meta.json", "w", encoding="utf-8"), ensure_ascii=False)
# checa consistencia: quantas celulas chegam na foz
seen = 0
print("pixels validos", int(valid.sum()))
