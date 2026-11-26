import gc
import os
from math import dist
from pathlib import Path

import numpy as np

from .pass_analysis import associate, player_height
from .video import frame_at, open_video


MODEL_DIR = Path("models")


def runtime(device):
    config_dir = (Path(".cache") / "ultralytics").resolve()
    config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(config_dir))
    os.environ.setdefault("YOLO_AUTOINSTALL", "false")
    import torch
    import ultralytics

    if device == "auto":
        device = "0" if torch.cuda.is_available() else "cpu"
    if device != "cpu" and not torch.cuda.is_available():
        raise ValueError("CUDA indisponível. Use --dispositivo cpu ou instale o PyTorch com CUDA.")
    ultralytics.settings.update({"sync": False, "weights_dir": str(MODEL_DIR.resolve())})
    return torch, ultralytics, device


def model_for(ultralytics, name, task):
    path = MODEL_DIR / name
    if not path.is_file():
        raise ValueError(f"Peso ausente: {path}. Execute o comando preparar-modelos.")
    return ultralytics.YOLO(str(path), task=task)


def release_memory(torch):
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def track_players(video, frames, config, ultralytics, device):
    model = model_for(ultralytics, config["weights"]["detect"], "detect")
    with open_video(video) as capture:
        for frame in frames:
            result = model.track(
                frame_at(capture, frame["index"]),
                persist=True, tracker=config["tracker"], classes=[0], conf=0.1,
                imgsz=config["player_imgsz"], device=device, verbose=False,
            )[0]
            boxes = result.boxes
            if boxes is not None and boxes.id is not None:
                ids = boxes.id.int().cpu().tolist()
                frame["players"] = dict(zip(ids, boxes.xyxy.cpu().tolist()))
            frame["player_detections_without_id"] = len(boxes) if boxes is not None and boxes.id is None else 0


def detect_ball(video, frames, config, ultralytics, device):
    model = model_for(ultralytics, config["weights"]["ball"], "detect")
    last_point = None
    last_index = -10
    with open_video(video) as capture:
        for frame in frames:
            image = frame_at(capture, frame["index"])
            result = model.predict(
                image, classes=[config["ball_class"]], conf=config["ball_conf"],
                imgsz=config["ball_imgsz"], device=device, verbose=False,
            )[0]
            if result.boxes is None or not len(result.boxes):
                continue
            positions = result.boxes.xywh[:, :2].cpu().numpy()
            confidence = result.boxes.conf.cpu().numpy()
            scores = confidence.copy()
            gap = frame["index"] - last_index
            if last_point is not None and gap <= 3:
                distance = np.linalg.norm(positions - last_point, axis=1)
                tolerance = 0.035 * image.shape[1] * gap
                scores -= 0.16 * np.minimum(distance / tolerance, 2)
            index = int(np.argmax(scores))
            position = positions[index]
            frame["ball"] = position.tolist()
            frame["ball_confidence"] = float(confidence[index])
            last_point, last_index = position, frame["index"]


def estimate_pose(video, frames, config, ultralytics, device):
    model = model_for(ultralytics, config["weights"]["pose"], "pose")
    with open_video(video) as capture:
        for offset, frame in enumerate(frames):
            neighborhood = [near["ball"] for near in frames[max(0, offset - 3):offset + 4] if near["ball"]]
            if not neighborhood or not frame["players"]:
                continue
            ranked = []
            for track, box in frame["players"].items():
                foot = ((box[0] + box[2]) / 2, box[3])
                score = min(dist(foot, xy) for xy in neighborhood) / player_height(box)
                if score <= 1.5:
                    ranked.append((score, track))
            if not ranked:
                continue
            image = frame_at(capture, frame["index"])
            crops = [player_crop(image, track, frame["players"][track]) for _, track in sorted(ranked)[:4]]
            predictions = model.predict([crop[0] for crop in crops], classes=[0], conf=0.2,
                                        imgsz=config["pose_imgsz"], device=device, verbose=False)
            for (_, x, y, track), result in zip(crops, predictions):
                if result.boxes is None or result.keypoints is None:
                    continue
                boxes = [[a + x, b + y, c + x, d + y] for a, b, c, d in result.boxes.xyxy.cpu().tolist()]
                matches = associate(frame["players"], boxes, config["association_iou"])
                if track not in matches:
                    continue
                keypoints = result.keypoints.data[matches[track]].cpu().tolist()
                frame["poses"][track] = [[u + x, v + y, confidence] for u, v, confidence in keypoints]


def player_crop(image, track, box):
    x1, y1, x2, y2 = box
    padding = max(8, (y2 - y1) * 0.28)
    left = max(0, round(x1 - padding))
    top = max(0, round(y1 - padding))
    right = min(image.shape[1], round(x2 + padding))
    bottom = min(image.shape[0], round(y2 + padding))
    return image[top:bottom, left:right], left, top, track


def segment_frames(video, frames, selected_ids, config, ultralytics, device):
    model = model_for(ultralytics, config["weights"]["segment"], "segment")
    masks = {}
    with open_video(video) as capture:
        for frame in frames:
            tracked = {track: box for track, box in frame["players"].items() if track in selected_ids}
            if not tracked:
                continue
            image = frame_at(capture, frame["index"])
            result = model.predict(
                image, classes=[0], retina_masks=True, imgsz=config["segment_imgsz"],
                device=device, verbose=False,
            )[0]
            if result.masks is None:
                continue
            assignments = associate(frame["players"], result.boxes.xyxy.cpu().tolist(), config["association_iou"])
            masks[frame["index"]] = {
                track: result.masks.data[index].cpu().numpy().astype(bool)
                for track, index in assignments.items() if track in tracked
            }
    return masks


def estimate_depth(video, indices, config, ultralytics, device):
    model = model_for(ultralytics, config["weights"]["depth"], "depth")
    maps = {}
    with open_video(video) as capture:
        for index in indices:
            image = frame_at(capture, index)
            result = model.predict(image, imgsz=config["depth_imgsz"], device=device, verbose=False)[0]
            depth = result.depth.data.cpu().numpy()
            if depth.shape != image.shape[:2]:
                raise ValueError("O mapa de profundidade não tem a geometria do quadro original.")
            maps[index] = depth
    return maps
