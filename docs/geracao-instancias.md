# Geração das instâncias NRP-S

Como são geradas as instâncias do mestrado: cada parâmetro com o valor usado, a fonte do valor e a
justificativa. Estado em **2026-11-11**.

**Legenda da coluna Status**
- **Decidido**: o Rudson decidiu explicitamente.
- **Implementado**: está no gerador, com fonte para o valor, mas sem decisão explícita do Rudson.
- **Pendente**: falta o valor, a fonte ou a justificativa. Precisa de decisão antes da geração final.

## 1. Visão geral

| Item | Situação |
|---|---|
| Instâncias clássicas | `instances/nrp1`–`nrp5` do nrp-heuristic (Bagnall et al., 2001; Xuan et al., 2012), de 140 a 3.250 requisitos. Ficam no estudo para comparação. |
| Instâncias novas | Sintéticas. Geradas pelo `salbpgen nrps`, a reprodução própria do SALBPGen ([rudsonm/SALBPGen](https://github.com/rudsonm/SALBPGen)), com calibração pelo TAWOS. |
| Código do gerador | O `salbpgen/features.py` está no branch `nrps-features`, PR [rudsonm/SALBPGen#2](https://github.com/rudsonm/SALBPGen/pull/2), **ainda não mergeado**. O visualizador Streamlit está no PR #3. |
| Conjunto final | **Ainda não foi gerado.** Existem só 6 instâncias de exemplo no PC do usuário, fora do git. Os níveis dos fatores do experimento estão em aberto (seção 6). |

### Decisões que orientam a geração

| # | Decisão | Data | Motivo |
|---|---|---|---|
| D1 | Gerar com o SALBPGen, calibrado por métricas do TAWOS. Um LLM entra só como complemento, nunca como base. | 2026-11-05 | O SALBPGen controla a estrutura do grafo de precedência (estágios, OS, cadeias e gargalos), e o TAWOS ancora os valores em dados reais de times ágeis. |
| D2 | A unidade de calibração é o **projeto** do TAWOS, não a sprint. | 2026-11-05 | Decisão do usuário. |
| D3 | Os tamanhos ficam na faixa das clássicas (140–3.250). A faixa de 50 a 200 é pequena demais. | 2026-11-05 | Comparabilidade com nrp1–nrp5. |
| D4 | Entram só tarefas **planejadas**: estão numa sprint, entraram antes do início dela, e não são Bug, Epic nem suporte. | 2026-11-05 | O NRP decide o que entra na release a partir do backlog. O trabalho que surge durante a sprint não é decisão de planejamento. |
| D5 | Uma issue pai é **sempre** substituída pelas suas sub-tasks. | 2026-11-05 | Decisão do usuário. Ver a limitação em 3.2. |
| D6 | As instâncias precisam expor **inviabilidade temporal**: pelo menos um caminho crítico maior que T. Cada DAG representa as tarefas de uma feature. | 2026-11-05 | É o fenômeno que separa o NRP-S do NRP (seção 2). |
| D7 | As tarefas mais profundas valem mais (fator α). | 2026-11-05/06 | É o incentivo para selecionar caminhos críticos (seção 5.3). |

## 2. Por que caminho crítico > T

Fonte: `/mnt/project-files/tawos/gap-nrp-vs-nrps.md`, que tem a análise e o teste empírico.

- **Capacidade sozinha não gera inviabilidade.** Com `C[d] = T` e sem precedência, basta enfileirar
  as tarefas de cada dev. Por isso toda inviabilidade do NRP-S em relação ao NRP vem da restrição 9
  (`i` termina antes de `j` começar).
- **Condição suficiente.** Se `CP(S) > T`, a seleção `S` é inviável qualquer que seja o
  escalonamento.
- **Condição necessária.** Com `m` devs idênticos, o limite de Graham para list scheduling diz que o
  gap só pode aparecer se `W/m + (1 − 1/m)·CP > T`.
- **As clássicas não servem para isso.** Com 3 devs MID, o CP máximo vai de 10 (nrp5) a 43 (nrp4),
  abaixo de quase todo T em {40, …, 160}. Só 8 de 600 planos saturados (1,3%) se mostraram inviáveis
  no NRP-S.
- **O TAWOS também não.** Com o filtro D4, o maior caminho tem 10 tarefas (DM). 22 projetos não
  passam de 2 tarefas encadeadas, e 68% dos epics não têm nenhuma precedência interna
  (`tawos-caminho-critico.md`, `tawos-epics.md`).
- **Teste controlado.** Com os esforços do nrp1 e um grafo sintético em L níveis, a inviabilidade
  aparece quando `ρ = CP/T` fica entre cerca de 0,7 e 1,5. Com L = 2 ela não aparece, nem com 90% de
  dependência. Com L = 16, 30% de dependência já basta. **O que importa é a profundidade, não o
  percentual de dependência.**

**Consequência para o desenho.** O TAWOS calibra o *tamanho* das features, as *durações* e a
*proporção de arcos dentro e entre* features. A *profundidade* das features críticas é um nível
sintético de estresse, e é declarada como tal.

## 3. Fonte de dados: TAWOS

### 3.1 Dataset

| Item | Valor |
|---|---|
| Referência | Tawosi, Al-Subaihin, Moussa & Sarro (2022). *A versatile dataset of agile open source software projects.* MSR 2022. |
| Dump | figshare 21308124, `TAWOS.sql.zip` (MD5 `e9c5ecc7649d55f0cf2fb4efb5664494`), carregado em MariaDB 10.11 |
| Tamanho | 458.232 issues, 39 projetos, 4.594 sprints, 246.587 linhas em `Issue_Link` |
| Consultas | `/mnt/project-files/tawos/measure.sql`, `dep_pct.sql`, `cand.sql`. As consultas do filtro de planejadas, dos epics e do caminho crítico rodaram no PC do usuário e **não estão versionadas** (pendente). |

### 3.2 Filtros

| Filtro | Regra | Justificativa | Status |
|---|---|---|---|
| Tarefa planejada | `Sprint_ID` não nulo, e a primeira entrada no `Change_Log` (campo Sprint) na sprint final é anterior a `Sprint.Start_Date`. Sem registro no log, vale a data de criação. | D4. | Decidido. Limitação: o TAWOS guarda só a sprint final, então uma tarefa que transbordou e foi movida antes da sprint seguinte conta como planejada nela. |
| Tipos excluídos | Bug, Sub-task, Epic, Build Failure, Support Request, Question, Problem Ticket, Milestone | D4. Bugs e suporte surgem durante a sprint. | Decidido |
| Sub-tasks | O pai é trocado pelas filhas (D5). | Decisão do usuário. | Decidido, com cobertura baixa. O dump não tem o campo "pai", e a ligação só aparece no `Change_Log` para 17% das sub-tasks. Só 53 das 9.431 planejadas têm filhas identificáveis (96 sub-tasks). **Pendente:** (a) aceitar essa cobertura ou buscar o pai na API REST do Jira; (b) se a filha sem SP herda o SP do pai dividido entre as irmãs. |
| Story points válidos | 0 < SP ≤ 100 | SP > 100 são erros evidentes (141 issues; DATACASS = 26.710.114). SP = 0 não é duração. | Implementado |
| Links de precedência | Depends, Depend, dependent, Dependency, Required, Blocks, Blockers, Blocker, Block, Blocked, Gantt Dependency, Gantt End to Start, Gantt: finish-start, Finish-to-Start Dependency, Gantt: start-finish, Follows. Ficam fora Relates, Duplicate, Cloners, Part/Epic/Child, Cause/Regression e os tipos "fazer junto". | Só os tipos com semântica de ordem. | Implementado. **Pendente:** "Gantt: start-finish" não é finish-to-start, e só no DM são 2.228 linhas desse tipo. Sem ele, o DM cai de 19,0% para 13,9% de tarefas com dependência. Falta decidir se entra. |
| Direção dos arcos | "blocks", "has to be done before", "will help resolve" e "is triggering": A → B. "depends on", "requires", "follows" e "FS-depends on": B → A. | Semântica do texto do link. | Implementado |
| Ciclos | Descartados | Precisa ser DAG. | Implementado |
| Feature | Epic do último registro "Epic Link" (ou "Parent" apontando para um Epic) no `Change_Log` | O dump não tem coluna de epic. | Implementado. Nota: o filtro dos epics é o de "backlog" (os tipos acima) e **não** exige sprint. Medido em 3.288 epics de 25 projetos. |

### 3.3 Medidas usadas na calibração

| Medida | Valor | Arquivo |
|---|---|---|
| Tarefas planejadas | 9.431 (22% das 43.475 em sprint). O máximo por projeto é 2.516 (DM). | `tawos-planejadas-por-projeto.md` |
| SP das planejadas (n = 8.002) | mín 0,1; média 4,63; mediana 3; p90 8; máx 100 | idem |
| Planejadas com dependência entre si | 8,7% (566 pares). 11 projetos não têm nenhuma. | idem |
| Tarefas por epic | média 10,2; mediana 6; p75 12; p90 23; p99 68; máx 200 | `tawos-epics.md` |
| Epics (≥ 5 tarefas) sem precedência interna | 67,9% (CP = 1); só 4% com CP ≥ 4 | idem |
| Arcos entre epics diferentes | 35% (1.536 de 4.397) | idem |
| Maior caminho crítico (planejadas) | 10 tarefas / 100 SP (DM) | `tawos-caminho-critico.md` |

## 4. Gerador

Comando (PR #2):

```bash
salbpgen nrps -n <|R|> -T <T> --critical <k> --cp-ratio <ρ> --alpha <α> --seed <s> -o inst.nrp
```

A saída é o formato clássico lido por `nrp_instance.py`, mais um `.json` com os parâmetros, o CP de
cada feature e o CP da instância.

### Algoritmo

1. **Features críticas** (`n_critical`). São `critical_width` tarefas por estágio e K estágios, com
   OS no meio de [OSmin(n, K), OSmax(n, K)] (Teorema 1 de Otto et al., 2013). K começa em
   ⌊ρ·T / d_max⌋ e cresce, com até 50 sorteios por K, até que o CP com o dev mais rápido,
   Σ⌈h/1,4⌉, caia em [ρ·T, ρ·T + d_max). Aqui d_max é a maior duração rápida (⌈13·k/1,4⌉: 10 com k = 1, 75 com k = 8).
2. **Demais features**. O tamanho vem da lognormal da seção 5.1, e o grafo do SALBPGen com OS
   `feature_os`. O processo para quando a soma chega a |R|.
3. As features são embaralhadas e os valores distribuídos (5.3).
4. **Arcos entre features**: `inter_share/(1 − inter_share)` × (arcos internos), sempre de uma
   feature anterior para uma posterior, o que mantém o DAG.

### Pseudocódigo de `generate_nrps`

Transcrição de `salbpgen/features.py` (branch `nrps-features` / `streamlit-viewer`). A notação
⌈h/s⌉ é a duração com o dev mais rápido (s = `speedup`).

```text
Entrada: p = (n_tasks, T, n_critical, cp_ratio, speedup, critical_width, feature_os,
              size_median, size_p90, size_max, inter_share, alpha, value_scale,
              periods_per_sp, sp_weights), seed
Saída:   durações h[r], valores v[r], arcos A, features F

GENERATE_NRPS(p, seed):
    rng ← Random(seed)
    blocos ← []
    // 1. features críticas
    repita n_critical vezes:
        blocos.append( (crítica = V, CRITICAL_FEATURE(p, rng)) )
    usadas ← Σ |tarefas dos blocos|
    se usadas > n_tasks: erro "critical features need … tasks"

    // 2. demais features, até completar n_tasks
    enquanto usadas < n_tasks:
        k ← min(FEATURE_SIZE(p, rng), n_tasks − usadas)
        arcos ← GRAPH(k, feature_os, rng)                    // SALBPGen, K padrão
        dur   ← DURATIONS(k, p, rng)
        blocos.append( (crítica = F, arcos, dur) )
        usadas ← usadas + k
    embaralhar(blocos)

    // 3. concatenar as features e distribuir o valor por profundidade
    h, v, A, F ← [], [], [], []
    para cada (crit, arcos_f, dur_f) em blocos:
        o ← |h|                                              // deslocamento dos ids
        prof[r] ← nº de tarefas do maior caminho que termina em r, dentro da feature
        w[r]    ← (prof[r] / max prof) ^ alpha
        V_f     ← Σ dur_f · U(0,5; 1,5) · value_scale
        v      += [ max(1, round(V_f · w[r] / Σ w)) para r na feature ]
        h      += dur_f
        A      += { (o+u, o+w) : (u, w) ∈ arcos_f }
        cp_f ← CP rápido da feature (só arcos internos)
        F.append( tarefas o … o+|dur_f|−1,
                  crítica = (cp_f > T),          // qualquer feature cujo CP passe de T
                  controlada = crit, cp_f )      // gerada para mirar ρ·T

    // 4. arcos entre features (35% do total por padrão)
    n_inter ← round( inter_share / (1 − inter_share) · |A| )
    repita até n_inter arcos novos ou 100·n_inter tentativas:
        (a, b) ← dois índices de feature distintos, com a < b
        e ← (tarefa aleatória de F[a], tarefa aleatória de F[b])   // anterior → posterior: DAG
        se e ∉ A: A.append(e)
    retornar (h, v, A, F)

CRITICAL_FEATURE(p, rng):
    alvo  ← cp_ratio · T
    d_max ← ⌈max(sp_weights) · periods_per_sp / speedup⌉     // maior duração rápida (10 com k=1; 75 com k=8)
    K     ← max(2, ⌊alvo / d_max⌋)                           // menos estágios não alcança o alvo
    repita até 100 valores de K:
        abaixo ← V
        repita 50 vezes:
            n     ← K · critical_width
            OS    ← (OSmin(n, K) + OSmax(n, K)) / 2          // Otto et al. (2013), Teorema 1
            arcos ← GRAPH(n, OS, rng, K estágios)
            dur   ← DURATIONS(n, p, rng)
            cp    ← maior Σ ⌈dur[r]/speedup⌉ ao longo de um caminho
            se alvo ≤ cp < alvo + d_max: retornar (arcos, dur, cp)
            abaixo ← abaixo e (cp < alvo)
        se abaixo: K ← K + 1                                 // todos curtos demais: aprofundar
    erro "no critical feature with critical path in [alvo, alvo + d_max)"

FEATURE_SIZE(p, rng):
    σ ← ln(size_p90 / size_median) / 1,2816                  // 1,2816 = z do p90
    retornar min(size_max, max(1, round(LogNormal(ln size_median, σ))))

DURATIONS(k, p, rng):
    retornar [ periods_per_sp · s  para s ~ Categórica(sp_weights), k vezes ]   // SP do TAWOS; periods_per_sp inteiro

GRAPH(n, OS, rng, K = padrão):
    se n = 1: retornar ∅
    retornar arcos de generate_precedence_graph(n, OS, K)    // gerador SALBPGen, Seção 5.1
```

Observações:
- **Crítica × controlada.** `n_critical` define quantas features são *controladas*, isto é,
  construídas para ter CP em [ρ·T, ρ·T + d_max). A marca *crítica* vale para **toda** feature
  com CP > T, controlada ou não. Por isso o número de críticas é ≥ `n_critical` quando ρ > 1, e
  com k = 8 e T pequeno é bem maior.
- **Profundidade dos valores.** A profundidade que define o valor usa só os arcos internos da
  feature. Os arcos entre features, criados depois, não mudam o valor.
- **CP final.** O CP da instância é recalculado por `critical_path` sobre todos os arcos e gravado
  no `.json`. Ele pode passar de cp_ratio·T por causa dos arcos entre features.
- **Escrita.** `write` grava cada arco u → v como a linha `v+1 u+1`, para seguir o leitor atual
  `nrp_instance.py` (seção 7). Cada valor distinto vira um stakeholder com peso igual ao valor.

### Verificação (rodada na nuvem em 2026-11-12)

Com `-n 600 --critical 2 --cp-ratio 1.2 --periods-per-sp 8 --seed 1` (T e h em horas, SP ≤ 13), branch
`streamlit-viewer`:

| T | Features | Arcos | CP das controladas (rápido) | ρ·T | Features críticas (CP > T) | CP da instância |
|---|---|---|---|---|---|---|
| 40 | 55 | 544 | 104, 58 | 48 | 39 | 449 |
| 80 | 58 | 539 | 104, 110 | 96 | 17 | 643 |
| 120 | 53 | 522 | 150, 168 | 144 | 11 | 310 |
| 160 | 59 | 511 | 208, 220 | 192 | 5 | 365 |

- **Tamanho das features.** Com 20.000 sorteios, a mediana deu 6 e o p90 23, como o alvo.
- **Janela de aceitação larga com k = 8.** O CP de uma feature controlada é aceito em
  [ρ·T, ρ·T + d_max), e d_max = ⌈13·8/1,4⌉ = 75 h. Com T = 40, isso permite CP de 48 a 122 h, ou
  seja, de 1,2 a 3·T, e por isso o ρ efetivo varia muito. **Pendente:** decidir se a janela deve
  ficar proporcional a T.
- **Features não controladas também passam de T,** e mais ainda com T pequeno (coluna "críticas").
- **CP da instância.** Os arcos entre features só alongam o CP. O CP da instância fica muito acima de
  ρ·T e precisa ser lido do `.json`.

## 5. Parâmetros

### 5.1 Estrutura e durações (gerador)

| Parâmetro | Valor | Referência | Justificativa | Status |
|---|---|---|---|---|
| Tamanho das features | lognormal com mediana 6 e p90 23, truncada em [1, 200]; σ = ln(23/6)/1,2816 | TAWOS, tarefas por epic (`tawos-epics.md`) | Feature = Epic. Ajuste pela mediana e pelo p90, e o corte em 200 é o máximo observado. | Implementado. A escolha da família lognormal não foi testada por aderência (KS): **pendente**. |
| Duração base h_r (SP, dev MID) | distribuição empírica `TAWOS_SP` = {1: 16,2; 2: 16,6; 3: 17,4; 4: 10,0; 5: 15,0; 6: 2,8; 8: 12,6; 10: 2,4; 13: 2,9} (%), renormalizada no sorteio | SP das 8.002 planejadas com 0 < SP ≤ 100; corte de outliers: Cohn (2005), *Agile Estimating and Planning* (a página precisa ser conferida) | Distribuição real do backlog planejado. SP < 1 é arredondado para 1. **Outliers: SP > 13 removidos** (16, 20, 21 e acima, cerca de 1,8% das tarefas; decisão de 2026-11-12). 13 é o topo da escala de planning poker usada dentro de uma sprint, e itens maiores devem ser quebrados. A regra de Tukey (Q3 + 1,5·IQR = 9,5) foi descartada porque, numa distribuição assimétrica, corta a cauda real (≈7%). | Decidido (corte em 13). O descarte de valores intermediários raros (< 0,39%, como 7 e 11) continua sem justificativa: **pendente**. |
| Conversão SP → períodos (`periods_per_sp`, inteiro; `HOURS_PER_SP` no notebook) | **T em horas** (decisão de 2026-11-12). Notebook: 8 h por SP. Padrão da biblioteca: 1. | SAFe, *Iteration Planning*: 1 SP normalizado ≈ ½ dia de dev + ½ dia de teste, 8 SP por dev numa iteração de 2 semanas, ou seja, ≈ 1 dia-pessoa = 8 h. Tawosi, Moussa & Sarro (ESEM 2022): SP tem correlação fraca a média com o tempo registrado, e `In_Progress_Time` é o melhor proxy. | Não existe uma conversão média publicada. Os 8 h são uma **convenção** (SAFe), não um valor medido. | Implementado como convenção. **Pendente:** medir no TAWOS (mediana de `In_Progress_Time`/SP por projeto) ou assumir a convenção. Com 8 h/SP e T = 40, cerca de 23% das tarefas têm h > T para um dev MID (SP ≥ 6). Com o corte em 13, a maior tarefa tem 104 h (MID). |
| `feature_os` (features não críticas) | 0,1 | TAWOS: 68% dos epics sem precedência interna | Features reais são rasas. | Implementado. O valor 0,1 **não foi medido**: falta calcular a OS real dos epics (`salbpgen stats` sobre um `.alb` por epic). **Pendente.** |
| `inter_share` | 0,35 | TAWOS: 35% dos arcos ligam epics diferentes | Calibração direta. | Implementado |
| Direção dos arcos entre features | da feature anterior para a posterior | — | Garante DAG. Não reflete uma direção observada. | Implementado |
| Estrutura das features críticas | `critical_width` = 2 tarefas por estágio; OS no meio de [OSmin, OSmax] | Otto et al. (2013), Teorema 1 | Largura pequena gera profundidade com poucas tarefas. | Implementado. O valor 2 **não tem fonte**: **pendente** (candidato a fator, ou justificar). |
| `n_critical` | padrão 1; exemplo 2 | — | D6 pede "pelo menos um". | **Pendente** (nível do experimento) |
| `cp_ratio` ρ | padrão 1,2 | Teste controlado em `gap-nrp-vs-nrps.md`: transição com ρ ≈ 0,7–1,5 | ρ > 1 garante uma feature que não cabe inteira em T (D6). | Implementado. Os níveis do experimento (proposta: 0,5; 0,8; 1,0; 1,2) estão **pendentes**. |
| `speedup` | 1,4 | `nrp_instance.py`, SENIOR: H = ⌈h/1,4⌉ | O CP > T vale mesmo com o dev mais rápido. | Implementado. Herda a pendência do multiplicador SENIOR (5.2). |
| Sementes | `--seed`; o mesmo (parâmetros, semente) dá a mesma instância | — | Reprodutibilidade. | Implementado. Falta definir o plano de sementes do conjunto final: **pendente**. |

### 5.2 Desenvolvedores e horizonte (definidos ao carregar, em `nrp_instance.py`)

O arquivo gerado tem só tarefas, arcos e valores. D, T, H_rd, O_d e C_d são definidos ao carregar a
instância, em `nrp_instance.py` do nrp-heuristic, como nas clássicas.

| Parâmetro | Valor atual | Referência | Justificativa | Status |
|---|---|---|---|---|
| \|D\| e níveis | 3 × MID nos experimentos atuais (ADR 0002) | Proposta: Scrum Guide 2020 ("10 ou menos") | — | **Pendente** para as instâncias novas. Um time misto é necessário para o objetivo de custo não ser degenerado. |
| H_rd | JUNIOR ⌈h/0,7⌉; MID h; SENIOR ⌈h/1,4⌉ | Sem fonte no código | — | **Pendente.** Candidato: os multiplicadores ACAP/PCAP do COCOMO II (Boehm et al., 2000), a conferir. |
| O_d | JUNIOR 1, MID 2, SENIOR 3 | Sem fonte | Com esses valores, O_d·m_d varia (1,43 / 2 / 2,14 por SP), então o custo depende da atribuição. | **Pendente.** Candidato: razões salariais da Stack Overflow Developer Survey. |
| C_d | T | ADR 0002 | Com C_d = T, a restrição de capacidade não limita, e a inviabilidade fica só por conta da precedência (seção 2). | Implementado. A alternativa C_d < T enfraquece o mecanismo de saturação. |
| T | {40, 80, 120, 160} nas clássicas (ADR 0002) | Sprints de 1 a 4 semanas | — | **Pendente** para as instâncias novas: depende da unidade do período. |
| \|R\| | Faixa 140–3.250 (D3). Níveis propostos: ~150, ~600, ~1.500, ~3.000 | Clássicas nrp1–nrp5 | Comparabilidade. | Faixa decidida. **Níveis pendentes** (alternativa: os tamanhos exatos das clássicas, 140/620/1.500/3.250). |

### 5.3 Valor das tarefas e stakeholders

| Parâmetro | Valor | Referência | Justificativa | Status |
|---|---|---|---|---|
| Valor da feature V_f | esforço_f × U(0,5; 1,5) × `value_scale` | Pisinger (2005); Martello & Toth (1990) | A correlação valor × esforço controla a dificuldade da mochila embutida. | Implementado, mas **pendente**: a correlação ainda não é um fator controlado. Essa decisão foi levada ao Rudson e não foi respondida. |
| `value_scale` | 10 | — | Só escala para os valores inteiros terem resolução. | Implementado (técnico) |
| Distribuição por profundidade | v_r ∝ (prof_r / prof_max)^α, com soma V_f | Denne & Cleland-Huang (2004), Incremental Funding Method (MMF): a feature gera valor quando é entregue. Bagnall et al. (2001): o cliente conta se recebe tudo. | D7: valor no fim da cadeia, o que incentiva selecionar o caminho crítico. α precisa ser finito: com α → ∞ a feature crítica vale 0 em toda solução viável, e o incentivo some. | Implementado (padrão α = 1). Os níveis {0, 1, 3} foram propostos e **estão pendentes**. |
| Evidência empírica da premissa D7 | Fraca | TAWOS, 103.877 tarefas de backlog com prioridade (1–5) | Dentro do mesmo projeto, as tarefas com dependência ficam de 0,1 a 0,5 ponto acima em 18 de 24 projetos. No agregado a diferença some (2,78 × 2,76), e o fim da cadeia tem prioridade um pouco menor (2,72). | A premissa se apoia na teoria (MMF), não nos dados. Precisa ficar declarada. |
| Stakeholders S, W_s, I_rs | Cada valor distinto vira um stakeholder com peso igual ao valor, então Σ_s W_s·I_rs = v_r | — | No NRP-S o objetivo só depende de v_r = Σ W_s·I_rs, então isso basta para o modelo. | Implementado como artifício técnico. **Pendente:** a proposta de stakeholders realistas, que pedem features e não tarefas, com W_s ∈ 1–5 (Greer & Ruhe, 2004), número calibrado por componentes do TAWOS (63% das planejadas têm componente) e I_sf pela distribuição de prioridade do TAWOS mapeada para 1–5 (66% têm prioridade; o DM não tem nenhuma). |

## 6. Desenho experimental: o que falta fechar

Fatores com níveis ainda em aberto: |R|, T e a unidade do período, ρ = CP/T, `n_critical`, α,
a correlação valor–esforço, a composição de D e o número de réplicas por célula (o SALBPGen usa 25).
Recomendação de `gap-nrp-vs-nrps.md`: congelar o gerador e os parâmetros **antes** de rodar
qualquer heurística, e medir o gap de forma exata (MILP do NRP mais um teste de escalonabilidade
com CP-SAT), independente dos algoritmos comparados.

## 7. Pendência crítica: a direção das arestas em `_parse_file`

- **Nos arquivos clássicos**, a linha `a b` sempre tem `a` num nível anterior ao de `b`. Verificado
  nos 5 arquivos: 97/97, 556/556, 1.486/1.486, 4.961/4.961 e 2.036/2.036 pares. Isso é coerente com
  o CLAUDE.md, em que `a` precede `b`.
- **O `_parse_file`** grava `(b−1, a−1)`, e `nrp_problem.py` e `nrp_repair.py` leem `P[k] = (predecessor,
  sucessor)`. Logo, **as clássicas estão sendo lidas com as precedências invertidas**: um requisito
  de nível alto vira pré-requisito dos de nível baixo. Os comprimentos de caminho crítico não mudam
  ao inverter o grafo, mas mudam quais requisitos são raízes e o efeito do reparo.
- **O gerador** (`NRPSInstance.write`) segue o leitor atual e grava o arco u → v como `v+1 u+1`. Se o
  leitor for corrigido, o gerador precisa ser invertido junto, ou as instâncias novas passam a ser
  lidas ao contrário.
- **Pendente:** confirmar a convenção na fonte original do formato (Xuan et al., 2012) e corrigir o
  leitor e o gerador **juntos**. Este documento não altera código.

## 8. Referências

> Lista herdada dos documentos do projeto, montada de memória e sem conferência das fontes. Antes de
> citar, confirme os números de página e os valores (multiplicadores do COCOMO II, por exemplo).

- Bagnall, A. J.; Rayward-Smith, V. J.; Whittley, I. M. (2001). The next release problem. *IST* 43(14), 883–890.
- Boehm, B. et al. (2000). *Software Cost Estimation with COCOMO II*. Prentice Hall.
- Denne, M.; Cleland-Huang, J. (2004). The incremental funding method: data-driven software development. *IEEE Software* 21(3), 39–47.
- Graham, R. L. (1969). Bounds on multiprocessing timing anomalies. *SIAM J. Appl. Math.* 17(2), 416–429.
- Greer, D.; Ruhe, G. (2004). Software release planning: an evolutionary and iterative approach. *IST* 46(4), 243–253.
- Martello, S.; Toth, P. (1990). *Knapsack Problems*. Wiley.
- Otto, A.; Otto, C.; Scholl, A. (2013). Systematic data generation and test design for solution algorithms on the example of SALBPGen for assembly line balancing. *EJOR* 228(1), 33–45.
- Pisinger, D. (2005). Where are the hard knapsack problems? *Computers & OR* 32(9), 2271–2284.
- Schwaber, K.; Sutherland, J. (2020). *The Scrum Guide*.
- Tawosi, V.; Al-Subaihin, A.; Moussa, R.; Sarro, F. (2022). A versatile dataset of agile open source software projects. *MSR 2022*.
- Xuan, J.; Jiang, H.; Ren, Z.; Luo, Z. (2012). Solving the large scale next release problem with a backbone-based multilevel algorithm. *IEEE TSE* 38(5), 1195–1212.

## Fontes deste documento

- O código de `rudsonm/SALBPGen`: branch `nrps-features` (`salbpgen/features.py`, `README.md`) e
  `docs/nrp-s-geracao-de-instancias.md`.
- `nrp_instance.py`, `nrp_problem.py`, `nrp_repair.py` e `docs/adr/0002-experiment-design.md` do
  repositório rudsonm/nrp-heuristic (cópia deste documento em `docs/geracao-instancias.md` de lá).
- Na pasta do projeto: `tawos/medicoes-iniciais.md`, `tawos/gap-nrp-vs-nrps.md`,
  `tawos/dependencia-por-projeto.md`, `tawos-planejadas-por-projeto.md`,
  `tawos-tempos-por-projeto.md`, `tawos-caminho-critico.md` e `tawos-epics.md`.
- O histórico da thread "Gerar instâncias com SALBPGen calibrado pelo TAWOS" (2026-11-05 e 06).
