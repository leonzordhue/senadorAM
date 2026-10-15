# Metodologia

## Quem entra
Todo senador que o Senado lista pelo AM entre a 51ª e a 57ª legislatura e que **exerceu** mandato de 1999 em diante, titular ou suplente (`GET /senador/lista/legislatura/51/57?uf=AM` + `/senador/{cod}/mandatos`). Suplentes que nunca exerceram ficam de fora.

## Fontes
| Dado | Fonte oficial |
|---|---|
| Cadastro, mandatos, exercícios, filiações, comissões, cargos, licenças | API Dados Abertos do Senado (`/senador/{cod}/...`) |
| Matérias de autoria e 1º autor | `/senador/{cod}/autorias` |
| Situação e norma gerada | `/processo/{id}` (campo `normaGerada`) |
| Votações nominais | `/votacao?codigoParlamentar={cod}&dataInicio&dataFim` (ano a ano) |
| Discursos | `/senador/{cod}/discursos` (ano a ano) |
| Cota (CEAPS) | `senado.leg.br/transparencia/LAI/verba/despesa_ceaps_<ano>.csv` (2008 em diante) |
| Emendas ao orçamento | Portal da Transparência/CGU (2014 em diante) |

## Definições
- **Exercício:** períodos de `Exercicios` de cada mandato. Mandato de senador = 8 anos (duas legislaturas); os indicadores são separados por legislatura de 4 anos.
- **1º autor:** `IndicadorAutorPrincipal = Sim`.
- **Norma gerada:** matéria com `normaGerada` preenchido (lei, emenda constitucional, resolução, decreto legislativo), contada na legislatura da data de assinatura.
- **Presença em votações:** nas votações nominais em que o senador consta da lista, conta como presente quem votou (Sim, Não, Abstenção, "Votou" em votação secreta), presidiu ou estava presente sem registrar voto (P-NRV). **Ausência justificada:** licença, missão, atividade parlamentar (LS, LP, MIS, AP etc.). **Não compareceu:** NCom.
- **CEAPS:** valor reembolsado por ano; CPF de pessoa física não é publicado (LGPD). O casamento é pelo nome do senador na planilha.
- **Emendas:** mesmo critério do repositório dos deputados (casamento pelo nome e código do autor na CGU; teste de homônimo pela fração aplicada no AM).

## Identidade na plataforma comum (TSE)
Os três repositórios (deputadosfederais, senadorAM e dossieprefeitosAM) seguem o modelo de `PLATAFORMA-POLITICOS-AM.md`:
`pessoa_id` = os 10 primeiros caracteres do sha1 do título de eleitor. O título vale para qualquer eleição, então quem foi
prefeito, deputado e senador (ex.: Arthur Virgílio, Alfredo Nascimento) vira uma pessoa só. `scripts/tse.py` liga cada
parlamentar ao cadastro de candidatos do TSE das eleições gerais (1994 em diante) pelo nome civil + data de nascimento e grava:
- `dados/pessoas.csv`, `dados/identificadores.csv` (id da Casa e `SQ_CANDIDATO` de cada eleição), `dados/candidaturas.csv`
  (todas as candidaturas em eleições gerais no AM, com votos somados de `votacao_candidato_munzona`);
- `dados/mandatos.csv` (gerado por `gerar.py`, um período de exercício por linha);
- `fotos/<pessoa_id>.jpg` (foto oficial da Casa, 240 px) e `dados/integridade/tse.md`.
Título e CPF nunca são publicados. Vice-governador e suplente de senador não recebem voto próprio: o resultado é o da chapa.

## Emendas de quem mudou de Casa
O código de autor da CGU não muda quando a pessoa passa da Câmara ao Senado (ou volta). Por isso uma emenda só entra se houve
exercício no cargo deste repositório entre 01/08 do ano anterior e 31/12 do ano da emenda (a emenda à LOA de Y é apresentada no
2º semestre de Y-1). As linhas descartadas aparecem na saída de `gerar.py`.

## Limites
1. Relatorias e articulação política não aparecem nos números.
2. A API de autorias antiga está marcada como descontinuada pelo Senado; o teste 2 de VERIFICACAO.md compara com a API nova.
3. Antes de citar em documento oficial, confira no portal do Senado, no Planalto ou no Portal da Transparência.
