# HAND com referencia do rio corrigida: a cota de cada celula de canal passa a ser o minimo do MDE num raio
# de R celulas (aproxima a lamina d'agua/varzea, que o MDE de superficie mostra mais alta por causa da mata ciliar),
# forcada a nunca subir rio abaixo.
import sys, os, numpy as np, rasterio, warnings
if not hasattr(np, "in1d"): np.in1d = np.isin
from pysheds.grid import Grid
from scipy.ndimage import minimum_filter
warnings.filterwarnings("ignore")
WORK, R = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3
grid = Grid.from_raster(WORK + "/dem_nd.tif")
dem = grid.read_raster(WORK + "/dem_nd.tif")
z = np.asarray(dem, dtype="float64"); valid = z > -9000
demc = grid.read_raster(WORK + "/dem_cond.tif")
inf = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(demc)))
fdir = grid.flowdir(inf); F = np.asarray(fdir)
accR = grid.accumulation(fdir); A = np.asarray(accR)
zf = np.where(valid, z, 1e9)
yy, xx = np.mgrid[-R:R+1, -R:R+1]; disco = (xx**2 + yy**2) <= R*R
zmin = minimum_filter(zf, footprint=disco, mode="nearest")
DR = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}
Hh, Ww = z.shape
for nome, km2 in [("arroios", 1.0), ("rios", 50.0)]:
    s = (A > km2*1e6/900) & valid
    ref = np.where(s, np.minimum(z, zmin), z)
    r, c = np.where(s); o = np.argsort(A[r, c])
    for k in o:                       # de montante para jusante: nunca sobe
        i, j = r[k], c[k]; d = DR.get(int(F[i, j]))
        if not d: continue
        a, b = i + d[0], j + d[1]
        if 0 <= a < Hh and 0 <= b < Ww and s[a, b] and ref[a, b] > ref[i, j]: ref[a, b] = ref[i, j]
    dm = dem.copy(); dm[:] = np.where(valid, ref, -9999.0)
    H = np.asarray(grid.compute_hand(fdir, dm, accR > km2*1e6/900), dtype="float64")
    H[~valid] = np.nan
    H[s] = 0.0
    # dentro do raster, a altura usa o MDE original; a referencia corrigida so muda a cota do canal
    km = lambda n: n * 900 / 1e6; nc = np.isfinite(H) & ~s
    print(nome, "canal %.1f km2 | fora do canal: <0 %.1f, 0-0.15 %.1f, 0.15-1 %.1f, 1-2 %.1f km2" % (km(s.sum()), km((nc & (H < 0)).sum()), km((nc & (H >= 0) & (H < .15)).sum()), km((nc & (H >= .15) & (H < 1)).sum()), km((nc & (H >= 1) & (H < 2)).sum())))
    np.save(WORK + f"/hand_{nome}.npy", H)
