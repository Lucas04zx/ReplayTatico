"""Exporta observações numéricas da demonstração a partir dos artefatos locais."""

import argparse
import csv
import json
import shutil
from pathlib import Path, PureWindowsPath

import cv2
import numpy as np


DATA = Path(__file__).resolve().parent / "data"
LEG_JOINTS = (11, 13, 15, 12, 14, 16)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")


def coordinates(values):
    return [round(value, 1) for value in values]


def read_masks(path):
    masks = {}
    if path.is_file():
        with np.load(path, allow_pickle=False) as tracks:
            for key in tracks.files:
                frame, track = key.split("_")
                contours, _ = cv2.findContours(tracks[key].astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                masks.setdefault(int(frame), {})[track] = [
                    cv2.approxPolyDP(contour, 1.0, True).reshape(-1, 2).tolist()
                    for contour in contours if cv2.contourArea(contour) > 4
                ]
    return masks


def export_clip(folder, identifier, label, *, evaluation=False):
    analysis = read_json(folder / "analise.json")
    result = analysis["pass"]
    depth_folder = folder / "evidencias"
    moments = analysis["depth_frames"]
    reference = None
    if evaluation:
        comparison = read_json(folder / "avaliacao.json")
        annotation = comparison["referencia_manual"]
        reference = {
            "passer": comparison["id_associado_ao_passador_manual"],
            "receiver": comparison["id_associado_ao_recebedor_manual"],
            "release": annotation["release"],
            "reception": annotation["reception"],
            "seconds": comparison["duracao_manual_segundos"],
        }
        visual = folder / "referencia-visual"
        depth_folder = visual / "evidencias"
        moments = read_json(visual / "origem.json")["quadros"]
    passer = str((reference or result)["passer"])
    masks = read_masks(folder / "mascaras.npz")
    frames = []
    for raw in read_json(folder / "quadros.json"):
        index = raw["index"]
        frame = {
            "index": index,
            "players": {track: coordinates(box) for track, box in raw["players"].items()},
            "ball": None if raw["ball"] is None else coordinates(raw["ball"]),
        }
        pose = raw["poses"].get(passer)
        if pose:
            frame["pose"] = [[*coordinates(pose[joint][:2]), round(pose[joint][2], 3)]
                             for joint in LEG_JOINTS]
        if index in masks:
            frame["masks"] = masks[index]
        frames.append(frame)
    if [frame["index"] for frame in frames] != list(range(analysis["start"], analysis["end"] + 1)):
        raise ValueError(f"Numeração de quadros inválida em {folder}.")
    indexed = {frame["index"]: frame for frame in frames}
    events = []
    for source in analysis["events"]:
        event = {**source, "position": indexed[source["frame"]]["ball"]}
        role = "passer" if source["type"] == "PASS_START" else "receiver"
        box = indexed[source["frame"]]["players"].get(str(result[role]))
        if box is not None:
            event["player"] = [round((box[0] + box[2]) / 2, 1), box[3]]
        events.append(event)
    if reference:
        events.extend({"type": event, "frame": reference[key], "origin": "referência manual"}
                      for event, key in (("REFERENCE_START", "release"), ("REFERENCE_END", "reception")))
    depths = {name: {"name": name, "frame": index, "samples": []} for name, index in moments.items()}
    with (depth_folder / "profundidade.csv").open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            depths[row["momento"]]["samples"].append({
                "id": int(row["id"]) if row["id"] else None,
                "role": row["papel"],
                "median": float(row["mediana_modelo"]) if row["mediana_modelo"] else None,
            })
    metadata = {
        "id": identifier, "label": label,
        "source": PureWindowsPath(analysis["source"]).name,
        "has_analysis": True,
        **{field: analysis[field] for field in ("start", "end", "config_signature")},
        **{field: analysis["video"][field] for field in ("width", "height", "fps")},
        "pass": result, "events": events, "frames": frames, "reference": reference,
        "depth": list(depths.values()), "pose_conf": analysis["config"]["pose_conf"],
        "has_masks": bool(masks),
    }
    write_json(DATA / f"{identifier}.json", metadata)
    shutil.copyfile(folder / "resultado.csv", DATA / f"{identifier}-resultado.csv")
    shutil.copyfile(depth_folder / "profundidade.csv", DATA / f"{identifier}-profundidade.csv")
    return {"id": identifier, "label": label}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ajuste", type=Path, default=Path("outputs/ajuste"))
    parser.add_argument("--avaliacao", type=Path, default=Path("outputs/avaliacao"))
    args = parser.parse_args()
    DATA.mkdir(exist_ok=True)
    write_json(DATA / "clipes.json", [
        export_clip(args.ajuste, "ajuste", "Ajuste · passe automático"),
        export_clip(args.avaliacao, "avaliacao-tp2", "Avaliação · resultado inconclusivo", evaluation=True),
    ])
