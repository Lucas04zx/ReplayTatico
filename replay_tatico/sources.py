from pathlib import Path

SOURCES = {
    "0bfacc_0.mp4": "12TqauVZ9tLAv8kWxTTBFWtgt2hNQ4_ZF",
    "2e57b9_0.mp4": "19PGw55V8aA6GZu5-Aac5_9mCy3fNxmEf",
    "08fd33_0.mp4": "1OG8K6wqUw9t7lp9ms1M48DxRhwTYciK-",
    "573e61_0.mp4": "1yYPKuXbHsCxqjA9G-S6aeR2Kcnos8RPU",
}


def fetch(names, directory):
    import gdown

    from .video import probe

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        destination = directory / name
        if not destination.exists():
            partial = destination.with_suffix(".download")
            gdown.download(id=SOURCES[name], output=str(partial), use_cookies=False)
            probe(partial)
            partial.replace(destination)
        print(name, probe(destination))
