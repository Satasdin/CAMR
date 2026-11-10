import sys, fitz
for p in sys.argv[1:]:
    d = fitz.open(p)
    out = p[:-4] + ".txt"
    with open(out, "w") as f:
        for i, pg in enumerate(d):
            f.write(f"\n<<<PAGE {i+1}>>>\n" + pg.get_text())
    print(p, len(d), "pages", sum(len(pg.get_text()) for pg in d), "chars")
