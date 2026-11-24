import sys, shutil, os
site, P = sys.argv[1], sys.argv[2]
pub = P + "/public"
for f in ["dados.png", "base.png", "fluxo.png", "solo.png", "meta.json", "logo_muda.png", "favicon.ico", "apple-touch-icon.png", "icone-512.png"]:
    shutil.copy(f"{site}/{f}", f"{pub}/{f}")
h = open(site + "/index.html", encoding="utf-8").read()
old = 'const DC_URL = "https://redehidrometeorologica.defesacivil.rs.gov.br/graphql";'
assert old in h
h = h.replace(old, 'const DC_URL = /^https?:$/.test(location.protocol) && !/claude\\.ai|claudeusercontent/.test(location.hostname) ? "api/defesacivil" : "https://redehidrometeorologica.defesacivil.rs.gov.br/graphql";')
te = h.index("</title>") + len("</title>")
head = ('\n<link rel="icon" href="favicon.ico" sizes="any">\n<link rel="apple-touch-icon" href="apple-touch-icon.png">\n<meta name="theme-color" content="#427a52">\n'
        '<style>body{margin:0}[hidden]{display:none!important}</style>\n')
doc = ('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
       + h[:te] + head + h[te:].replace("</style>\n", "</style>\n</head>\n<body>\n", 1) + "\n</body>\n</html>\n")
open(pub + "/index.html", "w", encoding="utf-8").write(doc)
print("ok")
