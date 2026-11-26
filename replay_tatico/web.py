import io
import tempfile
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, abort, jsonify, render_template, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from .evaluation import EVALUATION_CLIP, frozen_experiment, record_reference
from .exports import render_frame
from .pass_analysis import Pass
from .pipeline import read_json
from .video import file_hash, frame_at, open_video, video_info


ROOT = Path.cwd()
RAW = ROOT / "data" / "raw"
IMPORTS = ROOT / "data" / "imports"
OUTPUTS = ROOT / "outputs"
REFERENCE = ROOT / "data" / "annotations" / "avaliacao.json"
VIDEO_FORMATS = {".mp4", ".mov", ".mkv", ".avi"}
LAYERS = {"boxes", "pose", "ball", "mask", "hud"}


def clips():
    catalog = []
    for prefix, folder in (("raw", RAW), ("import", IMPORTS)):
        for path in sorted(folder.glob("*")):
            if path.is_file() and path.suffix.lower() in VIDEO_FORMATS:
                catalog.append({"id": f"{prefix}-{path.name}", "label": path.name, "source": path})
    for manifest in sorted(OUTPUTS.glob("*/analise.json")):
        metadata = read_json(manifest)
        source = Path(metadata["source"])
        if source.is_file():
            catalog.append({
                "id": f"run-{manifest.parent.name}", "label": manifest.parent.name,
                "source": source, "run": manifest.parent,
            })
    if EVALUATION_CLIP.is_file():
        experiment = read_json(EVALUATION_CLIP)
        source = Path(experiment["video"])
        if source.is_file():
            catalog.insert(0, {"id": "avaliacao", "label": "Avaliação · anotação independente", "source": source,
                               "experiment": experiment})
    return catalog


def find_clip(identifier):
    return next((clip for clip in clips() if clip["id"] == identifier), None) or abort(404)


@lru_cache(maxsize=8)
def source_info(source, changed):
    with open_video(source) as capture:
        return video_info(capture)


@lru_cache(maxsize=8)
def analysis_data(directory):
    manifest = read_json(directory / "analise.json")
    frames = read_json(directory / "quadros.json")
    for frame in frames:
        frame["players"] = {int(track): box for track, box in frame["players"].items()}
        frame["poses"] = {int(track): pose for track, pose in frame["poses"].items()}
    result = Pass(**{key: value for key, value in manifest["pass"].items() if key != "status"})
    return manifest, frames, result


def clip_meta(clip):
    info = source_info(clip["source"], clip["source"].stat().st_mtime_ns)
    meta = {"id": clip["id"], "label": clip["label"], "fps": info.fps, "width": info.width, "height": info.height,
            "start": 0, "end": info.frames - 1, "events": [], "has_analysis": "run" in clip}
    if "experiment" in clip:
        meta.update({key: clip["experiment"][key] for key in ("start", "end")})
        meta["reference_saved"] = REFERENCE.exists()
    if "run" in clip:
        manifest, frames, result = analysis_data(clip["run"])
        meta.update({key: manifest[key] for key in ("start", "end", "events", "pass")})
        reference_origin = clip["run"] / "referencia-visual" / "origem.json"
        moments = manifest["depth_frames"]
        if reference_origin.is_file():
            moments = read_json(reference_origin)["quadros"]
            meta["depth_origin"] = "manual"
        meta["comparison"] = (clip["run"] / "avaliacao.json").is_file()
        meta["depth"] = [
            {"name": name, "frame": index,
             "rgb": f"{name}-{index}-rgb.png", "map": f"{name}-{index}-profundidade.png"}
            for name, index in moments.items()
        ]
        timeline = {frame["index"]: frame for frame in frames}
        meta["events"] = [event.copy() for event in meta["events"]]
        for event in meta["events"]:
            frame = timeline[event["frame"]]
            track = result.passer if event["type"] == "PASS_START" else result.receiver
            box = frame["players"].get(track)
            event["position"] = frame["ball"]
            event["player"] = [(box[0] + box[2]) / 2, box[3]] if box else None
        meta["ball"] = {frame["index"]: frame["ball"] for frame in frames if frame["ball"] is not None}
    return meta


def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024
    app.config["TRUSTED_HOSTS"] = ["127.0.0.1", "localhost", "testserver"]

    @app.errorhandler(ValueError)
    def bad_request(error):
        return jsonify(error=str(error)), 400

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/clipes")
    def catalog():
        return jsonify([{"id": item["id"], "label": item["label"]} for item in clips()])

    @app.get("/api/clipes/<identifier>")
    def metadata(identifier):
        return jsonify(clip_meta(find_clip(identifier)))

    @app.get("/api/clipes/<identifier>/quadros/<int:index>")
    def picture(identifier, index):
        clip = find_clip(identifier)
        info = source_info(clip["source"], clip["source"].stat().st_mtime_ns)
        start, end = 0, info.frames - 1
        if "experiment" in clip:
            start, end = clip["experiment"]["start"], clip["experiment"]["end"]
        elif "run" in clip:
            manifest, frames, result = analysis_data(clip["run"])
            start, end = manifest["start"], manifest["end"]
        if not start <= index <= end:
            abort(404)
        with open_video(clip["source"]) as capture:
            image = frame_at(capture, index)
        if "run" in clip and request.args.get("view") == "technical":
            position = index - start
            history = [item["ball"] for item in frames[max(0, position - 29):position + 1]]
            layers = LAYERS & set(request.args.get("layers", "").split(","))
            masks = {}
            mask_file = clip["run"] / "mascaras.npz"
            if "mask" in layers and mask_file.is_file():
                with np.load(mask_file, allow_pickle=False) as stored:
                    for key in stored.files:
                        frame_index, track = map(int, key.split("_"))
                        if frame_index == index:
                            masks[track] = stored[key]
            render_frame(image, frames[position], history, masks, result, manifest["config"]["pose_conf"], layers)
        if request.args.get("full") != "1" and image.shape[1] > 1280:
            height = round(image.shape[0] * 1280 / image.shape[1])
            image = cv2.resize(image, (1280, height), interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not ok:
            abort(500)
        return send_file(io.BytesIO(encoded.tobytes()), mimetype="image/jpeg", max_age=3600)

    @app.get("/api/clipes/<identifier>/evidencias/<name>")
    def evidence(identifier, name):
        clip = find_clip(identifier)
        if "run" not in clip or Path(name).suffix not in {".png", ".csv"}:
            abort(404)
        directory = clip["run"]
        if request.args.get("origem") == "manual":
            directory = directory / "referencia-visual"
        return send_from_directory(directory / "evidencias", name)

    @app.get("/api/clipes/<identifier>/video")
    def media(identifier):
        clip = find_clip(identifier)
        if request.args.get("view") == "technical":
            if "run" not in clip:
                abort(404)
            return send_file((clip["run"] / "replay.mp4").resolve(), conditional=True)
        return send_file(clip["source"].resolve(), conditional=True)

    @app.get("/api/clipes/<identifier>/exportar/<name>")
    def download(identifier, name):
        clip = find_clip(identifier)
        if "run" not in clip or name not in {
            "replay.mp4", "resultado.csv", "analise.json", "avaliacao.json", "replay-referencia.mp4",
        }:
            abort(404)
        directory = clip["run"] / "referencia-visual" if name == "replay-referencia.mp4" else clip["run"]
        return send_from_directory(directory, name, as_attachment=True)

    @app.post("/api/importar")
    def upload():
        video = request.files.get("video")
        if not video:
            raise ValueError("Selecione um arquivo de vídeo.")
        name = secure_filename(video.filename or "")
        if Path(name).suffix.lower() not in VIDEO_FORMATS:
            raise ValueError("Selecione um vídeo MP4, MOV, MKV ou AVI.")
        IMPORTS.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=IMPORTS) as staging:
            temporary = Path(staging) / name
            video.save(temporary)
            with open_video(temporary) as capture:
                video_info(capture)
                frame_at(capture, 0)
            destination = IMPORTS / name
            if destination.exists():
                if file_hash(destination) != file_hash(temporary):
                    raise ValueError("Já existe um vídeo com esse nome. Renomeie o novo arquivo.")
            else:
                temporary.replace(destination)
        return jsonify(id=f"import-{name}")

    @app.post("/api/avaliacao/referencia")
    def save_reference():
        if not request.is_json:
            abort(415)
        frozen_experiment()
        payload = request.get_json()
        try:
            if any(type(payload[key]) is not int for key in ("release", "reception")):
                raise ValueError
            passer = [float(coord) for coord in payload["passer"]]
            receiver = [float(coord) for coord in payload["receiver"]]
            if len(passer) != 2 or len(receiver) != 2:
                raise ValueError
            release, reception = payload["release"], payload["reception"]
        except (KeyError, TypeError, ValueError):
            raise ValueError("Marque os quadros de saída e recepção e os dois jogadores.") from None
        record_reference(REFERENCE, release, reception, passer, receiver)
        return jsonify(saved=True)

    return app
