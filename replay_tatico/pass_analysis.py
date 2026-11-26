import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Pass:
    passer: int | None = None
    receiver: int | None = None
    release: int | None = None
    reception: int | None = None
    seconds: float | None = None
    reason: str = ""

    @property
    def status(self):
        return "CONCLUIDO" if self.seconds is not None else "INCONCLUSIVO"


def iou(first, second):
    x1, y1, x2, y2 = first
    u1, v1, u2, v2 = second
    intersection = max(0, min(x2, u2) - max(x1, u1)) * max(0, min(y2, v2) - max(y1, v1))
    union = (x2 - x1) * (y2 - y1) + (u2 - u1) * (v2 - v1) - intersection
    return intersection / union if union > 0 else 0


def associate(players, boxes, minimum):
    scores = sorted(
        ((iou(player, box), track, index)
         for track, player in players.items() for index, box in enumerate(boxes)),
        reverse=True,
    )
    assignments = {}
    used = set()
    for score, track, index in scores:
        if score < minimum:
            break
        if track in assignments or index in used:
            continue
        ambiguities = (other for other, other_track, other_index in scores
                       if (track, index) != (other_track, other_index)
                       and (track == other_track or index == other_index))
        if any(other >= score - 0.08 for other in ambiguities):
            continue
        assignments[track] = index
        used.add(index)
    return assignments


def player_height(box):
    return max(1, box[3] - box[1])


def foot_distance(frame, track, point, pose_conf):
    box = frame["players"][track]
    height = player_height(box)
    joints = frame["poses"].get(track, [])
    ankles = [joints[index][:2] for index in (15, 16) if len(joints) > index and joints[index][2] >= pose_conf]
    if not ankles:
        ankles = [((box[0] + box[2]) / 2, box[3])]
    return min(math.dist(foot, point) for foot in ankles) / height


def leg_motion(before, after, track, pose_conf):
    if track not in before["players"] or track not in after["players"]:
        return None
    first = before["poses"].get(track, [])
    second = after["poses"].get(track, [])
    movement = []
    for hip, knee, ankle in ((11, 13, 15), (12, 14, 16)):
        if min(len(first), len(second)) <= ankle:
            continue
        if any(pose[index][2] < pose_conf for pose in (first, second) for index in (hip, knee, ankle)):
            continue
        first_height = player_height(before["players"][track])
        second_height = player_height(after["players"][track])
        for joint in (knee, ankle):
            previous = [(first[joint][axis] - first[hip][axis]) / first_height for axis in (0, 1)]
            current = [(second[joint][axis] - second[hip][axis]) / second_height for axis in (0, 1)]
            movement.append(math.dist(previous, current))
    return max(movement, default=None)


def nearest_player(frame, point, pose_conf):
    candidates = sorted((foot_distance(frame, track, point, pose_conf), track) for track in frame["players"])
    if not candidates or len(candidates) > 1 and candidates[1][0] - candidates[0][0] < 0.07:
        return None
    return candidates[0]


def identify_pass(frames, fps, config):
    contact = config["contact"]
    pose_conf = config["pose_conf"]
    min_flight = max(2, round(config["min_flight_seconds"] * fps))
    max_gap = max(0, round(config["max_gap_seconds"] * fps))
    launch = Pass(reason="Nenhuma saída com bola, ID persistente e movimento de perna suficientes.")
    for index in range(2, len(frames) - 1):
        before, current, following = frames[index - 1:index + 2]
        if any(frame["ball"] is None for frame in (before, current, following)):
            continue
        prior = nearest_player(before, before["ball"], pose_conf)
        if prior is None or prior[0] > contact:
            continue
        distance, passer = prior
        if any(passer not in frame["players"] for frame in (current, following)):
            continue
        separation = foot_distance(current, passer, current["ball"], pose_conf)
        further = foot_distance(following, passer, following["ball"], pose_conf)
        displacement = math.dist(before["ball"], current["ball"]) / player_height(current["players"][passer])
        if separation <= contact or further < config["release"] or further <= separation:
            continue
        if separation - distance < config["min_motion"] or displacement < config["min_motion"]:
            continue
        movement = [
            leg_motion(frames[earlier], frames[later], passer, pose_conf)
            for earlier, later in ((index - 2, index - 1), (index - 1, index), (index, index + 1))
        ]
        if max((value for value in movement if value is not None), default=0) < config["min_leg_motion"]:
            continue
        launch = Pass(passer=passer, release=current["index"], reason="A trajetória termina sem recepção verificável.")
        gap = 0
        for arrival_index in range(index + 1, len(frames) - 1):
            arrival = frames[arrival_index]
            ball = arrival["ball"]
            if ball is None:
                gap += 1
                if gap > max_gap:
                    return Pass(passer=passer, release=current["index"],
                                reason="Perda prolongada da bola durante a trajetória.")
                continue
            candidate = nearest_player(arrival, ball, pose_conf)
            gap_before, gap = gap, 0
            if candidate is None or candidate[0] > contact or candidate[1] == passer:
                continue
            receiver = candidate[1]
            previous = frames[arrival_index - 1]
            next_frame = frames[arrival_index + 1]
            if arrival_index - index < min_flight:
                return Pass(passer=passer, release=current["index"],
                            reason="Contato ambíguo próximo demais à saída.")
            if gap_before or previous["ball"] is None or next_frame["ball"] is None:
                return Pass(passer=passer, release=current["index"],
                            reason="Bola perdida junto ao possível primeiro contato.")
            if any(receiver not in frame["players"] for frame in (previous, next_frame)):
                return Pass(passer=passer, release=current["index"],
                            reason="ID do possível recebedor descontínuo junto ao primeiro contato.")
            approach = foot_distance(previous, receiver, previous["ball"], pose_conf)
            retained = foot_distance(next_frame, receiver, next_frame["ball"], pose_conf)
            if approach <= contact:
                continue
            incoming = (ball[0] - previous["ball"][0], ball[1] - previous["ball"][1])
            outgoing = (next_frame["ball"][0] - ball[0], next_frame["ball"][1] - ball[1])
            change = math.dist(incoming, outgoing)
            changed = change >= max(math.hypot(*incoming) * 0.6, 1)
            if retained <= contact or changed:
                duration = (arrival["index"] - current["index"]) / fps
                return Pass(passer, receiver, current["index"], arrival["index"], duration)
    return launch
