import os

exts = (".html", ".js", ".py", ".json", ".ts")
for root, dirs, files in os.walk(r"C:\Users\Gabriel\Desktop"):
    if ".git" in root or "node_modules" in root or ".venv" in root:
        continue
    for f in files:
        if f.endswith(exts):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fl:
                    content = fl.read()
                    if "entregando" in content or "silêncio" in content or "palmas" in content or "orbe" in content:
                        print("FOUND:", path)
            except Exception:
                pass
print("Done.")
