# Replay de futebol com OpenCV e Ultralytics YOLO

Instituto Federal do Sul de Minas, Campus Machado · Bacharelado em Sistemas de Informação

Computação Gráfica · Trabalho Prático 2 · Professor Renan

Lucas Antônio Ferreira Neto · demais integrantes a confirmar

## Objetivo e trechos

O Replay Tático gera um MP4 para revisar a trajetória de um passe, identificar os jogadores envolvidos e inspecionar pose, segmentação e profundidade monocular. Os vídeos do Roboflow têm 1.920 × 1.080 pixels e 25 FPS verificados. O trecho de ajuste usa `0bfacc_0.mp4`, quadros 55–160. A avaliação independente usa `2e57b9_0.mp4`, quadros 402–471. O segundo lance foi inspecionado apenas no vídeo original até o congelamento. [Fontes e integridade dos vídeos](VIDEOS.md)

## Experimento de ajuste

| Configuração de bola e pose | Quadros sem candidato | Resultado |
| --- | ---: | --- |
| YOLO26n genérico, 1.600 px, confiança 0,12, pose no quadro inteiro | 27 / 106 | Inconclusivo |
| YOLO26n genérico, 1.920 px, confiança 0,08, pose no quadro inteiro | 15 / 106 | Inconclusivo |
| Detector Roboflow, 1.280 px, confiança 0,14, pose no quadro inteiro | 16 / 106 | Inconclusivo |
| Detector Roboflow, mesma entrada e limiar, pose em recortes de jogadores | 16 / 106 | Concluído |

Reduzir a confiança do YOLO genérico fez aparecer candidatos em mais quadros, inclusive falsos positivos na publicidade. O detector especializado acompanhou a bola perto da saída e até o primeiro contato estimado. A pose em recortes ampliou os jogadores e permitiu associar o gesto ao ID **6**. O sistema estimou a saída no quadro **60**, recepção pelo ID **1** no **91** e duração de **1,24 s**. Nos quadros 93–97 a bola não foi localizada. Esta é uma dificuldade real logo após a recepção estimada.

Os três momentos de pose foram exportados nos quadros 57, 60 e 63. A comparação caixa/máscara usa o quadro 56 e permite inspecionar a área de gramado incluída na caixa. O MP4 e as imagens do ajuste são gerados pelo comando do README. [Metodologia e limitações](ALGORITMOS.md)

| Momento | Quadro | Mediana do ID 6 | Mediana do ID 1 | ID estimado mais próximo |
| --- | ---: | ---: | ---: | ---: |
| Saída | 60 | 5,77 | 4,57 | 1 |
| Trajetória | 75 | 6,02 | 4,54 | 1 |
| Recepção | 91 | 6,25 | 4,89 | 1 |

As estimativas usaram a mediana dentro das máscaras dos dois jogadores. Os mapas são qualitativos neste experimento. Em um plano aberto, um atleta ocupa poucos pixels e a oclusão altera a parte visível sobre a qual a mediana é calculada.

## Avaliação independente

A marcação do grupo foi salva antes da inferência. O passador e o recebedor marcados foram associados aos IDs **1** e **3** do ByteTrack. Ambos os IDs aparecem nos 70 quadros do recorte. Ter IDs presentes não basta para confirmar automaticamente os papéis no passe.

| Medida | Referência manual | Automático | Diferença |
| --- | --- | --- | --- |
| Passador / recebedor | IDs associados 1 / 3 | Indeterminados | Indeterminada |
| Saída | Quadro 411 | Indeterminada | Indeterminada |
| Recepção | Quadro 456 | Indeterminada | Indeterminada |
| Duração | 1,80 s | Indeterminada | Indeterminada |

A bola foi detectada em 67 dos 70 quadros. As perdas ocorreram nos quadros 405, 409 e 410. No detalhe do lance, a bola fica junto ao corpo do atleta nos quadros 409–410 e reaparece separada no 411. A regra de saída exige observações consecutivas da bola e movimento da perna associado ao ID. Com a perda no intervalo decisivo, a inferência registrou **INCONCLUSIVO** e deixou os eventos e a duração em branco no CSV.

### Evidências dos quadros indicados pela referência manual

Depois de apurar e registrar o resultado automático, usamos os cliques e os quadros manuais para escolher as evidências visuais. O replay com referência exibe a origem manual dos marcadores. Os quadros 408, 411 e 414 apresentam pose em preparação, saída e finalização. O par caixa/máscara do quadro 407 permite observar o gramado incluído pela caixa na margem do atleta.

| Momento | Quadro | Mediana do ID 1 | Mediana do ID 3 | ID estimado mais próximo |
| --- | ---: | ---: | ---: | ---: |
| Saída | 411 | 5,13 | 6,58 | 1 |
| Trajetória | 433 | 5,53 | 6,99 | 1 |
| Recepção | 456 | 5,19 | 6,66 | 1 |

Nas três imagens, a estimativa aponta o passador como mais próximo. As medianas utilizam 1.114 a 1.477 pixels válidos por máscara. Cada valor descreve a superfície visível selecionada pelo modelo. Em câmera aberta, bordas imprecisas e regiões oclusas podem introduzir gramado ou deixar parte do corpo de fora. Os mapas ajudam a revisar a ordem de profundidade neste lance. Um único trecho não sustenta uma medida geral de acurácia.

## Apoio de IA

Codex auxiliou na implementação, execução de testes e organização da documentação. O grupo é responsável pela revisão, anotação independente e apresentação.
