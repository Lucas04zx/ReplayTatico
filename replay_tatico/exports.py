import csv
import json
from contextlib import contextmanager
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

from .video import frame_at, open_video, video_info


RESULT_FIELDS = (
    "clipe", "id_passador", "id_recebedor", "quadro_saida", "quadro_recepcao",
    "duracao_segundos", "resultado",
)
DEPTH_FIELDS = ("momento", "quadro", "papel", "id", "mediana_modelo", "pixels_validos", "metodo")
WHITE = (245, 245, 245)
ORANGE = (36, 133, 255)
BLUE = (255, 184, 62)
GREEN = (118, 208, 105)
GRAY = (177, 177, 177)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(fields)
        writer.writerows(rows)


def export_pass(path, clip, result):
    write_csv(path, RESULT_FIELDS, [(clip, result.passer, result.receiver, result.release, result.reception,
                                    None if result.seconds is None else f"{result.seconds:.6f}", result.status)])


def color_for(track, result):
    if track == result.passer:
        return ORANGE
    if track == result.receiver:
        return BLUE
    return GRAY


def point(coordinates):
    return tuple(round(value) for value in coordinates[:2])


def label(image, text, xy, color=WHITE, scale=0.62):
    cv2.putText(image, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, (12, 12, 12), 4, cv2.LINE_AA)
    cv2.putText(image, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def draw_box(image, box, track, color):
    x1, y1, x2, y2 = map(round, box)
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
    label(image, f"#{track}", (x1, max(15, y1 - 5)), color, 0.48)


def draw_mask(image, mask, color):
    image[mask] = np.rint(image[mask] * 0.55 + np.array(color) * 0.45).astype(np.uint8)
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image, contours, -1, color, 1, cv2.LINE_AA)


def draw_pose(image, pose, confidence):
    hidden = []
    for side, indices in (("E", (11, 13, 15)), ("D", (12, 14, 16))):
        for index, name in zip(indices, ("quadril", "joelho", "tornozelo")):
            if len(pose) <= index or pose[index][2] < confidence:
                hidden.append(f"{name} {side}")
            else:
                cv2.circle(image, point(pose[index]), 4, ORANGE, -1, cv2.LINE_AA)
        for start, end in zip(indices, indices[1:]):
            if len(pose) > end and min(pose[start][2], pose[end][2]) >= confidence:
                cv2.line(image, point(pose[start]), point(pose[end]), ORANGE, 2, cv2.LINE_AA)
    if hidden:
        label(image, "Pose baixa/ausente: " + ", ".join(hidden), (14, image.shape[0] - 16), ORANGE, 0.5)


def render_frame(image, frame, history, masks, result, pose_conf, layers=None, manual=False):
    if layers is None:
        layers = {"mask", "boxes", "pose", "ball", "hud"}
    index = frame["index"]
    if "mask" in layers:
        for track, mask in masks.items():
            draw_mask(image, mask, color_for(track, result))
    if "boxes" in layers:
        for track, box in frame["players"].items():
            draw_box(image, box, track, color_for(track, result))
    if "pose" in layers and result.release is not None and abs(index - result.release) <= 12:
        draw_pose(image, frame["poses"].get(result.passer, []), pose_conf)
    if "ball" in layers:
        for first, second in zip(history, history[1:]):
            if first is not None and second is not None:
                cv2.line(image, point(first), point(second), ORANGE, 2, cv2.LINE_AA)
        if frame["ball"] is not None:
            cv2.circle(image, point(frame["ball"]), 8, ORANGE, 2, cv2.LINE_AA)
    if "hud" in layers:
        event = {result.release: " | SAIDA", result.reception: " | RECEPCAO"}.get(index, "")
        ball = "Bola detectada" if frame["ball"] else "Bola perdida"
        label(image, f"Q {index}  |  {ball}{event}", (14, 28))
        duration = "" if result.seconds is None else f"  |  {result.seconds:.3f} s"
        status = "EVENTOS DA REFERENCIA MANUAL" if manual else result.status
        label(image, status + duration, (14, 54), scale=0.54)
    return image


@contextmanager
def mp4_writer(path, width, height, fps):
    writer = imageio_ffmpeg.write_frames(
        str(path), (width, height), fps=fps, codec="libx264", pix_fmt_in="bgr24",
        macro_block_size=1, output_params=[
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-crf", "18", "-movflags", "+faststart",
        ],
    )
    writer.send(None)
    try:
        yield writer
    finally:
        writer.close()


def export_replay(path, video, info, frames, masks, result, pose_conf, manual=False):
    with open_video(video) as capture, mp4_writer(path, info["width"], info["height"], info["fps"]) as writer:
        history = []
        for frame in frames:
            image = frame_at(capture, frame["index"])
            history.append(frame["ball"])
            annotated = render_frame(image, frame, history[-30:], masks.get(frame["index"], {}), result, pose_conf,
                                     manual=manual)
            writer.send(np.ascontiguousarray(annotated))
    with open_video(path) as capture:
        encoded = video_info(capture)
        if encoded.frames != len(frames) or abs(encoded.fps - info["fps"]) > 0.01:
            raise ValueError("O MP4 exportado diverge da contagem ou do FPS do trecho.")
        frame_at(capture, encoded.frames - 1)


def save_image(path, image):
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise ValueError(f"Falha ao gerar {path.name}.")
    path.write_bytes(encoded.tobytes())


def sample_depth(depth, mask, box):
    method = "mascara"
    if mask is None:
        if box is None:
            return None, 0, "sem_ID_no_quadro"
        method = "interior_caixa"
        x1, y1, x2, y2 = box
        inset_x = (x2 - x1) * 0.25
        inset_y = (y2 - y1) * 0.2
        left = max(0, round(x1 + inset_x))
        top = max(0, round(y1 + inset_y))
        right = min(depth.shape[1], round(x2 - inset_x))
        bottom = min(depth.shape[0], round(y2 - inset_y))
        values = depth[top:bottom, left:right].ravel()
    else:
        values = depth[mask]
    valid = values[np.isfinite(values) & (values > 0)]
    return (float(np.median(valid)), int(valid.size), method) if valid.size else (None, 0, method)


def export_evidence(directory, video, frames, masks, maps, depth_moments, result, pose_conf):
    directory.mkdir(exist_ok=True)
    indexed = {frame["index"]: frame for frame in frames}
    depth_rows = []
    with open_video(video) as capture:
        for moment, index in depth_moments.items():
            frame = indexed[index]
            image = frame_at(capture, index)
            save_image(directory / f"{moment}-{index}-rgb.png", image)
            depth = maps[index]
            valid = np.isfinite(depth) & (depth > 0)
            normalized = np.zeros(depth.shape, np.uint8)
            if valid.any():
                low, high = np.percentile(depth[valid], (2, 98))
                normalized[valid] = np.clip((depth[valid] - low) / max(0.001, high - low) * 255, 0, 255).astype(np.uint8)
            colored = cv2.applyColorMap(normalized, cv2.COLORMAP_VIRIDIS)
            colored[~valid] = 0
            for role, track in (("passador", result.passer), ("recebedor", result.receiver)):
                box = frame["players"].get(track)
                mask = masks.get(index, {}).get(track)
                median, pixels, method = sample_depth(depth, mask, box)
                depth_rows.append((moment, index, role, track, median, pixels, method))
                if box is not None:
                    draw_box(colored, box, track, color_for(track, result))
            label(colored, "Profundidade estimada | escuro: perto  claro: longe", (14, 28))
            save_image(directory / f"{moment}-{index}-profundidade.png", colored)
        if result.release is not None:
            start, end = frames[0]["index"], frames[-1]["index"]
            for moment, offset in (("preparacao", -3), ("chute", 0), ("finalizacao", 3)):
                index = min(end, max(start, result.release + offset))
                image = frame_at(capture, index)
                draw_pose(image, indexed[index]["poses"].get(result.passer, []), pose_conf)
                label(image, f"{moment.upper()} | Q {index} | ID {result.passer}", (14, 28))
                save_image(directory / f"pose-{moment}-{index}.png", image)
        for index, frame_masks in masks.items():
            if not frame_masks:
                continue
            track, mask = next(iter(frame_masks.items()))
            image = frame_at(capture, index)
            boxed = image.copy()
            draw_box(boxed, indexed[index]["players"][track], track, color_for(track, result))
            draw_mask(image, mask, color_for(track, result))
            save_image(directory / f"segmentacao-{index}-caixa.png", boxed)
            save_image(directory / f"segmentacao-{index}-mascara.png", image)
            break
    write_csv(directory / "profundidade.csv", DEPTH_FIELDS, depth_rows)
