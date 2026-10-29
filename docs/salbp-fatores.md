# Fatores do SALBP e do SALBPGen

Explicação de cada fator do problema (SALBP-1) e do gerador de instâncias SALBPGen, com base em
Otto, Otto & Scholl (2013), *EJOR* 228(1), 33–45. As referências de seção, tabela e figura são
desse artigo. A última coluna das tabelas indica onde cada fator aparece neste repositório.

## 1. O problema: SALBP-1

Uma linha de montagem tem **estações** em sequência. Cada peça passa por todas as estações, e
cada estação tem o mesmo tempo disponível por peça, o **tempo de ciclo** *c*. O problema é
distribuir as **tarefas** entre as estações respeitando duas regras:

1. **Capacidade**: a soma dos tempos das tarefas de uma estação (o *tempo da estação*) não pode
   passar de *c*;
2. **Precedência**: se a tarefa *i* precede *j*, *i* precisa estar na mesma estação de *j* ou em
   uma anterior.

O **SALBP-1** minimiza o número de estações *m* para um *c* dado (Seção 3). O SALBP-2, que não é
tratado aqui, faz o inverso: fixa *m* e minimiza *c*.

| Elemento | Símbolo | Significado | No código |
|---|---|---|---|
| Tarefas | V = {1, …, n} | operações a distribuir | `Instance.n` |
| Tempo da tarefa | tᵢ | duração da operação *i* (inteiro) | `Instance.task_times` |
| Precedências | E | arcos (i, j): *i* antes de *j* | `Instance.arcs` |
| Grafo de precedência | G = (V, E, t) | grafo acíclico com os tempos nos nós | `PrecedenceGraph` |
| Fecho transitivo | Eᵀ | todos os pares (i, j) em que *i* precede *j*, direta ou indiretamente | `PrecedenceGraph.reach` |
| Tempo de ciclo | c | capacidade de cada estação | `Instance.cycle_time` |
| Estações | m | número a minimizar | — |

Arquivo de exemplo: um arquivo `.alb` contém exatamente esses elementos (`<number of tasks>`,
`<cycle time>`, `<order strength>`, `<task times>`, `<precedence relations>`).

## 2. Fatores do grafo de precedência

### Número de tarefas — *n*

O tamanho da instância. O data set de 2013 usa quatro tamanhos (Seção 5.3):

| Rótulo | n | Uso sugerido pelo artigo |
|---|---|---|
| small | 20 | pré-testes rápidos |
| medium | 50 | métodos exatos |
| large | 100 | heurísticas |
| very large | 1000 | tamanho comum na prática |

**Efeito na dificuldade:** é o fator de efeito mais forte. No modelo probit da Seção 6.2, a
probabilidade prevista de uma instância ser *extremely tricky* (com PM, OS = 0.2 e idle time de
5·c) passa de 0% para 63% e depois para 98% quando *n* vai de 20 para 50 e para 100.

No código: `GraphParams.n`, `--sizes`.

### Order strength — OS

Mede o quanto as tarefas estão ordenadas entre si (Tabela 2):

$$OS = \frac{2\,|E^T|}{n(n-1)}$$

É a fração dos pares de tarefas que têm alguma relação de precedência, direta ou indireta.

- **OS = 0**: nenhuma precedência; qualquer tarefa pode ir para qualquer estação.
- **OS = 1**: as tarefas formam uma única sequência; só existe uma ordem possível.
- **Exemplo:** com 4 tarefas há 6 pares. Com os arcos 1→2 e 2→3, o fecho tem (1,2), (2,3) e
  (1,3); então OS = 3/6 = 0.5.

Níveis do data set: **0.2 (baixa), 0.6 (média), 0.9 (alta)**. O gerador aceita uma tolerância
±dOS em torno do alvo.

**Efeito na dificuldade:** não é monotônico. As instâncias com OS média (0.6) são mais difíceis que
as de OS muito baixa ou muito alta (Seção 6.2). No exemplo do artigo, a probabilidade de ser
*extremely tricky* sobe de 63% (OS 0.2 ou 0.9) para 76% (OS 0.6). Com OS baixa há muitas soluções;
com OS alta, poucas.

No código: `GraphParams.order_strength`, `os_tolerance`, `--os`, `--os-tolerance`.

### Estágios — K

O **estágio** de uma tarefa é sua profundidade: o maior número de arcos de um caminho que vai de
uma origem fictícia até a tarefa (Seção 3). Na Fig. 2 do artigo há seis estágios: {1}, {2, 3, 4, 5},
{6, 7}, {8, 9, 10, 11}, {12} e {13}.

O conceito de estágio é o centro do SALBPGen (Seção 5.1). Primeiro o gerador escolhe K, depois
distribui as tarefas pelos estágios e só então cria os arcos.

O valor de K limita as OS possíveis (Teorema 1):

- **OSmin** = K(K−1) / (n(n−1)): todos os estágios ligados por um único caminho;
- **OSmax**: estágios de tamanhos iguais, com todas as ligações entre estágios vizinhos.

O padrão é o K que **maximiza OSmax − OSmin**, isto é, a maior variedade de grafos possíveis. Esse
máximo ocorre em n² ≈ K²(2K − 1) (Tabela 3):

| n | 20 | 50 | 100 | 1000 |
|---|---|---|---|---|
| K padrão | 6 | 11 | 17 | 80 |

Quando a OS alvo está fora de [OSmin, OSmax], K passa a crescer linearmente com a OS: K = 1 para
OS = 0 e K = n para OS = 1.

No código: `GraphParams.n_stages`, `default_stages()`, `os_min()`, `os_max()`, `--n-stages`.

### Tamanho dos estágios

Quantas tarefas cada estágio recebe. O padrão do artigo é uma **normal truncada**, com cada estágio
recebendo pelo menos uma tarefa (Seção 5.1). O artigo não informa o desvio padrão; o código usa
0.5·n/K (suposição).

No código: `GraphParams.stage_size_sd`, `--stage-size-sd`.

### Tipo de estrutura do grafo — MIXED, CH, BN

Grafos reais de montagem costumam ter **cadeias** e **gargalos** (Seção 4.1.2). Na Tabela 1 do
artigo, os grafos reais têm de 30% a 45% de tarefas em cadeias e de 1% a 6% de tarefas-gargalo, com
grau médio entre 5 e 14.

**Cadeia (*chain*).** Tarefas que formam um caminho, cada uma com no máximo um predecessor direto e
no máximo um sucessor direto. Uma cadeia tem pelo menos duas tarefas. Exemplo real: prender cabos
um após o outro. Na Fig. 2, as tarefas 2 → 6 → 8 → 12 formam uma cadeia.

**Gargalo (*bottleneck*).** Tarefa que é o único sucessor direto de pelo menos dois dos seus
predecessores e o único predecessor direto de pelo menos dois dos seus sucessores. Tem, portanto,
grau ≥ 4. Exemplo real: inspecionar a parte elétrica antes de instalar o carpete. Ela fecha um
bloco de trabalho e abre o seguinte. Na Fig. 2, a tarefa 7 é um gargalo de grau 6.

As três categorias do data set (Seção 5.3):

| Categoria | Definição | Parâmetros no código |
|---|---|---|
| **MIXED** | configuração padrão do gerador, sem controlar cadeias nem gargalos | nenhum |
| **CH** | pelo menos 40% das tarefas em cadeias | `chain_share=0.4`, `chain_length=(2, 6)`* |
| **BN** | gargalos com grau ≥ 8 (≥ 4 nas instâncias com n = 20) | `n_bottlenecks = 2% de n`*, `bottleneck_in/out = 4–7` (2–3 para n = 20)* |

\* Valores que o artigo não informa; foram escolhidos dentro das faixas da Tabela 1.

**Efeito na dificuldade:** no modelo probit (Tabela 7), o tipo de grafo **não** teve efeito
estatisticamente significativo.

No código: `structure_preset()`, `--structure`, `--chain-share`, `--n-bottlenecks`,
`--bottleneck-in`, `--bottleneck-out`.

### Tarefas isoladas

Tarefas sem predecessores nem sucessores. São uma estrutura opcional; no exemplo da Fig. 5 do
artigo, há uma.

No código: `GraphParams.n_isolated`, `--n-isolated`.

### Módulos

Grafos gerados separadamente e ligados como "super-nós" (Seção 5.1). A matriz M diz quais
módulos precedem quais: se o módulo A precede o B, toda tarefa de A precede toda tarefa de B.
Exemplo real: na montagem de carros, rodas, pedal do acelerador e revestimento do porta-malas.

No código: `connect_modules()`. A geração automática de M a partir de uma OS desejada não está
implementada.

## 3. Fatores dos tempos das tarefas

### Tempo de ciclo — *c*

O padrão é **c = 1000** (Seção 5.1). Os tempos são inteiros, porque alguns métodos exigem dados
inteiros; um *c* grande reduz o efeito do arredondamento e permite muitas combinações de tempos.

No código: `InstanceParams.cycle_time`, `--cycle-time`.

### Faixa dos tempos — tmin, tmax

Os limites da distribuição. O usuário pode defini-los (Seção 5.1). O código usa o padrão
[1, c].

No código: `--tmin`, `--tmax`.

### Distribuição dos tempos — PB, BM, PM

Três normais truncadas (Seção 5.3), baseadas em linhas reais (Kilbridge & Wester, 1961). Nelas, a
maioria das tarefas é pequena, perto de 1/10 do maior tempo, e as tarefas agregadas ficam perto de
metade do tempo de ciclo (Seção 4.1.1):

| Código | Nome | Forma | Parâmetros usados no código* |
|---|---|---|---|
| **PB** | *peak at the bottom* | um pico nas tarefas pequenas | N(0.1c, 0.1c) |
| **BM** | *bimodal* | dois picos, o maior nas tarefas pequenas (é o padrão do SALBPGen) | ⅔·N(0.1c, 0.1c) + ⅓·N(0.5c, 0.1c) |
| **PM** | *peak in the middle* | um pico em 0.5·c | N(0.5c, 0.1c) |

\* O artigo não informa desvios nem pesos; esses valores são suposições.

**Efeito na dificuldade:** forte. Instâncias PB são as mais fáceis e PM as mais difíceis
(Seção 6.2). O motivo é o mesmo do *bin packing*: com tarefas pequenas, quase qualquer distribuição
enche bem as estações; com tarefas perto de c/2, cabem só uma ou duas por estação, e uma escolha
errada desperdiça muito tempo.

No código: `--times`, `salbpgen/times.py`.

### Soma múltipla do tempo de ciclo

Opção de ajustar os tempos para que a soma seja múltipla de *c*, como em Hoffmann (1992)
(Seção 5.1). Assim, o limitante inferior ⌈Σt/c⌉ corresponde a estações exatamente cheias.

No código: `--sum-multiple-of-c`.

## 4. Medidas usadas para analisar as instâncias

Não são parâmetros de entrada: são calculadas sobre a instância gerada (Tabela 2). O comando
`salbpgen stats` calcula todas.

| Medida | Definição | O que indica |
|---|---|---|
| AIP | \|E\| / n | número médio de predecessores diretos |
| Grau máximo (MD) | maxᵢ (\|Pᵢ\| + \|Fᵢ\|) | tarefa mais conectada |
| Tarefas sem predecessor (s₁) | — | quantas tarefas podem começar a linha |
| Divergência e convergência | fórmulas da Tabela 2 | se o grafo mais se abre ou mais se fecha |
| Parcela de cadeias e de gargalos | definições da Seção 4.1.2 | estrutura do grafo |
| tmax/c, tmin/c | maior e menor tempo em relação ao ciclo | tamanho das tarefas |
| Variabilidade (TV) | tmax / tmin | dispersão dos tempos |
| Razão de soma | c / Σt | relação entre o ciclo e o trabalho total |
| Limitante inferior (LB) | ⌈Σt / c⌉ (e tarefas > c/2) | menor número possível de estações |
| *Idle time* | m·c − Σt | tempo ocioso na solução ótima |

**Idle time e dificuldade:** no modelo probit, o *idle time* tem efeito significativo: com menos
folga, a instância tende a ser mais difícil. O efeito é menor nas instâncias pequenas (Seção 6.2).

## 5. Trickiness (medida de dificuldade)

Proposta pelo artigo (Seção 4.2): **Tr é a fração de soluções não ótimas** no espaço de soluções,
estimada com 10.000 soluções aleatórias geradas pela regra de carga máxima. Em cada passo, uma
tarefa é sorteada entre as que cabem na estação atual; uma estação nova só é aberta quando nenhuma
tarefa cabe mais.

| Categoria | Tr |
|---|---|
| *extremely tricky* | ≥ 0.995 |
| *very tricky* | [0.95, 0.995) |
| *tricky* | [0.5, 0.95) |
| *less tricky* | (0, 0.5) |
| *trivial* | 0 (todas as soluções aleatórias são ótimas) |
| *open* | ótimo desconhecido |

Uma instância sem ótimo conhecido é considerada *extremely tricky* se a melhor solução conhecida
apareceu em menos de 0.5% das buscas aleatórias.

No código: `trickiness()`, `salbpgen trickiness`. Sem solver exato, o ótimo só é reconhecido quando
bate com o limitante inferior.

## 6. Fatores do desenho experimental

Como os fatores acima se combinam no data set de 2013 (Seção 5.3):

| Fator do desenho | Níveis |
|---|---|
| Tamanho (n) | 20, 50, 100, 1000 |
| Estrutura × OS | MIXED × {0.2, 0.6, 0.9}; CH × {0.2, 0.6}; BN × {0.2, 0.6} (7 blocos) |
| Distribuição dos tempos | PB, BM, PM |
| Réplicas por célula | 25 |

Isso dá 7 × 3 × 25 = **525 instâncias por tamanho** e 2100 no total. Instâncias triviais (Tr = 0)
são descartadas. O conjunto **"medium permuted"** acrescenta, para cada instância de n = 50, nove
cópias com os tempos das tarefas embaralhados. O grafo e o conjunto de tempos ficam iguais, e mesmo
assim a dificuldade pode mudar muito: o artigo encontrou permutações com Tr ≈ 0.9999 e outras com
Tr ≈ 0.0001.

No código: `generate_dataset()`, `salbpgen dataset` (com `--permutations 9` para o conjunto
permutado).

## 7. Resumo: quais fatores mais importam

Segundo o modelo probit do artigo (Tabela 7), em ordem de efeito sobre a dificuldade:

1. **Tamanho (n)**: o efeito mais forte.
2. **Distribuição dos tempos**: PM é a mais difícil, PB a mais fácil.
3. ***Idle time***: menos folga, mais difícil.
4. **OS**: efeito moderado e não monotônico; a OS média é a mais difícil.
5. **Tipo de estrutura (MIXED/CH/BN)** e **LB = ótimo**: sem efeito significativo.
