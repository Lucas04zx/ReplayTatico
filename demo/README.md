# Demonstração do Replay Tático na Vercel

[Abrir a demonstração publicada](https://replaytatico.vercel.app/)

O estúdio Flask inicia localmente por `python -m replay_tatico estudio`. O preset Flask da Vercel procurava um ponto de entrada distribuível e falhava com `FLASK_ENTRYPOINT_NOT_FOUND`. A hospedagem usa a interface compartilhada, arquivos JavaScript e as observações já calculadas. A montagem estática usa apenas módulos nativos do Node.js. [Entrypoints Flask](https://vercel.com/docs/frameworks/backend/flask)

## Implantação pelo GitHub

Na Vercel, use a branch `main` e mantenha **Root Directory** na raiz do repositório. No painel, o campo pode ficar em branco. O `vercel.json` nessa raiz define:

| Configuração | Valor |
| --- | --- |
| Application / Framework Preset | **Other** (`framework: null`) |
| Root Directory | Raiz do repositório |
| Install Command | Vazio |
| Build Command | `node demo/build.mjs` |
| Output Directory | `dist-demo` |

A integração Git dispara um novo deploy ao receber um commit na branch de produção. Para disparar pelo painel, selecione o commit novo. Reexecutar o deployment que falhou a partir do commit antigo reaplica o código antigo. [Configuração de build](https://vercel.com/docs/builds/configure-a-build) · [vercel.json](https://vercel.com/docs/project-configuration/vercel-json)

## Validar a montagem localmente

```powershell
node demo/build.mjs
python -m http.server 8771 --bind 127.0.0.1 --directory dist-demo
```

Abra o [servidor de teste](http://127.0.0.1:8771/). O build copia o template, estilos, controles e efeitos compartilhados do estúdio e os dados de `demo/data`. PyTorch, CUDA, Ultralytics, Flask e os pesos pertencem ao ambiente do estúdio local.

## Dados e limites

- O ajuste é o intervalo Q55–160 do `0bfacc_0.mp4`. O passe automático vai de Q60 a Q91 e dura 1,24 s.
- A avaliação usa Q402–471 do `2e57b9_0.mp4`. A saída automática é inconclusiva. A referência manual vai de Q411 a Q456 e dura 1,80 s. A linha do tempo identifica a origem desses instantes e os efeitos automáticos de passe usam somente os eventos do ajuste.
- A animação desenha as caixas, poses, trajetórias e contornos disponíveis a partir das observações originais. Os jogadores são posicionados em coordenadas da imagem sobre um campo autoral, sem calibração de coordenadas reais do gramado. Os contornos de segmentação publicados são do ajuste.
- Os três mapas de cada lance resumem as medianas medidas por jogador. As cores indicam a ordem de proximidade dentro do quadro. Os mapas densos, os MP4 e as imagens da transmissão permanecem no ambiente local.
- O modo Especial permite posicionar efeitos manuais, armazenados no navegador. A demonstração usa dois lances fixos. Novas inferências, importação e anotação acadêmica exigem o estúdio local.

Os dados da demonstração foram exportados de `outputs/ajuste-recorte` e `outputs/avaliacao`. Para atualizá-los após processar os lances localmente, gere os arquivos com `python demo/export_data.py --ajuste outputs/ajuste`. O comando usa o ambiente local e apenas grava JSON e CSV na pasta da demonstração. [Release acadêmica](https://github.com/Lucas04zx/ReplayTatico/releases/tag/tp2-1.0) · [Origem e licenças](../docs/LICENCAS.md)
