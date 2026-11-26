import argparse
import json
from pathlib import Path

from .sources import SOURCES


def main():
    parser = argparse.ArgumentParser(prog="python -m replay_tatico")
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("baixar", help="Obtém os vídeos recomendados pelo professor.")
    download.add_argument("videos", nargs="*", metavar="VIDEO")
    download.add_argument("--pasta", type=Path, default=Path("data/raw"))
    probe = commands.add_parser("verificar", help="Decodifica o vídeo e confere FPS e integridade.")
    probe.add_argument("video", type=Path)
    inspect = commands.add_parser("inspecionar", help="Abre o vídeo original para inspeção quadro a quadro.")
    inspect.add_argument("video", type=Path)
    inspect.add_argument("--inicio", type=int, default=0)
    inspect.add_argument("--fim", type=int)
    commands.add_parser("preparar-modelos", help="Obtém os pesos YOLO26n e o detector de bola Roboflow.")
    analyze = commands.add_parser("analisar", help="Processa um trecho de ajuste ou um vídeo avulso.")
    analyze.add_argument("video", type=Path)
    analyze.add_argument("--inicio", type=int, required=True)
    analyze.add_argument("--fim", type=int, required=True)
    analyze.add_argument("--saida", type=Path, required=True)
    analyze.add_argument("--config", type=Path, default=Path("configs/ajuste.json"))
    analyze.add_argument("--dispositivo", default="auto")
    evaluate = commands.add_parser("avaliar", help="Executa o trecho congelado após a anotação independente.")
    evaluate.add_argument("--referencia", type=Path, default=Path("data/annotations/avaliacao.json"))
    evaluate.add_argument("--saida", type=Path, default=Path("outputs/avaliacao"))
    evaluate.add_argument("--dispositivo", default="auto")
    evidence = commands.add_parser("evidencias-avaliacao", help="Gera evidências visuais com a referência já comparada.")
    evidence.add_argument("--analise", type=Path, default=Path("outputs/avaliacao"))
    evidence.add_argument("--dispositivo", default="auto")
    delivery = commands.add_parser("empacotar", help="Organiza a entrega local e os resultados para a release.")
    delivery.add_argument("--ajuste", type=Path, default=Path("outputs/ajuste"))
    delivery.add_argument("--avaliacao", type=Path, default=Path("outputs/avaliacao"))
    delivery.add_argument("--referencia", type=Path, default=Path("data/annotations/avaliacao.json"))
    delivery.add_argument("--saida", type=Path, default=Path("outputs/entrega"))
    studio = commands.add_parser("estudio", help="Abre a estação local de inspeção e replay.")
    studio.add_argument("--porta", type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.command == "baixar":
            from .sources import fetch

            names = args.videos or list(SOURCES)[:2]
            unknown = sorted(set(names) - SOURCES.keys())
            if unknown:
                parser.error(f"Vídeos desconhecidos: {', '.join(unknown)}. Opções: {', '.join(SOURCES)}.")
            fetch(names, args.pasta)
        elif args.command == "verificar":
            from .video import probe as probe_video

            print(json.dumps(probe_video(args.video), ensure_ascii=False, indent=2))
        elif args.command == "inspecionar":
            from .video import inspect as inspect_video

            inspect_video(args.video, args.inicio, args.fim)
        elif args.command == "preparar-modelos":
            from .weights import prepare_weights

            prepare_weights()
        elif args.command == "estudio":
            from .web import create_app

            create_app().run(host="127.0.0.1", port=args.porta)
        elif args.command == "evidencias-avaliacao":
            from .evaluation import export_reference_evidence

            export_reference_evidence(args.analise, args.dispositivo)
        elif args.command == "empacotar":
            from .delivery import package_delivery

            package_delivery(args.ajuste, args.avaliacao, args.referencia, args.saida)
        elif args.command in {"analisar", "avaliar"}:
            from .pipeline import FROZEN_CONFIG, analyze

            if args.command == "analisar":
                from .evaluation import EVALUATION_CLIP
                from .pipeline import read_json
                from .video import file_hash

                if EVALUATION_CLIP.is_file():
                    registered = read_json(EVALUATION_CLIP)
                    if (file_hash(args.video) == registered["video_sha256"]
                            and args.inicio <= registered["end"] and args.fim >= registered["start"]):
                        raise ValueError("O trecho de avaliação deve ser executado pelo comando avaliar.")
                analyze(args.video, args.inicio, args.fim, args.saida, args.config, args.dispositivo)
            else:
                from .evaluation import frozen_experiment

                if not args.referencia.is_file():
                    raise ValueError("Registre primeiro a referência independente no clipe Avaliação do estúdio.")
                clip = frozen_experiment()
                analyze(clip["video"], clip["start"], clip["end"], args.saida, FROZEN_CONFIG,
                        args.dispositivo, evaluation_reference=args.referencia)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Erro: {error}\n")


if __name__ == "__main__":
    main()
