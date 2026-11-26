import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def package_delivery(adjustment, evaluation, reference, output):
    adjustment, evaluation, reference, output = map(Path, (adjustment, evaluation, reference, output))
    visual = evaluation / "referencia-visual"
    report_files = ("RELATORIO.md", "APRESENTACAO.md", "VIDEOS.md", "ALGORITMOS.md")
    common = {f"docs/{name}": Path("docs") / name for name in report_files}
    common["data/annotations/avaliacao.json"] = reference
    for name, directory in (("ajuste", adjustment), ("avaliacao", evaluation)):
        for filename in ("resultado.csv", "analise.json"):
            common[f"resultados/{name}/{filename}"] = directory / filename
    common["resultados/ajuste/profundidade.csv"] = adjustment / "evidencias/profundidade.csv"
    common["resultados/avaliacao/comparacao.json"] = evaluation / "avaliacao.json"
    common["resultados/avaliacao/profundidade-referencia.csv"] = visual / "evidencias/profundidade.csv"
    common["resultados/avaliacao/origem-das-evidencias.json"] = visual / "origem.json"
    local_only = {
        "replays/ajuste.mp4": adjustment / "replay.mp4",
        "replays/avaliacao-automatica.mp4": evaluation / "replay.mp4",
        "replays/avaliacao-referencia-manual.mp4": visual / "replay-referencia.mp4",
    }
    for name, directory in (("ajuste", adjustment), ("avaliacao-referencia", visual)):
        images = sorted((directory / "evidencias").glob("*.png"))
        if not images:
            raise ValueError(f"Evidências PNG ausentes em {directory}.")
        for path in images:
            local_only[f"evidencias/{name}/{path.name}"] = path
    for path in {**common, **local_only}.values():
        if not path.is_file():
            raise ValueError(f"Entregável ausente: {path}.")
    output.mkdir(parents=True, exist_ok=True)
    archives = {
        "ReplayTatico-resultados-e-referencia.zip": common,
        "ReplayTatico-entrega-local.zip": {**common, **local_only},
    }
    with tempfile.TemporaryDirectory(dir=output) as staging:
        for name, files in archives.items():
            with ZipFile(Path(staging) / name, "w", ZIP_DEFLATED, compresslevel=3) as archive:
                for target, source in sorted(files.items()):
                    archive.write(source, target)
        for name in archives:
            (Path(staging) / name).replace(output / name)
            print(output / name)
