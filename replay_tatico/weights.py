import tempfile
import urllib.request
from pathlib import Path

from .video import file_hash


ASSET_RELEASE = "https://github.com/ultralytics/assets/releases/download/v8.4.0"
OFFICIAL_WEIGHTS = {
    "yolo26n.pt": "9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef",
    "yolo26n-pose.pt": "eb3bb8268828aeaf515cec23a4bfafd793944a86fe9af94ba7823609c14522a9",
    "yolo26n-seg.pt": "361fbfabab285c3237700b6bb91d7ecfa602cd945fffda8dbe1242829b71e73f",
    "yolo26n-depth.pt": "befed1b8561d8b2eaa66274b070cdfc9c44853bda6d6d62a04759f9383af74e9",
}
SPECIALIST_NAME = "football-ball-detection.pt"
SPECIALIST_HASH = "678fbad05134f19c5094cb8d273812ec9c6691228180d46832551ecf99ed2912"


def prepare_weights():
    import gdown

    directory = Path("models")
    directory.mkdir(exist_ok=True)
    for filename, expected in {**OFFICIAL_WEIGHTS, SPECIALIST_NAME: SPECIALIST_HASH}.items():
        path = directory / filename
        if not path.exists():
            with tempfile.TemporaryDirectory(dir=directory) as staging:
                downloaded = Path(staging) / filename
                if filename == SPECIALIST_NAME:
                    gdown.download(id="1isw4wx-MK9h9LMr36VvIWlJD6ppUvw7V", output=str(downloaded), use_cookies=False)
                else:
                    urllib.request.urlretrieve(f"{ASSET_RELEASE}/{filename}", downloaded)
                if file_hash(downloaded) != expected:
                    raise ValueError(f"SHA-256 divergente para {filename}.")
                downloaded.replace(path)
        if file_hash(path) != expected:
            raise ValueError(f"SHA-256 divergente para o peso local {filename}.")
        print(f"{filename}: SHA-256 verificado")
