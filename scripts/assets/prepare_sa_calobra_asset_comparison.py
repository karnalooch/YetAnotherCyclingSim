"""Build an offline review board from approved, hash-pinned colour review copies."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
from pathlib import Path
import re
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.manage_local_workspace import load_workspace  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "worldgen/materials"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jpeg(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


def uri(data: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def metric_crop(source: Image.Image, dimensions: list[float]) -> Image.Image:
    """Show exactly 2 x 2 source metres, centered, periodically wrapped if needed."""
    width, height = dimensions
    if min(width, height) <= 0:
        raise ValueError("Metric review requires positive source dimensions")
    extent_x, extent_y = source.width * 2 / width, source.height * 2 / height
    if max(extent_x, extent_y) > 4096:
        raise ValueError("Review extent exceeds the bounded renderer")
    tiled = Image.new("RGB", (source.width * 5, source.height * 5))
    for y in range(5):
        for x in range(5):
            tiled.paste(source, (x * source.width, y * source.height))
    cx, cy = tiled.width / 2, tiled.height / 2
    return tiled.transform(
        (512, 512),
        Image.Transform.EXTENT,
        (cx - extent_x / 2, cy - extent_y / 2, cx + extent_x / 2, cy + extent_y / 2),
        Image.Resampling.BICUBIC,
    )


def main(config: Path, output_name: str) -> None:
    workspace = load_workspace(config)
    work = Path(workspace["work"]).resolve()
    cache = work / "2b-asset-comparison-20261005"
    output = (work / output_name).resolve()
    if output.parent != work or output.exists():
        raise ValueError("Use a new direct child of canonical work")
    receipt_path = DATA / "sa_calobra_surface_review_receipt_20261005.json"
    decisions_path = DATA / "sa_calobra_surface_comparison_20261005.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    assets = {r["id"]: r for r in receipt["assets"]}
    if len(assets) != len(receipt["assets"]):
        raise ValueError("Duplicate asset identity")
    if len(decisions["roles"]) != 6:
        raise ValueError("All six surface roles are required")
    views, pixels = {}, {}
    for ident, record in assets.items():
        path = (cache / record["review_file"]).resolve()
        if path.parent != cache or sha(path) != record["review_sha256"]:
            raise ValueError(f"Invalid review bytes: {ident}")
        source = Image.open(path).convert("RGB")
        if list(source.size) != record["review_pixels"]:
            raise ValueError(f"Invalid review dimensions: {ident}")
        full = source.resize((512, 512), Image.Resampling.LANCZOS)
        metric = (
            metric_crop(source, record["dimensions_m"])
            if record["dimensions_m"]
            else full
        )
        views[ident] = {"full": uri(jpeg(full)), "metric": uri(jpeg(metric))}
        pixels[ident] = metric
    reference_text = (
        ROOT / "docs/experiments/sa-calobra-material-reference-review-2026-10-05.md"
    ).read_text(encoding="utf-8")
    source_links = re.findall(r"\[Source panorama\]\((https[^)]+)\)", reference_text)
    if len(source_links) != 3:
        raise ValueError("Expected three explicit panorama references")
    source_for = {
        "rock": 2,
        "scree": 0,
        "mineral": 2,
        "grass": 0,
        "forest": 1,
        "earthworks": 0,
    }
    ortho = (
        Path(workspace["data"])
        / "world-data/sa-calobra-working-v1/mask-transition-review-v1a-2026-10-04/orthophoto.png"
    )
    if sha(ortho) != "36eb65995ccd9ff7b8d169a208f97d2f3c6729c97053c5a5fcba4b3a6c62faa5":
        raise ValueError("Orthophoto identity differs")
    ortho_image = Image.open(ortho).convert("RGB")
    edges = [round(i * 4033 / 4) for i in range(5)]
    sections, nav = [], []
    e = html.escape
    for role in decisions["roles"]:
        candidates = role["candidates"]
        if len({c[0] for c in candidates}) < 3:
            raise ValueError("At least three distinct candidates are required per role")
        nav.append(f'<a href="#{role["id"]}">{e(role["title"])}</a>')
        row, col = int(role["sector"][1]) - 1, int(role["sector"][2]) - 1
        aerial = ortho_image.crop(
            (edges[col], edges[row], edges[col + 1], edges[row + 1])
        )
        aerial.thumbnail((260, 260))
        cards = []
        for ident, verdict, reason, limitation, status in candidates:
            a = assets[ident]
            dims = a["dimensions_m"]
            scale = f"{dims[0]:.2f} × {dims[1]:.2f} m" if dims else "skala nieznana"
            density = (
                f"{a['review_pixels'][0] / dims[0]:.1f} px/m w próbce"
                if dims
                else "bez porównania metrycznego"
            )
            label = (
                "Wyświetlony wycinek: 2 × 2 m"
                if dims
                else "Pełny kafel · skala nieznana"
            )
            cards.append(f'''<article class="candidate {status}">
<div class="verdict">{e(verdict)}</div><h3>{e(ident)}</h3>
<button class="picture" aria-label="Powiększ {e(ident)}" data-id="{e(ident)}"><img class="texture" data-id="{e(ident)}" src="{views[ident]["metric"]}" alt="Mapa koloru {e(ident)}"></button>
<p class="view-label" data-metric="{e(label)}" data-full="Pełny kafel · {e(scale)}">{e(label)}</p>
<p class="meta">Źródło: {e(scale)} · {e(density)}<br>{e(a["provider"])} · CC0 · 0 zł · maks. {a["max_resolution"][0] // 1024}K<br>Kolor / normal / roughness / AO / height: dostępne według API</p>
<p>{e(reason)}</p><p class="limit"><strong>Ograniczenie:</strong> {e(limitation)}</p>
<a href="{e(a["source_url"])}" target="_blank" rel="noopener">Strona źródłowa ↗</a></article>''')
        sections.append(f'''<section id="{role["id"]}"><header><span class="eyebrow">ROLA POWIERZCHNI</span><h2>{e(role["title"])}</h2><p>{e(role["target"])}</p></header>
<div class="reference"><img src="{uri(jpeg(aerial))}" alt="Ortofotomapa sektora {role["sector"]}"><div><h3>Referencja i jej granice</h3><p>{e(role["reference"])}</p><p>Orto: sektor {role["sector"]}, około 504 m szerokości. Pokazuje położenie i otoczenie, nie ziarno materiału. Fotografia i mapa koloru nie mają wspólnego oświetlenia.</p><a href="{e(source_links[source_for[role["id"]]])}" target="_blank" rel="noopener">Otwórz fotografię terenową ↗</a><p class="meta">Obra derivada de PNOA CC-BY 4.0 scne.es · 2024</p></div></div>
<p class="decision"><strong>Rekomendacja:</strong> {e(role["decision"])}</p><div class="candidates">{"".join(cards)}</div></section>''')
    extra = "".join(
        f'<li><a href="{e(assets[i]["source_url"])}">{e(i)}</a>: {e(reason)}</li>'
        for i, reason in decisions["additional_rejections"]
    )
    page = """<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sa Calobra — porównanie powierzchni</title>
<style>
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f4f3ee;color:#242c2a;font:16px/1.55 system-ui,sans-serif}a{color:#315d50}aside{position:fixed;inset:0 auto 0 0;width:240px;padding:30px 22px;background:#e8e9e1;border-right:1px solid #cdd0c7;overflow:auto}aside a{display:block;padding:10px 0}main{margin-left:240px;padding:36px;max-width:1600px}h1{font-size:32px;line-height:1.2;max-width:820px}h2{font-size:26px;margin:8px 0}h3{font-size:18px;margin:8px 0}.eyebrow{font-size:12px;letter-spacing:.1em;font-weight:700}.intro{max-width:980px}.toolbar{position:sticky;top:0;background:#f4f3ee;padding:14px 0;border-bottom:1px solid #bbb;z-index:2}.toolbar button{padding:9px 15px;border:1px solid #687b70;background:white;font:inherit;cursor:pointer}.toolbar button.active{background:#315d50;color:white}section{padding:45px 0;border-bottom:1px solid #aaa;scroll-margin-top:70px}.reference{display:flex;gap:24px;padding:20px 0;max-width:1050px}.reference img{width:190px;height:190px;object-fit:cover}.reference p{margin:7px 0}.decision{border-left:4px solid #315d50;padding:15px 20px;background:#e7ece5}.candidates{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:26px}.candidate{padding:16px;background:#fff;border-top:3px solid #a3aba4;min-width:0}.preferred{border-color:#315d50}.conditional{border-color:#a56b25}.verdict{font-size:13px;font-weight:700;min-height:22px}.picture{display:block;width:100%;padding:0;border:0;background:transparent;cursor:zoom-in}.texture{width:100%;aspect-ratio:1;display:block}.meta,.view-label{font-size:12px;color:#525e56}.limit{font-size:14px}.view-label{margin:5px 0}.notice{padding:16px 20px;border:1px solid #a56b25;max-width:1060px}dialog{border:1px solid #687b70;max-width:95vw;max-height:95vh;padding:20px;background:#f4f3ee}dialog img{max-width:80vw;max-height:75vh;display:block}dialog::backdrop{background:#000b}dialog button{float:right;font:inherit;padding:5px 12px}footer{font-size:13px;padding:35px 0}@media(max-width:1050px){aside{position:static;width:auto}aside a{display:inline-block;margin-right:18px}main{margin:0;padding:20px}.candidates{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.candidates{grid-template-columns:1fr}.reference{display:block}.reference img{width:100%;height:180px}h1{font-size:26px}}@media print{aside,.toolbar,dialog{display:none}main{margin:0;padding:0}.candidate{break-inside:avoid}.reference img{width:150px}section{padding:20px 0}}
</style><aside><span class="eyebrow">YACS · #363 · 05.10.2026</span><h3>Porównanie powierzchni</h3>__NAV__<p class="meta">21 źródeł<br>6 ról<br>Bez tintowania<br>Bez importu Unreal</p></aside><main>
<div class="intro"><span class="eyebrow">SA CALOBRA · PRZEGLĄD KANDYDATÓW</span><h1>Najpierw właściwa powierzchnia.<br>Potem materiał w Unreal.</h1><p>Porównanie surowych map koloru ze znanymi referencjami całego Landscape. Pierwszy wybór oznacza rekomendację do kolejnych próbek, nie zatwierdzenie produkcyjne.</p></div>
<p class="notice"><strong>Otwarte ograniczenia:</strong> skala Rock024 jest nieznana, lokalny gatunek ściółki niepotwierdzony, a granice FILL nie wynikają z receipt CUT-only. Tutaj oceniamy kolor i strukturę. Normal i roughness mają potwierdzoną dostępność w API, ale ich pliki i wygląd w Unreal nie zostały jeszcze sprawdzone.</p>
<div class="toolbar"><button class="active" data-mode="metric">Ten sam obszar: 2 × 2 m</button> <button data-mode="full">Pełne kafle źródłowe</button></div>
__SECTIONS__<section><h2>Pozostali sprawdzeni kandydaci</h2><ul>__EXTRA__</ul><h3>Spójność zestawu i następny test</h3><p>Jasne podłoże mineralne i szare kruszywo tworzą punkt wyjścia. Sucha trawa i brązowe liście powinny pozostawiać widoczny grunt i skałę. Nie poprawialiśmy barwy, jasności ani kontrastu źródeł.</p><p>Nie wybieramy modelu klifu ani głazu w tym kroku. Późniejsze modele (#368) trzeba dopasować do zaakceptowanej skały pod względem pęknięć, skali i barwy. Tekstura rumoszu nie zastąpi sylwetek kamieni.</p><p>Przed pełnym pozyskaniem i importem: decyzja o zestawie i brakującej skali skały, następnie sprawdzenie plików PBR i próbki w Unreal przy wspólnej kamerze i świetle. Przejścia trzeba ocenić parami; teren i drogi pozostają zamrożone.</p></section>
<footer>Źródła assetów: Poly Haven public API i ambientCG · CC0. Dostęp do API: YACS-SurfaceReview/1.0. Raport nie jest zatwierdzony przez dostawców. Lokalnie pozyskano 20 map koloru 1K i jeden podgląd koloru; nie pobrano pełnych zestawów produkcyjnych. Widok 2 m zachowuje skalę dostawcy; powiększenie nie dodaje detalu. Rocky Terrain ma tylko około 23 piksele źródłowe na 2 m w próbce 1K.<br>Fotografie terenowe: odnośniki do Google Maps, bez kopiowania ich obrazów do projektu. Kolor ortofotomapy nie jest mapą PBR. PNOA: Obra derivada de PNOA CC-BY 4.0 scne.es.</footer></main>
<dialog><button id="close">Zamknij</button><h3 id="dialog-title"></h3><img id="detail" alt="Powiększona mapa koloru"></dialog><script>
const views=__VIEWS__;let mode='metric';const dialog=document.querySelector('dialog');function change(m){mode=m;document.querySelectorAll('.texture').forEach(x=>x.src=views[x.dataset.id][m]);document.querySelectorAll('.view-label').forEach(x=>x.textContent=x.dataset[m]);document.querySelectorAll('[data-mode]').forEach(x=>x.classList.toggle('active',x.dataset.mode===m));}document.querySelectorAll('[data-mode]').forEach(x=>x.onclick=()=>change(x.dataset.mode));document.querySelectorAll('.picture').forEach(x=>x.onclick=()=>{document.querySelector('#detail').src=views[x.dataset.id][mode];document.querySelector('#dialog-title').textContent=x.dataset.id;dialog.showModal();});document.querySelector('#close').onclick=()=>dialog.close();
</script></html>"""
    page = page.replace("__NAV__", "".join(nav)).replace(
        "__SECTIONS__", "".join(sections)
    )
    page = page.replace("__EXTRA__", extra).replace("__VIEWS__", json.dumps(views))
    output.mkdir()
    (output / "comparison.html").write_text(page, encoding="utf-8")
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 19)
    title_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 23)
    sheet = Image.new("RGB", (1260, 1110), "#f4f3ee")
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (20, 12),
        "Sa Calobra: kandydaci do próbek — bez akceptacji produkcyjnej",
        font=title_font,
        fill="#242c2a",
    )
    for n, role in enumerate(decisions["roles"]):
        ident, verdict, *_ = role["candidates"][0]
        if role["id"] == "earthworks":
            ident, verdict = "rock_ground", "FILL · drobniejsze kruszywo"
        x, y = (n % 3) * 420 + 20, (n // 3) * 500 + 65
        draw.text((x, y), role["title"], font=font, fill="#242c2a")
        sheet.paste(pixels[ident].resize((390, 390)), (x, y + 30))
        draw.text((x, y + 428), ident, font=title_font, fill="#242c2a")
        for line, txt in enumerate(textwrap.wrap(verdict, 34)):
            draw.text((x, y + 460 + line * 21), txt, font=font, fill="#525e56")
    draw.text(
        (20, 1080),
        "2 × 2 m poza Rock024 (skala nieznana) · Poly Haven / ambientCG · CC0 · surowy kolor",
        font=font,
        fill="#525e56",
    )
    sheet.save(output / "shortlist.png")
    report = {
        "status": "REVIEW_NOT_APPROVAL",
        "assets": len(assets),
        "roles": 6,
        "receipt_sha256": sha(receipt_path),
        "decisions_sha256": sha(decisions_path),
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "outputs": [
            {"path": p.name, "sha256": sha(p)} for p in sorted(output.iterdir())
        ],
    }
    (output / "comparison-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "assets": len(assets),
                "roles": 6,
                "output": str(output),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-config", required=True, type=Path)
    parser.add_argument("--output-name", required=True)
    args = parser.parse_args()
    main(args.workspace_config, args.output_name)
