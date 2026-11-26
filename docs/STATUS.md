# Status em 26/11/2026

- Enunciado e dossiê lidos. A avaliação exige anotação independente do grupo antes da execução automática no segundo trecho.
- Python 3.14.7 e ambiente virtual isolado disponíveis. O driver NVIDIA 621.24 reconhece a RTX 3050 Laptop com 6.144 MiB de VRAM. O disco tinha 97,4 GiB livres no diagnóstico inicial.
- Repositório privado criado como `Lucas04zx/ReplayTatico`. A branch local inicial é `main`.
- PyTorch 2.10.0+cu128, Ultralytics 8.4.219 e OpenCV 4.13.0 instalados. Uma operação de tensor na GPU retornou o valor esperado. `pip check` informou dependências consistentes.
- Os dois vídeos oficiais foram decodificados integralmente. Ambos têm 1.920 × 1.080 pixels, 750 quadros, 25 FPS constantes e 30 segundos. Referências e hashes em [Vídeos](VIDEOS.md).
- Os quatro pesos YOLO26n oficiais foram baixados e conferidos por SHA-256.
- A CLI de obtenção, verificação e inspeção usa os índices originais. Os testes verificam a leitura fora de ordem, o FPS e a rejeição de entrada inválida.
- O ajuste (`0bfacc_0.mp4`, Q55–160) gerou um passe automático ID 6 → 1, Q60–91, duração de 1,24 s. O detector especializado e a pose em recortes foram escolhidos nesse trecho. As comparações iniciais estão no [relatório](RELATORIO.md).
- O grupo registrou a referência do lance congelado (`2e57b9_0.mp4`, Q402–471) antes da inferência. Referência manual de 1,80 s em Q411–456. A saída automática foi inconclusiva, com perda da bola em Q409–410 perto da saída.
- A revisão visual da avaliação usou os quadros e papéis da referência após registrar a saída automática. O MP4 com os marcadores manuais, as três duplas RGB/profundidade, a tabela e os quadros de pose e segmentação foram gerados.
- Estúdio Flask local com avanço e retorno por quadro, reprodução, camadas, exportação, profundidade e efeitos manuais. A reprodução, a navegação e a Mão Fantasma foram verificadas no Chrome.
- Os oito testes automatizados passaram. Os MP4 de ajuste e avaliação foram decodificados e conferidos a 25 FPS.
- A tag `tp2-1.0` preserva o código e o ZIP de resultados da entrega acadêmica. Em um clone da tag, a avaliação reproduziu a análise, a comparação, o CSV e a tabela de profundidade da release byte a byte com o mesmo ambiente CUDA.
- O README tem versões em português e inglês e capturas da interface. A [documentação de licenças](LICENCAS.md) descreve o que é distribuído e a origem dos insumos locais.
- A [demonstração estática](../demo/README.md) foi montada sem dependências de inferência na hospedagem. Os quatro CSVs correspondem à release acadêmica. O Chrome verificou reprodução, navegação por quadro, camadas, efeitos, profundidade e downloads da demonstração, além da regressão do estúdio Flask local.
