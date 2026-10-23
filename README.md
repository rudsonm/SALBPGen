# SALBPGen

Systematic data generation and test design for solution algorithms on the example of SALBPGen for assembly line balancing.

Reprodução em Python do gerador **SALBPGen** de Otto, Otto & Scholl (2013) para instâncias do
*Simple Assembly Line Balancing Problem* (SALBP). Usa só a biblioteca padrão (Python ≥ 3.10).

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

# data set fatorial completo (tamanhos x OS x estrutura x distribuição x réplicas)
salbpgen dataset data/ --sizes 20 50 100 1000 --os 0.2 0.6 0.9 \
    --structures MIXED BN CH --times PB PM BM --replicates 5 --seed 42

# estatísticas (CSV) de arquivos .alb, gerados ou originais
salbpgen stats data/*.alb
```

```python
from salbpgen import InstanceParams, generate_instance, instance_stats

inst = generate_instance(InstanceParams(n=100, order_strength=0.9, structure="CH", time_dist="BM"), seed=7)
inst.write("x.alb")
print(instance_stats(inst))
```

## Parâmetros do gerador

| Fator | Valores | Significado |
|---|---|---|
| `n` | ex. 20, 50, 100, 1000 | número de tarefas |
| `order_strength` | ex. 0.2, 0.6, 0.9 | OS = pares ordenados do fecho transitivo / (n(n−1)/2) |
| `structure` | `MIXED`, `BN`, `CH` | sem estrutura destacada / gargalos (*bottlenecks*) / cadeias (*chains*) |
| `time_dist` | `PB`, `PM`, `BM` | pico embaixo / pico no meio / bimodal |
| `cycle_time` | padrão 1000 | tempo de ciclo; tempos das tarefas ficam em `[tmin, tmax]` (padrão `[1, c]`) |

### Algoritmo do grafo de precedência (`salbpgen/precedence.py`)

1. **Esqueleto** conforme a estrutura:
   * `BN`: `max(1, round(n/50))` gargalos espalhados pela ordem topológica, cada um com 4–7
     predecessores e 4–7 sucessores diretos (grau limitado automaticamente quando a OS alvo exige).
   * `CH`: `chain_share` (padrão 50%) das tarefas em cadeias de 3–8 tarefas; o interior das cadeias
     fica travado (exatamente 1 predecessor e 1 sucessor).
   * `MIXED`: sem esqueleto.
2. **Preenchimento**: arcos aleatórios não redundantes são adicionados até a OS atingir o alvo
   (tolerância padrão ±0.005, mínimo de 1 par). Tarefas comuns têm no máximo `max_pred`/`max_succ`
   (padrão 3) relações diretas; tarefas isoladas e parceiros próximos na numeração são preferidos.
   O fecho transitivo é mantido de forma incremental com bitsets, e o grafo fica sempre
   transitivamente reduzido.
3. Reinícios automáticos se o alvo não for atingido; no fim as tarefas são renumeradas segundo uma
   ordem topológica aleatória.

Todos esses parâmetros estão em `GraphParams` e também podem ser passados pela CLI
(`--max-pred`, `--bottleneck-degree`, `--chain-share`, ...).

### Tempos das tarefas (`salbpgen/times.py`)

Misturas de normais truncadas em `[tmin, tmax]`, com média e desvio dados como fração de `tmax`:
`PB = N(0.1, 0.1)`, `PM = N(0.5, 0.1)`, `BM = ½·N(0.1, 0.1) + ½·N(0.5, 0.1)`. Para usar outras
formas, passe uma lista `(peso, média, desvio)`.

## Formato de saída

Arquivos `.alb`, o mesmo formato dos data sets de Scholl (1993) e Otto et al. (2013)
(`<number of tasks>`, `<cycle time>`, `<order strength>`, `<task times>`,
`<precedence relations>`, `<end>`). O comando `dataset` também grava um `index.csv` com os
parâmetros e as estatísticas medidas de cada instância.

## Estado da reprodução

A estrutura geral (fatores OS × estrutura × distribuição de tempos, formato `.alb`) segue o
artigo. **Os valores numéricos padrão (graus dos gargalos, tamanho e proporção das cadeias,
limite de grau, parâmetros das distribuições de tempo) são uma reconstrução e ainda precisam ser
conferidos com o texto do artigo.** O comando `salbpgen stats` serve para comparar as instâncias
geradas com as instâncias originais.
