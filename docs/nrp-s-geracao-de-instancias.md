# Geração de instâncias para o NRP-S

Análise dos parâmetros do modelo proposto em *Next Release Problem with Precedence and Scheduling
Constraints* (Mendes, PPGCC/UFSC, 2026) e possíveis soluções para gerar instâncias de acordo com
eles. Cada decisão traz embasamento e referência.

## 1. Parâmetros do NRP-S

| Parâmetro | Significado | Nos experimentos preliminares |
|---|---|---|
| S | clientes | vêm das instâncias clássicas |
| R | tarefas | vêm das instâncias clássicas |
| P | pares de precedência | vêm das instâncias clássicas (níveis) |
| I_rs | prioridade do cliente s para a tarefa r | vem das instâncias clássicas (pedido ou não pedido) |
| W_s | importância do cliente | vem das instâncias clássicas |
| D | desenvolvedores | fixo em 3 |
| T | períodos do horizonte | {40, 80, 120, 160} |
| H_rd | tempo da tarefa r com o desenvolvedor d | H_rd = c_r, igual para todos ("MID") |
| O_d | custo por período | 2 para todos |
| C_d | capacidade | C_d = \|T\| |

## 2. Três pontos do modelo que pesam na geração

### (a) S, W_s e I_rs só entram na conta pelo valor somado de cada tarefa

O objetivo (4.1) é somado, tarefa por tarefa, sobre todos os clientes. Então ele depende apenas
de v_r = Σ_s W_s·I_rs. Isso é diferente do NRP clássico, em que o cliente só conta se *todas* as
suas tarefas forem entregues (Bagnall et al., 2001, eq. 2.3a).

- **Consequência**: o que controla a dificuldade é a distribuição de v_r e a correlação de v_r
  com o esforço H. O NRP sem dependências é uma mochila (Bagnall et al., 2001), e na mochila a
  correlação entre valor e peso é o principal fator de dificuldade: instâncias não correlacionadas
  são fáceis, e as fortemente correlacionadas são difíceis (Pisinger, 2005; Martello & Toth, 1990).
- Gerar S e I_rs só se justifica para obter v_r de forma realista, ou se houver objetivos por
  cliente (justiça entre clientes, por exemplo).

### (b) Com C_d = |T|, a restrição (4.4) nunca limita nada

Pelas restrições (4.5)–(4.9), um desenvolvedor já não pode trabalhar mais que |T| períodos. A
capacidade só passa a importar com C_d < |T|.

- Mesmo assim, o modelo deixa o desenvolvedor escolher *quais* períodos trabalhar. Férias ou
  dedicação parcial em datas fixas exigiriam um parâmetro de disponibilidade por período (A_dt),
  que hoje não existe.

### (c) O objetivo de custo deixa de ser constante só com heterogeneidade do tipo certo

O custo de uma tarefa com o desenvolvedor d é h_r·m_d·O_d, onde m_d é o multiplicador de
produtividade.

- Se O_d·m_d for igual para todos (sênior duas vezes mais caro e duas vezes mais rápido, por
  exemplo), o custo continua o mesmo para qualquer atribuição.
- Para existir o conflito "rápido e caro × lento e barato", O_d·m_d precisa variar entre os níveis.

## 3. Uma proposta por parâmetro

| Parâmetro | Proposta | Embasamento | Referência |
|---|---|---|---|
| **P (precedências)** | Gerar com o SALBPGen: estágios, OS controlada, cadeias e gargalos. Cada feature é um módulo, ligado às outras por uma matriz M esparsa. | Os "níveis" das instâncias clássicas são exatamente os estágios do SALBPGen, só que sem controle de OS. As dependências reais se concentram em poucas tarefas (cerca de 20% dos requisitos respondem por cerca de 75% das interdependências), e isso corresponde a tarefas-gargalo. | Otto et al. (2013); Bagnall et al. (2001); Carlshamre et al. (2001) |
| **P × T** | Controlar a razão entre o caminho crítico (em tempo) e \|T\|. | No NRP-S uma cadeia longa pode não caber no horizonte mesmo havendo capacidade de sobra (o efeito da Figura 2 da proposta). Em geradores de escalonamento, a estrutura da rede é um fator explícito. | Kolisch, Sprecher & Drexl (1995) |
| **H (duração base h_r)** | Story points de Fibonacci (1, 2, 3, 5, 8, 13), convertidos em períodos. Formato da distribuição como PB, BM ou PM do SALBPGen, relativo a \|T\|. | Story points são a unidade usual em times ágeis, e há datasets públicos para calibrar a distribuição. No SALBP, tempos próximos de metade da capacidade geram as instâncias mais difíceis, como no *bin packing*; a analogia aqui é a duração em relação a \|T\|. | Cohn (2005); Choetkiertikul et al. (2019); Tawosi et al. (2022); Otto et al. (2013, Tabela 7) |
| **H_rd (heterogeneidade)** | Duas variantes: **uniforme**, H_rd = ⌈h_r·m_d⌉ com m_d por senioridade; **não relacionada**, H_rd = ⌈h_r·m_d·ε_rd⌉ com um ruído ε, e H_rd > \|T\| para tarefas sem a habilidade necessária, o que as torna inviáveis via (4.9). | Os multiplicadores do COCOMO II dão uma base publicada: capacidade de análise (ACAP) de 1.42 (muito baixa) a 0.71 (muito alta), e de programação (PCAP) de 1.34 a 0.76. A diferença entre programadores existe, mas é bem menor que a lenda de 28:1. Máquinas paralelas não relacionadas são o modelo clássico desse tipo de atribuição, e o uso de habilidades tem precedente no gerador de escalonamento de projetos de software. | Boehm et al. (2000); Sackman et al. (1968); Prechelt (1999); Lenstra et al. (1990); Alba & Chicano (2007) |
| **O_d** | Razões salariais por nível tiradas de uma pesquisa salarial (por exemplo, a Stack Overflow Developer Survey, salário por anos de experiência), escolhendo os níveis de forma que O_d·m_d varie. | Sem esse cuidado o objetivo de custo continua degenerado (ponto c). Gerar salários aleatórios por funcionário tem precedente no gerador de Alba & Chicano. | Stack Overflow Developer Survey; Alba & Chicano (2007) |
| **C_d** | C_d = α_d·\|T\|, com α_d ∈ [0.5, 1]. Opcionalmente, estender o modelo com A_dt. | Desenvolvedores dividem o tempo com reuniões, interrupções e outras atividades, e a dedicação integral não é a regra. | Meyer et al. (2021) |
| **D** | \|D\| entre 3 e 10. | O Scrum Guide 2020 fala em times de "10 ou menos pessoas". A faixa de "3 a 7 desenvolvedores" atribuída ao Scrum Guide 2020 na proposta não aparece nessa versão; a de 2017 dizia de 3 a 9. Vale revisar a citação. | Schwaber & Sutherland (2020) |
| **T** | Fixar o período (hora ou meio dia) e derivar \|T\| da duração do sprint: 1 a 4 semanas, em geral 2. | Mantém a coerência entre a unidade de H e a de T. T = 40 a 160 funciona bem se o período for uma hora (de 1 a 4 semanas). | Schwaber & Sutherland (2020); Digital.ai (2023) |
| **Folga de capacidade** | Fator ρ = \|D\|·\|T\| / Σ_r h_r com níveis 0.3, 0.5 e 0.7. | É a forma padrão de definir o orçamento em instâncias de NRP (*cost ratio*). Em escalonamento, o fator correspondente é a *resource strength*. Nos resultados preliminares, o objetivo cresce com T justamente porque essa folga muda. | Xuan et al. (2012); Kolisch et al. (1995) |
| **v_r (valor)** e **I_rs, W_s** | Gerar v_r com correlação controlada com h_r: não correlacionada, fraca ou forte. Se forem mantidos clientes: W_s e I_rs na escala 1–5, com pedidos esparsos. | É a mochila embutida no problema (ponto a). As escalas 1–5 vêm do dataset clássico de 20 requisitos e 5 stakeholders. As instâncias realistas extraídas de repositórios de bugs servem para medir a popularidade das tarefas. | Pisinger (2005); Greer & Ruhe (2004); Xuan et al. (2012) |

## 4. Desenho experimental sugerido

Seguindo o princípio de Otto et al. (2013) e de Hall & Posner (2001), um desenho fatorial completo:

| Fator | Níveis |
|---|---|
| \|R\| | pequeno / médio |
| OS | 0.2 / 0.6 / 0.9 |
| Estrutura | MIXED / CH / BN |
| Folga ρ | 0.3 / 0.5 / 0.7 |
| Duração relativa a \|T\| | PB / BM / PM |
| Correlação valor–esforço | nenhuma / fraca / forte |
| Time | homogêneo / misto |

São 25 réplicas por célula, como no SALBPGen.

O limite prático de tamanho vem da Tabela 3 da proposta: o modelo tem cerca de 2·|R|·|D|·|T|
variáveis. A nrp4 com T=160 já passa de 3 milhões. Para o método exato, |R| deveria ficar entre
20 e 200. Tamanhos maiores ficam para comparar heurísticas, como o artigo do SALBPGen recomenda.

## 5. Três caminhos, que se complementam

1. **Estender as instâncias clássicas.** Basta acrescentar D, m_d, O_d e C_d conforme a tabela, e
   garante comparabilidade com a literatura.
2. **Sintético, com o SALBPGen.** P vem de estágios, OS, cadeias, gargalos e features como
   módulos. H vem das distribuições de tempo. O resto segue a tabela acima. É o único caminho que
   permite isolar cada fator.
3. **Calibrado com dados reais.**
   - **Estrutura e esforço**: medir as dependências e os story points de datasets públicos de
     Jira (Montgomery et al., 2022; Tawosi et al., 2022) com `salbpgen stats`.
   - **Clientes e popularidade das tarefas**: usar as instâncias realistas de Xuan et al. (2012).

Recomendação: usar os três: (1) como referência, (2) como núcleo do experimento e (3) para
justificar os valores usados em (2).

### Decisões em aberto

- Manter clientes explícitos (S, I_rs) ou gerar diretamente o valor v_r?
- Estender o modelo com disponibilidade por período (A_dt)?

## Referências

> Lista montada de memória, sem consulta às fontes. Antes de citar, conferir os números de página
> e os valores específicos: os 20%/75% de Carlshamre, os multiplicadores do COCOMO II e os níveis
> de *cost ratio* de Xuan et al.

- Alba, E.; Chicano, J. F. (2007). Software project management with GAs. *Information Sciences* 177(11), 2380–2401.
- Bagnall, A. J.; Rayward-Smith, V. J.; Whittley, I. M. (2001). The next release problem. *IST* 43(14), 883–890.
- Boehm, B. et al. (2000). *Software Cost Estimation with COCOMO II*. Prentice Hall.
- Carlshamre, P. et al. (2001). An industrial survey of requirements interdependencies in software product release planning. *RE'01*, 84–91.
- Choetkiertikul, M. et al. (2019). A deep learning model for estimating story points. *IEEE TSE* 45(7), 637–656.
- Cohn, M. (2005). *Agile Estimating and Planning*. Prentice Hall.
- Digital.ai (2023). *17th State of Agile Report*.
- Greer, D.; Ruhe, G. (2004). Software release planning: an evolutionary and iterative approach. *IST* 46(4), 243–253.
- Hall, N. G.; Posner, M. E. (2001). Generating experimental data for computational testing with machine scheduling applications. *Operations Research* 49, 854–865.
- Kolisch, R.; Sprecher, A.; Drexl, A. (1995). Characterization and generation of a general class of resource-constrained project scheduling problems. *Management Science* 41(10), 1693–1703.
- Lenstra, J. K.; Shmoys, D. B.; Tardos, É. (1990). Approximation algorithms for scheduling unrelated parallel machines. *Math. Programming* 46, 259–271.
- Martello, S.; Toth, P. (1990). *Knapsack Problems: Algorithms and Computer Implementations*. Wiley.
- Meyer, A. N.; Barr, E. T.; Bird, C.; Zimmermann, T. (2021). Today was a good day: the daily life of software developers. *IEEE TSE* 47(5), 863–880.
- Montgomery, L.; Lüders, C.; Maalej, W. (2022). An alternative issue tracking dataset of public Jira repositories. *MSR 2022*.
- Otto, A.; Otto, C.; Scholl, A. (2013). Systematic data generation and test design for solution algorithms on the example of SALBPGen for assembly line balancing. *EJOR* 228(1), 33–45.
- Pisinger, D. (2005). Where are the hard knapsack problems? *Computers & OR* 32(9), 2271–2284.
- Prechelt, L. (1999). The 28:1 Grant/Sackman legend is misleading, or: how large is interpersonal variation really? Tech. Report 1999-18, Univ. Karlsruhe.
- Sackman, H.; Erikson, W. J.; Grant, E. E. (1968). Exploratory experimental studies comparing online and offline programming performance. *CACM* 11(1), 3–11.
- Schwaber, K.; Sutherland, J. (2020). *The Scrum Guide*.
- Tawosi, V.; Al-Subaihin, A.; Moussa, R.; Sarro, F. (2022). A versatile dataset of agile open source software projects. *MSR 2022*.
- Xuan, J.; Jiang, H.; Ren, Z.; Luo, Z. (2012). Solving the large scale next release problem with a backbone-based multilevel algorithm. *IEEE TSE* 38(5), 1195–1212.
