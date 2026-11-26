# Pipeline técnico

O programa decodifica os quadros originais com OpenCV e usa a taxa de quadros verificada nos timestamps. O intervalo informado é fechado e começa em zero. O MP4 recortado imprime a numeração original no player, e o CSV utiliza os mesmos índices.

## Observações por quadro

1. `yolo26n.pt` e ByteTrack rastreiam pessoas. O detector pode incluir árbitros e pessoas fora do campo. Os IDs pertencem a um trecho, e perdas de rastreamento podem causar troca de ID.
2. O detector especializado do Roboflow localiza a bola. Quando há várias caixas, a confiança e a distância à posição recente ordenam os candidatos. O ponto registrado é o centro da caixa. As lacunas permanecem vazias e interrompem as linhas da trajetória.
3. Em uma janela de sete quadros, selecionamos até quatro jogadores próximos das posições observadas da bola. A pose usa recortes com margem e projeta as coordenadas de volta para o quadro original. As caixas são associadas ao ID por IoU, com rejeição de empates próximos. O desenho marca os pontos de baixa confiança em texto.

## Eventos do passe

A saída exige bola próxima do pé, o mesmo jogador rastreado em quadros consecutivos, distanciamento crescente e movimento de joelho ou tornozelo relativo ao quadril. As distâncias são normalizadas pela altura aparente do jogador. A sequência de trajetória busca um primeiro contato com outro jogador, aproximando-se, com persistência da proximidade ou mudança de movimento da bola no quadro seguinte. Quando o tornozelo está indisponível, o centro inferior da caixa aproxima a posição do pé. Esse recurso pode introduzir erro perto de oclusões. A detecção requer pose utilizável em uma das pernas na fase da saída.

A duração decorre de `(quadro_recepcao - quadro_saida) / FPS_original`. Troca de ID, candidatos ambíguos e perdas junto ao contato reduzem a confiança. Uma lacuna decisiva pode produzir um resultado inconclusivo com o motivo em `analise.json`.

## Evidências e profundidade

O modelo de segmentação produz máscaras associadas às caixas rastreadas. Os mesmos quadros de saída, meio da trajetória e recepção passam pelo YOLO26 Depth. Se o passe ficar inconclusivo, os mapas de amostragem são rotulados como início, meio e fim do recorte. Em cada mapa, a mediana exclui pixels não finitos ou não positivos. Quando o ID está disponível e a máscara falta, a região interna da caixa fornece uma estimativa rotulada, sujeita a contaminação pelo fundo.

O mapa tem a geometria do quadro original. Valores menores indicam superfícies mais próximas da câmera. A cor usa percentis de cada quadro, com regiões próximas mais escuras e distantes mais claras. O peso oficial carrega calibração global do conjunto de treino. O estádio e a câmera deste experimento não têm medições de referência. Por isso, analisamos a ordem de profundidade dentro de cada imagem. [Documentação do YOLO Depth](https://docs.ultralytics.com/tasks/depth/)

## Reprodução e avaliação

O cache guarda detecção, IDs e pose por hash do vídeo, intervalo, parâmetros de inferência, pesos, versões e dispositivo. Os modelos são executados em sequência para limitar uso de VRAM. A comparação com marcações manuais ocorre após a inferência. Os cliques do grupo são associados às caixas correspondentes no quadro de referência. Uma associação ambígua é registrada como ausente. Os erros de quadro e duração usam a convenção automático menos manual.
