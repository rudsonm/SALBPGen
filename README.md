# SALBPGen

Systematic data generation and test design for solution algorithms on the example of SALBPGen for assembly line balancing.

Reprodução em Python do gerador **SALBPGen** para instâncias do *Simple Assembly Line Balancing
Problem* (SALBP-1). Usa só a biblioteca padrão (Python ≥ 3.10).

> Otto, A., Otto, C., Scholl, A. (2013). *Systematic data generation and test design for solution
> algorithms on the example of SALBPGen for assembly line balancing*. EJOR 228(1), 33–45.
> doi:10.1016/j.ejor.2012.12.029

## Instalação

```bash
pip install -e ".[dev]"
pytest
```

## Uso

```bash
# uma instância
salbpgen generate -n 50 --os 0.6 --structure BN --times PM --seed 1 -o inst.alb

# data sets de 2013 (padrão: n = 20, 50, 100, 1000; 7 blocos estrutura/OS; PB, BM, PM; 25 réplicas;
# instâncias triviais regeneradas) -> 525 instâncias por tamanho
salbpgen dataset data/ --seed 42
salbpgen dataset data/ --sizes 50 --permutations 9      # conjunto "medium permuted"
salbpgen dataset data/ --sizes 100 --blocks MIXED:0.4 CH:0.8 --times BM --replicates 10

# medidas de estrutura (Tabela 2) e trickiness (Seção 4.2) de arquivos .alb
salbpgen stats data/*.alb
salbpgen trickiness inst.alb --runs 10000 [--optimum 7]
```

```python
from salbpgen import InstanceParams, generate_instance, instance_stats, trickiness

inst = generate_instance(InstanceParams(n=100, order_strength=0.6, structure="CH", time_dist="BM"), seed=7)
inst.write("x.alb")
print(instance_stats(inst), trickiness(inst, runs=10_000))
```

## O que segue o artigo

**Geração de arcos (Seção 5.1)**, baseada em *estágios* (o estágio de uma tarefa é sua profundidade):

1. O número de estágios K é escolhido com a maior flexibilidade de precedência
   (Teorema 1: máximo de OSmax − OSmin em n² = K²(2K−1); reproduz a Tabela 3). Se a OS alvo
   está fora de [OSmin(K), OSmax(K)], K passa a ser linear em OS (K = 1 para OS = 0, K = n para OS = 1).
2. As estruturas opcionais (cadeias, gargalos, tarefas isoladas) são geradas e colocadas
   aleatoriamente nos estágios.
3. As demais tarefas são distribuídas nos estágios segundo uma normal truncada. Todo estágio
   tem pelo menos uma tarefa e pelo menos uma tarefa capaz de preceder o estágio seguinte.
4. As tarefas são renumeradas topologicamente (estágio por estágio), e cada tarefa é ligada a
   uma tarefa do estágio anterior.
5. Arcos aleatórios entre pares ainda não relacionados (de um estágio menor para um maior) são
   adicionados até a OS cair na tolerância ±dOS. Se não der certo, o procedimento inteiro é
   repetido; após `max_attempts` tentativas, é lançado um erro.

**Definições (Seção 4.1.2)**:

* *bottleneck*: tarefa que é o único sucessor direto de ≥ 2 predecessores diretos e o único
  predecessor direto de ≥ 2 sucessores diretos;
* *chain*: caminho de ≥ 2 tarefas, cada uma com ≤ 1 predecessor e ≤ 1 sucessor direto.

**Categorias do data set (Seção 5.3)**: `CH` tem ≥ 40% de tarefas em cadeias; `BN` tem gargalos
de grau ≥ 8 (≥ 4 para n = 20); `MIXED` usa as configurações padrão. Os blocos são MIXED × {0.2, 0.6,
0.9}, CH × {0.2, 0.6} e BN × {0.2, 0.6}, combinados com PB/BM/PM e 25 réplicas, o que dá 525
instâncias por tamanho. Instâncias triviais (Tr = 0) são excluídas. O conjunto "medium permuted"
acrescenta 9 permutações dos tempos por instância.

**Tempos**: c = 1000 por padrão. Os tempos são inteiros, sorteados de forma independente em
`[tmin, tmax]`. PB é uma normal com pico nas tarefas pequenas; BM é a combinação de duas normais
com pico maior nas pequenas (padrão do SALBPGen); PM é uma normal com pico em 0.5·c. Há a opção
de soma múltipla de c (Hoffmann, 1992).

**Trickiness (Seção 4.2)**: Tr é a fração de soluções não ótimas em 10.000 buscas aleatórias
com a regra de carga máxima. As categorias são *extremely tricky* (≥ 0.995), *very tricky*,
*tricky*, *less tricky*, *trivial* e *open*, com intervalo de Wilson (Apêndice A).

**Conector de módulos (Seção 5.1)**: `connect_modules(instancias, M)` liga grafos como módulos
segundo a matriz M.

## Suposições (valores que o artigo não informa)

| Parâmetro | Valor usado | Onde mudar |
|---|---|---|
| Desvio do tamanho dos estágios | 0.5 · n/K | `stage_size_sd` |
| Tolerância da OS (dOS) | ±0.005 (mínimo de 1 par) | `os_tolerance`, `--os-tolerance` |
| BN: número de gargalos | 2% de n (mínimo 1); faixa real: 1–6% | `n_bottlenecks` |
| BN: predecessores/sucessores por gargalo | 4–7 cada (grau 8–14); 2–3 para n = 20 | `bottleneck_in/out` |
| CH: comprimento das cadeias | 2–6 | `chain_length` |
| PB / BM / PM | N(0.1c, 0.1c) / ⅔·N(0.1c, 0.1c) + ⅓·N(0.5c, 0.1c) / N(0.5c, 0.1c) | `salbpgen/times.py` |
| Ajuste de K após falhas repetidas | extensão própria: K se aproxima da regra linear | `n_stages` fixa K |
| Detecção de instância trivial | todas as soluções aleatórias com o mesmo nº de estações | `--trivial-runs` |

A geração automática da matriz M de módulos a partir de uma OS desejada não está implementada.
Sem um solver exato, a trickiness usa o limitante inferior para reconhecer o ótimo; quando não o
reconhece, a instância fica como "open" ou, pela regra do artigo, como "extremely tricky".

## Formato de saída

Arquivos `.alb`, o mesmo formato dos data sets de Scholl (1993) e Otto et al. (2013): `<number of
tasks>`, `<cycle time>`, `<order strength>`, `<task times>`, `<precedence relations>`, `<end>`.
O comando `dataset` também grava um `index.csv` com parâmetros e medidas de estrutura de cada
instância.
