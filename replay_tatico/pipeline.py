import hashlib
import json
import tempfile
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .exports import export_evidence, export_pass, export_replay, write_json
from .inference import detect_ball, estimate_depth, estimate_pose, release_memory, runtime, segment_frames, track_players
from .pass_analysis import identify_pass
from .video import file_hash, probe


CACHE_FORMAT = 2
DEFAULT_CONFIG = Path("configs/ajuste.json")
FROZEN_CONFIG = Path("configs/avaliacao.json")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def identity_digest(config_path, config):
    files = [Path(config_path), Path(config["tracker"])]
    files.extend(Path("models") / name for name in sorted(set(config["weights"].values())))
    return hashlib.sha256("".join(file_hash(path) for path in files).encode("ascii")).hexdigest()


def observe(video, start, end, info, config, torch, ultralytics, device):
    frame_config = {key: config[key] for key in (
        "player_imgsz", "ball_imgsz", "ball_conf", "ball_class", "pose_imgsz", "association_iou",
    )}
    frame_config["tracker"] = file_hash(config["tracker"])
    for task in ("detect", "ball", "pose"):
        frame_config[task] = file_hash(Path("models") / config["weights"][task])
    key = [CACHE_FORMAT, start, end, info["sha256"], ultralytics.__version__, torch.__version__, device, frame_config]
    digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode("utf-8")).hexdigest()
    destination = Path(".cache") / "observations" / f"{digest}.json"
    if destination.exists():
        frames = read_json(destination)
        for frame in frames:
            frame["players"] = {int(track): box for track, box in frame["players"].items()}
            frame["poses"] = {int(track): pose for track, pose in frame["poses"].items()}
        print("Detecção, IDs e poses carregados do cache.", flush=True)
        return frames
    frames = [{"index": index, "players": {}, "poses": {}, "ball": None, "ball_confidence": None}
              for index in range(start, end + 1)]
    for stage, observe_stage in (("ByteTrack", track_players), ("Bola", detect_ball), ("Pose", estimate_pose)):
        print(f"{stage} | quadros {start}–{end}", flush=True)
        observe_stage(video, frames, config, ultralytics, device)
        release_memory(torch)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
        pending = Path(staging) / destination.name
        write_json(pending, frames)
        pending.replace(destination)
    return frames


def depth_moments(result, start, end):
    if result.release is not None and result.reception is not None:
        return {"saida": result.release, "trajetoria": (result.release + result.reception) // 2,
                "recepcao": result.reception}
    return {"inicio_amostra": start, "meio_amostra": (start + end) // 2, "fim_amostra": end}


def analyze(video, start, end, output, config_path=DEFAULT_CONFIG, device="auto", evaluation_reference=None):
    video = Path(video)
    output = Path(output)
    if output.exists():
        raise ValueError(f"A saída já existe: {output}. Escolha outra pasta.")
    info = probe(video)
    if not info["constant_fps"]:
        raise ValueError("O pipeline requer FPS constante para calcular a duração e exportar o replay fielmente.")
    if not 0 <= start <= end - 3 or end >= info["frames"]:
        raise ValueError(f"Selecione pelo menos quatro quadros válidos entre 0 e {info['frames'] - 1}.")
    config = read_json(config_path)
    signature = identity_digest(config_path, config)
    if evaluation_reference is not None:
        from .evaluation import validate_reference

        # Somente o manifesto e a presença do registro independente são verificados aqui.
        validate_reference(evaluation_reference, info, start, end, signature)
    torch, ultralytics, device = runtime(device)
    frames = observe(video, start, end, info, config, torch, ultralytics, device)
    result = identify_pass(frames, info["fps"], config)
    roles = {track for track in (result.passer, result.receiver) if track is not None}
    moments = depth_moments(result, start, end)
    mask_indices = set(moments.values())
    if result.release is not None:
        mask_indices.update(range(max(start, result.release - 4), min(end, result.release + 4) + 1))
    print("Segmentação e profundidade", flush=True)
    masks = segment_frames(video, [frame for frame in frames if frame["index"] in mask_indices],
                           roles, config, ultralytics, device) if roles else {}
    release_memory(torch)
    maps = estimate_depth(video, moments.values(), config, ultralytics, device)
    release_memory(torch)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as staging:
        pending = Path(staging) / output.name
        pending.mkdir()
        events = [{"type": name, "frame": index, "origin": "automatico"}
                  for name, index in (("PASS_START", result.release), ("PASS_RECEIVED", result.reception))
                  if index is not None]
        manifest = {
            "source": str(video), "start": start, "end": end, "video": info, "config": config,
            "config_signature": signature, "ultralytics": ultralytics.__version__, "torch": torch.__version__,
            "device": device, "pass": {**asdict(result), "status": result.status}, "events": events,
            "lost_ball": [frame["index"] for frame in frames if frame["ball"] is None], "depth_frames": moments,
        }
        write_json(pending / "analise.json", manifest)
        write_json(pending / "quadros.json", frames)
        if masks:
            np.savez_compressed(pending / "mascaras.npz", **{
                f"{index}_{track}": mask for index, players in masks.items() for track, mask in players.items()
            })
        export_pass(pending / "resultado.csv", output.name, result)
        export_replay(pending / "replay.mp4", video, info, frames, masks, result, config["pose_conf"])
        export_evidence(pending / "evidencias", video, frames, masks, maps, moments, result, config["pose_conf"])
        if evaluation_reference is not None:
            from .evaluation import compare

            write_json(pending / "avaliacao.json", compare(evaluation_reference, frames, result, info["fps"]))
        pending.rename(output)
    print(f"{result.status} | {len(manifest['lost_ball'])}/{len(frames)} quadros sem bola | {output}", flush=True)
    if result.reason:
        print(result.reason, flush=True)
    return manifest
