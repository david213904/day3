# manual_src.html + code/* -> manual.html -> PDF
import html, re, subprocess, pathlib
root = pathlib.Path(__file__).parent
src = (root / "manual_src.html").read_text(encoding="utf-8")
src = src.replace("{{STYLE}}", (root / "_style.css").read_text(encoding="utf-8"))

def render(name):
    text = (root / "code" / name).read_text(encoding="utf-8").rstrip("\n")
    out = []
    for line in text.split("\n"):
        e = html.escape(line, quote=False)
        if name.endswith(".py"):
            m = re.match(r"^(\s*)(#.*)$", e) or re.match(r"^(.*?\S)(\s{2,}#\s.*)$", e)
            if m: e = m.group(1) + '<span class="c">' + m.group(2) + "</span>"
        elif name.endswith(".sql"):
            m = re.match(r"^(.*?)(--.*)$", e)
            if m: e = m.group(1) + '<span class="c">' + m.group(2) + "</span>"
        elif name.endswith(".jsx"):
            m = re.match(r"^(\s*)(//.*)$", e)
            if m: e = m.group(1) + '<span class="c">' + m.group(2) + "</span>"
        out.append(e)
    return "\n".join(out)

src = re.sub(r"\{\{FILE:([^}]+)\}\}", lambda m: render(m.group(1)), src)
(root / "manual.html").write_text(src, encoding="utf-8")
pdf = root / "주식1시간봉_FastAPI_Supabase_실습매뉴얼.pdf"
subprocess.run([r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={pdf}", (root / "manual.html").as_uri()], check=True)
print("ok", pdf, pdf.stat().st_size)
