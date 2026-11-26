import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

from replay_tatico.evaluation import compare
from replay_tatico.exports import RESULT_FIELDS, export_pass, sample_depth, write_json
from replay_tatico.pass_analysis import Pass, associate, identify_pass
from replay_tatico.pipeline import read_json


def pose(x, ankle_x):
    joints = [[0.0, 0.0, 0.0] for _ in range(17)]
    joints[11], joints[13], joints[15] = [x, 62, 1], [x, 80, 1], [ankle_x, 100, 1]
    return joints


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.config = read_json("configs/ajuste.json")
        points = [20, 20, 36, 50, 64, 78, 91, 96, 96]
        self.frames = [
            {
                "index": 50 + index,
                "ball": (x, 100),
                "players": {4: [10, 60, 30, 100], 8: [90, 60, 110, 100]},
                "poses": {4: pose(20, 15 if index == 0 else 20), 8: pose(100, 100)},
            }
            for index, x in enumerate(points)
        ]

    def test_pass_uses_original_frame_indices_and_fps(self):
        result = identify_pass(self.frames, 25, self.config)
        self.assertEqual((result.passer, result.receiver, result.release, result.reception), (4, 8, 52, 56))
        self.assertAlmostEqual(result.seconds, 4 / 25)

    def test_reception_with_ball_occluded_is_inconclusive(self):
        self.frames[5]["ball"] = None
        result = identify_pass(self.frames, 25, self.config)
        self.assertEqual(result.status, "INCONCLUSIVO")
        self.assertIsNone(result.reception)
        self.assertIn("Bola perdida", result.reason)

    def test_ambiguous_pose_assignment_is_omitted(self):
        boxes = {1: [0, 0, 20, 40], 2: [1, 0, 21, 40], 3: [40, 0, 60, 40]}
        self.assertEqual(associate(boxes, [[.5, 0, 20.5, 40], [40, 0, 60, 40]], .3), {3: 1})

    def test_depth_uses_only_positive_finite_mask_pixels(self):
        depth = np.array([[1, 7, 0], [3, np.nan, np.inf]])
        mask = np.array([[True, False, True], [True, True, True]])
        self.assertEqual(sample_depth(depth, mask, None), (2.0, 2, "mascara"))
        self.assertEqual(sample_depth(depth, None, None), (None, 0, "sem_ID_no_quadro"))

    def test_academic_csv_schema_and_missing_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resultado.csv"
            export_pass(path, "teste", Pass(passer=4, release=44))
            with path.open(newline="", encoding="utf-8") as file:
                header, row = list(csv.reader(file))
            self.assertEqual(tuple(header), RESULT_FIELDS)
            self.assertEqual(row, ["teste", "4", "", "44", "", "", "INCONCLUSIVO"])

    def test_comparison_keeps_manual_and_automatic_results_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manual.json"
            write_json(path, {"release": 52, "reception": 56, "passer_mark_frame": 51,
                              "receiver_mark_frame": 56, "passer_xy": [20, 80], "receiver_xy": [99, 80]})
            comparison = compare(path, self.frames, Pass(), 25)
            self.assertEqual(comparison["id_associado_ao_passador_manual"], 4)
            self.assertEqual(comparison["id_associado_ao_recebedor_manual"], 8)
            self.assertAlmostEqual(comparison["duracao_manual_segundos"], .16)
            self.assertIsNone(comparison["erro_saida_quadros"])
            self.assertIsNone(comparison["mesmo_recebedor"])
