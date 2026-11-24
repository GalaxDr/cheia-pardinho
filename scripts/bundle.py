import sys, base64, re, os
d, out = sys.argv[1], sys.argv[2]
h = open(d + "/index.html", encoding="utf-8").read()
for f in re.findall(r'carregar\("([\w.]+\.png)"\)', h):
    uri = "data:image/png;base64," + base64.b64encode(open(f"{d}/{f}", "rb").read()).decode()
    h = h.replace(f'carregar("{f}")', f'carregar("{uri}")')
meta = open(d + "/meta.json", encoding="utf-8").read()
old = 'fetch("meta.json").then((r) => r.json())'; assert old in h
h = h.replace(old, "Promise.resolve(META)")
h = h.replace("<script>\n(function () {", "<script>\nconst META = " + meta.replace("</", "<\\/") + ";\n</script>\n<script>\n(function () {", 1)
for f in re.findall(r'src="([\w.]+\.png)"', h):
    h = h.replace(f'src="{f}"', 'src="data:image/png;base64,' + base64.b64encode(open(f"{d}/{f}", "rb").read()).decode() + '"')
te = h.index("</title>") + len("</title>")
tema = '''<script>
(function () {
  const b = document.getElementById("tema"), r = document.documentElement;
  const rot = () => { b.textContent = r.dataset.theme === "dark" ? "Tema claro" : "Tema escuro"; };
  b.addEventListener("click", () => { r.dataset.theme = r.dataset.theme === "dark" ? "light" : "dark"; rot(); });
  rot();
})();
</script>'''
doc = ('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
       + h[:te] + "\n<link rel=\"icon\" type=\"image/png\" href=\"data:image/png;base64," + base64.b64encode(open(d + "/apple-touch-icon.png", "rb").read()).decode() + "\">\n<style>body{margin:0}[hidden]{display:none!important}</style>\n" + h[te:].replace("</style>\n", "</style>\n</head>\n<body>\n", 1) + "\n</body>\n</html>\n")
open(out, "w", encoding="utf-8").write(doc)
print(os.path.getsize(out) // 1024, "KB")
