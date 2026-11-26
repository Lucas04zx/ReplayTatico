# Efeitos especiais

O estúdio usa uma camada Canvas em coordenadas do vídeo. A mesma saída técnica gera os dois marcadores automáticos de passe. A trajetória luminosa usa somente posições de bola observadas em quadros consecutivos.

| Evento | Origem | Efeito |
| --- | --- | --- |
| `PASS_START` | Inferência | Pulso dourado, partículas e início do rastro |
| `PASS_RECEIVED` | Inferência | Impacto azul e destaque do recebedor |
| `SHOT` | Marcador manual | Concentração seguida de pulso e partículas laranja |
| `SAVE` | Marcador manual | Mão aberta procedural dourada, brilho, ondas e dissipação |
| `GOAL` | Marcador manual | Explosão, partículas e anúncio esportivo |
| `INTERCEPTION` | Marcador manual | Barreira luminosa e impacto |

Os marcadores manuais pedem o quadro e a posição do efeito no vídeo. São guardados no navegador com a indicação `manual`. A intensidade altera somente o desenho. O vídeo técnico exportado, eventos de passe, duração, mediana de profundidade e comparação manual vêm dos dados de análise.

A mão é uma silhueta Bézier autoral desenhada por código, sem dependência de sprites ou imagens externas. Use o modo Especial em uma partida real ou em um vídeo de anime fornecido pelo grupo. Um resultado nessa demonstração precisa ser registrado separadamente.
