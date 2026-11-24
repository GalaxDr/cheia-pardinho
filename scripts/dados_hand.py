# troca so os canais de HAND (R = arroios, G = rios) do dados.png pelos HAND recalculados
import sys, numpy as np
from PIL import Image
WORK, PNG = sys.argv[1], sys.argv[2]
d = np.array(Image.open(PNG).convert("RGB"))
def enc(h, fora):
    q = np.where(np.isfinite(h), np.clip(np.round(h * 10), 0, 254), 254)
    q[np.isfinite(h) & (h > 25.3)] = 254
    q[fora] = 255
    return q.astype("uint8")
fora = d[..., 0] == 255
d[..., 0] = enc(np.load(WORK + "/hand_arroios.npy"), fora)
d[..., 1] = enc(np.load(WORK + "/hand_rios.npy"), fora)
Image.fromarray(d).save(PNG, optimize=True)
print("ok", d.shape)
