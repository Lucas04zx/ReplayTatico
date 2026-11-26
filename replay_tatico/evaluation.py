import math
import tempfile
from pathlib import Path

from .exports import export_evidence, export_replay, write_json
from .inference import estimate_depth, release_memory, runtime, segment_frames
from .pass_analysis import Pass, player_height
from .pipeline import FROZEN_CONFIG, depth_moments, identity_digest, read_json
from .video import probe


EVALUATION_CLIP = Path("configs/trecho-avaliacao.json")


def frozen_experiment():
    if not FROZEN_CONFIG.is_file() or not EVALUATION_CLIP.is_file():
        raise ValueError("O trecho e a configuração de avaliação ainda não foram congelados.")
    clip = read_json(EVALUATION_CLIP)
    signature = identity_digest(FROZEN_CONFIG, read_json(FROZEN_CONFIG))
    if signature != clip["config_signature"]:
        raise ValueError("A configuração, o rastreador ou os pesos divergem do congelamento.")
    return clip


def validate_reference(reference_path, info, start, end, signature):
    clip = frozen_experiment()
    if (info["sha256"], start, end, signature) != (clip["video_sha256"], clip["start"], clip["end"], clip["config_signature"]):
        raise ValueError("O vídeo, o intervalo ou os parâmetros divergem do registro congelado.")
    reference = read_json(reference_path)
    if any(reference.get(key) != clip[key] for key in ("video_sha256", "start", "end", "config_signature")):
        raise ValueError("A anotação manual não corresponde ao experimento congelado.")
    return reference


def record_reference(path, release, reception, passer, receiver):
    clip = frozen_experiment()
    info = probe(clip["video"])
    if info["sha256"] != clip["video_sha256"]:
        raise ValueError("O vídeo de origem não corresponde à impressão SHA-256 do trecho congelado.")
    if not clip["start"] < release < reception <= clip["end"]:
        raise ValueError("Selecione saída e recepção dentro do trecho, com recepção posterior à saída.")
    for x, y in (passer, receiver):
        if not math.isfinite(x) or not math.isfinite(y) or not (0 <= x < info["width"] and 0 <= y < info["height"]):
            raise ValueError("Marque um ponto no interior de cada atleta no quadro original.")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError(f"Já existe uma referência em {path}.")
    write_json(path, {
        **clip, "release": release, "reception": reception,
        "passer_xy": passer, "passer_mark_frame": release - 1,
        "receiver_xy": receiver, "receiver_mark_frame": reception,
    })


def track_at(frame, point):
    x, y = point
    matches = []
    for track, box in frame["players"].items():
        x1, y1, x2, y2 = box
        if x1 <= x <= x2 and y1 <= y <= y2:
            center = ((x1 + x2) / 2, (y1 + y2) / 2)
            matches.append((math.dist(point, center) / player_height(box), track))
    matches.sort()
    if not matches or len(matches) > 1 and matches[1][0] - matches[0][0] < 0.12:
        return None
    return matches[0][1]


def compare(reference_path, frames, result, fps):
    manual = read_json(reference_path)
    by_index = {frame["index"]: frame for frame in frames}
    passer = track_at(by_index[manual["passer_mark_frame"]], manual["passer_xy"])
    receiver = track_at(by_index[manual["receiver_mark_frame"]], manual["receiver_xy"])
    release = manual["release"]
    reception = manual["reception"]
    seconds = (reception - release) / fps
    return {
        "referencia_manual": manual,
        "id_associado_ao_passador_manual": passer,
        "id_associado_ao_recebedor_manual": receiver,
        "mesmo_passador": None if passer is None or result.passer is None else passer == result.passer,
        "mesmo_recebedor": None if receiver is None or result.receiver is None else receiver == result.receiver,
        "erro_saida_quadros": None if result.release is None else result.release - release,
        "erro_recepcao_quadros": None if result.reception is None else result.reception - reception,
        "duracao_manual_segundos": seconds,
        "diferenca_duracao_segundos": None if result.seconds is None else result.seconds - seconds,
        "convencao_erro": "automático menos manual",
    }


def export_reference_evidence(analysis_dir, device):
    directory = Path(analysis_dir)
    destination = directory / "referencia-visual"
    if destination.exists():
        raise ValueError(f"As evidências já existem em {destination}.")
    experiment = frozen_experiment()
    manifest = read_json(directory / "analise.json")
    comparison = read_json(directory / "avaliacao.json")
    reference = comparison["referencia_manual"]
    if any(reference.get(key) != experiment[key] for key in ("video_sha256", "start", "end", "config_signature")):
        raise ValueError("A análise não corresponde à referência do trecho congelado.")
    info = probe(experiment["video"])
    if (manifest["video"]["sha256"], manifest["start"], manifest["end"], manifest["config_signature"]) != (
        info["sha256"], experiment["start"], experiment["end"], experiment["config_signature"]
    ):
        raise ValueError("O vídeo ou os dados de análise divergem do trecho congelado.")
    config = read_json(FROZEN_CONFIG)
    frames = read_json(directory / "quadros.json")
    for frame in frames:
        frame["players"] = {int(track): box for track, box in frame["players"].items()}
        frame["poses"] = {int(track): pose for track, pose in frame["poses"].items()}
    roles = Pass(
        comparison["id_associado_ao_passador_manual"], comparison["id_associado_ao_recebedor_manual"],
        reference["release"], reference["reception"], comparison["duracao_manual_segundos"],
    )
    moments = depth_moments(roles, experiment["start"], experiment["end"])
    mask_indices = set(moments.values()) | set(range(roles.release - 4, roles.release + 5))
    selected = [frame for frame in frames if frame["index"] in mask_indices]
    tracks = {track for track in (roles.passer, roles.receiver) if track is not None}
    torch, ultralytics, device = runtime(device)
    video = experiment["video"]
    masks = segment_frames(video, selected, tracks, config, ultralytics, device) if tracks else {}
    release_memory(torch)
    maps = estimate_depth(video, moments.values(), config, ultralytics, device)
    release_memory(torch)
    with tempfile.TemporaryDirectory(dir=directory) as staging:
        pending = Path(staging) / destination.name
        pending.mkdir()
        write_json(pending / "origem.json", {
            "origem": "referencia_manual_pos_avaliacao",
            "passador_associado": roles.passer, "recebedor_associado": roles.receiver,
            "quadros": moments,
            "continuidade_ids": {
                str(track): [frame["index"] for frame in frames if track not in frame["players"]]
                for track in sorted(tracks)
            },
        })
        export_replay(pending / "replay-referencia.mp4", video, info, frames, masks, roles, config["pose_conf"],
                      manual=True)
        export_evidence(pending / "evidencias", video, frames, masks, maps, moments, roles, config["pose_conf"])
        pending.rename(destination)
    print(f"Evidências baseadas na referência manual: {destination}", flush=True)
