import csv
import json
import unittest
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "demo" / "data"


class DemoDataTests(unittest.TestCase):
    def test_replay_indices_and_results_match_the_downloads(self):
        catalog = json.loads((DATA / "clipes.json").read_text(encoding="utf-8"))
        self.assertEqual([clip["id"] for clip in catalog], ["ajuste", "avaliacao-tp2"])
        for clip in catalog:
            name = clip["id"]
            with self.subTest(clip=name):
                data = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
                result = data["pass"]
                with (DATA / f"{name}-resultado.csv").open(newline="", encoding="utf-8") as stream:
                    row, = csv.DictReader(stream)
                self.assertEqual([frame["index"] for frame in data["frames"]],
                                 list(range(data["start"], data["end"] + 1)))
                self.assertEqual(row["resultado"], result["status"])
                if result["release"] is not None:
                    self.assertEqual((int(row["quadro_saida"]), int(row["quadro_recepcao"])),
                                     (result["release"], result["reception"]))
                    self.assertAlmostEqual(float(row["duracao_segundos"]), result["seconds"])
                else:
                    self.assertEqual(row["quadro_saida"], "")
                    self.assertEqual(row["quadro_recepcao"], "")
                    self.assertEqual(row["duracao_segundos"], "")

    def test_evaluation_depth_and_events_keep_manual_provenance(self):
        data = json.loads((DATA / "avaliacao-tp2.json").read_text(encoding="utf-8"))
        self.assertEqual(data["pass"]["status"], "INCONCLUSIVO")
        self.assertEqual([(event["frame"], event["origin"]) for event in data["events"]],
                         [(411, "referência manual"), (456, "referência manual")])
        self.assertEqual(data["reference"]["seconds"], 1.8)
        self.assertIsNone(data["frames"][409 - data["start"]]["ball"])
        self.assertIsNone(data["frames"][410 - data["start"]]["ball"])
        self.assertEqual([entry["frame"] for entry in data["depth"]], [411, 433, 456])
        with (DATA / "avaliacao-tp2-profundidade.csv").open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([(entry["frame"], sample["id"], sample["median"])
                          for entry in data["depth"] for sample in entry["samples"]],
                         [(int(row["quadro"]), int(row["id"]), float(row["mediana_modelo"])) for row in rows])
