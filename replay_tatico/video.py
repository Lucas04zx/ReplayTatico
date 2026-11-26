import hashlib
import math
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps: float
    frames: int

    @property
    def duration(self):
        return self.frames / self.fps


@contextmanager
def open_video(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Arquivo não encontrado: {path}")
    capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    try:
        if not capture.isOpened():
            raise ValueError(f"Vídeo inválido ou codec indisponível: {path}")
        yield capture
    finally:
        capture.release()


def video_info(capture):
    fps = capture.get(cv2.CAP_PROP_FPS)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if not math.isfinite(fps) or fps <= 0 or min(width, height, frames) <= 0:
        raise ValueError("O vídeo não informa resolução, FPS e quantidade de quadros válidos.")
    return VideoInfo(width, height, fps, frames)


def frame_at(capture, index):
    if int(capture.get(cv2.CAP_PROP_POS_FRAMES)) != index:
        if not capture.set(cv2.CAP_PROP_POS_FRAMES, index):
            raise ValueError(f"Não foi possível posicionar no quadro {index}.")
    ok, image = capture.read()
    if not ok or int(capture.get(cv2.CAP_PROP_POS_FRAMES)) != index + 1:
        raise ValueError(f"Não foi possível ler o quadro original {index}.")
    return image


def file_hash(path):
    with Path(path).open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def probe(path):
    with open_video(path) as capture:
        info = video_info(capture)
        timestamps = []
        for index in range(info.frames):
            frame_at(capture, index)
            timestamps.append(capture.get(cv2.CAP_PROP_POS_MSEC))
        if capture.read()[0]:
            raise ValueError("A contagem de quadros do vídeo diverge da decodificação.")
    period_ms = 1000 / info.fps
    max_deviation = max(
        (abs(end - start - period_ms) for start, end in zip(timestamps, timestamps[1:])),
        default=0,
    )
    return {
        **asdict(info),
        "duration_seconds": info.duration,
        "max_frame_period_deviation_ms": round(max_deviation, 4),
        "constant_fps": max_deviation <= 1.1,
        "sha256": file_hash(path),
    }


def inspect(path, start=0, end=None):
    """Avança pelo vídeo de origem, sem carregar modelos nem resultados."""
    with open_video(path) as capture:
        info = video_info(capture)
        end = info.frames - 1 if end is None else end
        if not 0 <= start <= end < info.frames:
            raise ValueError(f"O intervalo deve estar entre 0 e {info.frames - 1}.")
        index = start
        playing = False
        window = "Replay Tatico | Inspecao do original"
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window, min(info.width, 1280), min(info.height, 720))
        try:
            while True:
                image = frame_at(capture, index)
                cv2.rectangle(image, (0, 0), (810, 42), (12, 12, 12), -1)
                label = f"Q {index} / {end}  {index / info.fps:.3f}s | A/D: quadro  J/L: segundo  Espaco: tocar  Q: sair"
                cv2.putText(image, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.imshow(window, image)
                key = cv2.waitKeyEx(round(1000 / info.fps) if playing else 40)
                if key in (27, ord("q")) or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                    break
                if key == ord(" "):
                    playing = not playing
                elif key in (ord("a"), ord("d"), ord("j"), ord("l"), 2424832, 2555904):
                    jump = {ord("a"): -1, ord("d"): 1, ord("j"): -round(info.fps),
                            ord("l"): round(info.fps), 2424832: -1, 2555904: 1}[key]
                    index = min(end, max(start, index + jump))
                    playing = False
                elif playing and index < end:
                    index += 1
                elif index == end:
                    playing = False
        finally:
            cv2.destroyAllWindows()
