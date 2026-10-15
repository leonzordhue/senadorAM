"""Gera os dossiês (Markdown) e as tabelas derivadas dos senadores do AM a partir do que coletar.py baixou.

Saídas:
  README.md                      visão geral e índice
  legislaturas/<n>-<anos>.md     dossiê de cada legislatura (4 anos; o mandato de senador cobre duas)
  senadores/<slug>.md            dossiê de cada senador
  dados/resumo.csv               indicadores por senador × legislatura
  dados/materias.csv             matérias de autoria (com situação e norma gerada)
  dados/ceaps_resumo.csv         cota (CEAPS) por senador, ano e tipo de despesa
  dados/emendas_resumo.csv       emendas (CGU) por senador, ano e função
Uso: python -I scripts/gerar.py
"""
import csv, datetime as dt, json, os, re, unicodedata
from collections import Counter, defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE_DIR, "_cache")
DADOS = os.path.join(BASE_DIR, "dados")
HOJE = dt.date.today().isoformat()

# códigos de voto do Senado (RISF). Presente = estava na sessão; os demais são ausências.
PRESENTE = {"Sim", "Não", "Abstenção", "Votou", "P-NRV", "Obstrução", "Presidente (art. 51 RISF)", "P-OD", "AP-NRV"}
NAO_COMPARECEU = {"NCom"}  # ausência sem justificativa registrada
LEGISLATIVOS = {"PLS", "PL", "PLC", "PEC", "PLP", "PDS", "PDL", "PRS"}
NOME_TIPO = {"PLS": "Projeto de Lei do Senado", "PL": "Projeto de Lei", "PEC": "Proposta de Emenda à Constituição",
             "PLP": "Projeto de Lei Complementar", "PDS": "Projeto de Decreto Legislativo (Senado)",
             "PDL": "Projeto de Decreto Legislativo", "PRS": "Projeto de Resolução do Senado", "RQS": "Requerimento",
             "REQ": "Requerimento", "RQI": "Requerimento de informações", "INS": "Indicação"}


def ler_json(nome, pasta=DADOS):
    p = os.path.join(pasta, nome)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(a, b):
    return f"{100 * a / b:.1f}%".replace(".", ",") if b else "—"


def data_br(s):
    return "/".join(reversed(s[:10].split("-"))) if s else "—"


def num_br(s):
    s = (s or "0").strip()
    return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s or 0)


def leg_datas(L):
    a = 1999 + 4 * (L - 51)
    return f"{a}-02-01", f"{a + 4}-01-31"


def leg_de_data(d):
    a = int(d[:4]) if d[5:10] >= "02-01" else int(d[:4]) - 1
    return 51 + (a - 1999) // 4


def nome_leg(L):
    a, b = leg_datas(L)
    return f"{L}ª ({a[:4]}–{b[:4]})"


def arq_leg(L):
    a, b = leg_datas(L)
    return f"{L}-{a[:4]}-{b[:4]}.md"


def tabela(cab, linhas):
    out = ["| " + " | ".join(cab) + " |", "|" + "|".join("---" for _ in cab) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in l) + " |" for l in linhas]
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ carga
sens = ler_json("senadores.json")
S = {s["codigo"]: s for s in sens}
for s in sens:
    s["slug"] = slug(s["nome"])
    per = []
    for m in s["mandatos"]:
        for e in m["exercicios"]:
            ini = e["inicio"] or m["inicio"]
            fim = e["fim"] or min(m["fim"] or HOJE, HOJE)
            if fim >= "1999-02-01":
                per.append((max(ini, "1999-02-01"), fim, e.get("causa_afastamento")))
    s["exercicio"] = sorted(per)
    s["legislaturas"] = sorted({L for a, b, _ in per for L in range(leg_de_data(a), leg_de_data(b) + 1) if L >= 51})


def periodos(s, L):
    ini, fim = leg_datas(L)
    return [(max(a, ini), min(b, fim)) for a, b, _ in s["exercicio"] if a <= fim and b >= ini]


def em_exercicio(s, data):
    return any(a <= data[:10] <= b for a, b, _ in s["exercicio"])


def dias(per):
    return sum((dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days + 1 for a, b in per)


# ------------------------------------------------------------------ modelo comum da plataforma (../PLATAFORMA-POLITICOS-AM.md)
# pessoa_id e trajetória eleitoral vêm de scripts/tse.py (cadastro de candidatos do TSE)
def ler_csv(nome):
    p = os.path.join(DADOS, nome)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


PID = {i["valor"]: i["pessoa_id"] for i in ler_csv("identificadores.csv") if i["sistema"] == "senado"}
CAND = defaultdict(list)
for c_ in ler_csv("candidaturas.csv"):
    CAND[c_["pessoa_id"]].append(c_)
CARGO_TXT = {"deputado_federal": "Deputado federal", "deputado_estadual": "Deputado estadual", "senador": "Senador",
             "suplente_senador": "Suplente de senador", "governador": "Governador", "vice-governador": "Vice-governador"}


def trajetoria(pessoa_id):
    """Seção do dossiê com todas as candidaturas em eleições gerais no AM (os cargos municipais estão no dossieprefeitosAM)."""
    cs = CAND.get(pessoa_id)
    if not cs:
        return ""
    return ("\n## Trajetória eleitoral no AM (TSE, eleições gerais)\n\n"
            f"Identificador comum da plataforma: `pessoa_id {pessoa_id}`. Cargos municipais (prefeito, vereador) ficam no repositório dossieprefeitosAM.\n\n"
            + tabela(("Ano", "Turno", "Cargo", "Partido", "Nº", "Votos", "% votos nominais", "Resultado"),
                     [(c["ano"], c["turno"], CARGO_TXT.get(c["cargo"], c["cargo"]), c["partido"], c["numero"],
                       f"{int(c['votos']):,}".replace(",", ".") if c["votos"] else "—", (c["pct"].replace(".", ",") + "%") if c["pct"] else "—",
                       c["resultado"] or c["situacao_candidatura"] or "—") for c in cs]))


autorias = ler_json("autorias.json")
proc = ler_json("processos.json", CACHE)
for c, itens in autorias.items():
    for i in itens:
        ng = (proc.get(i.get("id_processo") or "", {}) or {}).get("norma_raw") or {}
        i["norma"] = ng.get("descricao") or ""
        i["norma_tipo"] = ng.get("tipo") or ""
        i["norma_data"] = ng.get("dataAssinatura") or ""
        i["url"] = f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{i['codigo_materia']}"
votacoes = ler_json("votacoes.json")
discursos = ler_json("discursos.json")

ceaps = defaultdict(lambda: defaultdict(float))
ceaps_forn = defaultdict(Counter)
p = os.path.join(DADOS, "ceaps.csv")
if os.path.exists(p):
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            v = num_br(r["valor"])
            ceaps[(r["codigo"], r["ano"])][r["tipo"].split(",")[0].strip()] += v
            ceaps_forn[r["codigo"]][(r["fornecedor"].strip(), r["cnpj"])] += v


def apresentou_no_cargo(per, ano):
    """A emenda à LOA do ano Y é apresentada no 2º semestre de Y-1. O código de autor da CGU é o mesmo quando a pessoa
    muda de Casa (ex.: deputada que vira senadora), então só conta a emenda se houve exercício neste cargo entre
    01/08 de Y-1 e 31/12 de Y."""
    a, b = f"{int(ano) - 1}-08-01", f"{ano}-12-31"
    return any(x <= b and y >= a for x, y in per)


emendas_fora = Counter()   # linhas descartadas por não haver exercício no cargo (vão para VERIFICACAO)
emendas = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
emendas_mun, emendas_qtd = defaultdict(Counter), defaultdict(set)
p = os.path.join(DADOS, "emendas.csv")
if os.path.exists(p):
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            c, ano = r["codigoSenador"], r["Ano da Emenda"]
            if not apresentou_no_cargo([(a_, b_) for a_, b_, _ in S[c]["exercicio"]], ano):
                emendas_fora[S[c]["nome"]] += 1
                continue
            e = emendas[(c, ano)][r["Nome Função"]]
            e[0] += num_br(r["Valor Empenhado"]); e[1] += num_br(r["Valor Pago"]) + num_br(r["Valor Restos A Pagar Pagos"])
            emendas_mun[c][r["Localidade de aplicação do recurso"]] += num_br(r["Valor Empenhado"])
            emendas_qtd[(c, ano)].add(r["Código da Emenda"])


# ------------------------------------------------------------------ indicadores
def indicadores(s, L):
    c, (ini, fim) = s["codigo"], leg_datas(L)
    per = periodos(s, L)
    mats = [i for i in autorias.get(c, []) if i["data"] and ini <= i["data"][:10] <= fim]
    nr = [i for i in autorias.get(c, []) if i["norma_data"] and leg_de_data(i["norma_data"]) == L]
    vs = [v for v in votacoes.get(c, []) if v["data"] and ini <= v["data"][:10] <= fim and v["voto"]]
    pres = [v for v in vs if v["voto"] in PRESENTE]
    ncom = [v for v in vs if v["voto"] in NAO_COMPARECEU]
    anos = [str(a) for a in range(int(ini[:4]), int(ini[:4]) + 4)]
    return dict(
        senador=s["nome"], codigo=c, legislatura=L, dias_exercicio=dias(per),
        materias=len(mats), legislativas_principal=sum(i["principal"] and i["sigla"] in LEGISLATIVOS for i in mats),
        requerimentos=sum(i["sigla"].startswith("R") for i in mats),
        normas_principal=sum(i["principal"] for i in nr), normas_coautor=sum(not i["principal"] for i in nr),
        votacoes=len(vs), presente=len(pres), nao_compareceu=len(ncom), ausencia_justificada=len(vs) - len(pres) - len(ncom),
        discursos=sum(1 for x in discursos.get(c, []) if x["data"] and ini <= x["data"][:10] <= fim),
        ceaps=round(sum(sum(ceaps[(c, a)].values()) for a in anos), 2),
        emendas_empenhado=round(sum(v[0] for a in anos for v in emendas[(c, a)].values()), 2),
        emendas_pago=round(sum(v[1] for a in anos for v in emendas[(c, a)].values()), 2))


RES = [indicadores(s, L) for s in sens for L in s["legislaturas"]]
IDX = {(r["codigo"], r["legislatura"]): r for r in RES}


def gravar_csv(nome, linhas):
    if linhas:
        with open(os.path.join(DADOS, nome), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0])); w.writeheader(); w.writerows(linhas)


gravar_csv("resumo.csv", RES)
gravar_csv("materias.csv", [dict(senador=S[c]["nome"], codigo=c, **{k: i.get(k, "") for k in (
    "identificacao", "sigla", "data", "principal", "situacao", "norma", "norma_data", "ementa", "url")})
    for c, itens in autorias.items() if c in S for i in itens])
gravar_csv("ceaps_resumo.csv", [dict(senador=S[c]["nome"], codigo=c, ano=a, tipo=k, valor=round(v, 2))
                                for (c, a), t in sorted(ceaps.items()) for k, v in sorted(t.items())])
gravar_csv("emendas_resumo.csv", [dict(senador=S[c]["nome"], codigo=c, ano=a, funcao=k, empenhado=round(e, 2), pago=round(p_, 2))
                                  for (c, a), fs in sorted(emendas.items()) for k, (e, p_) in sorted(fs.items())])
# mandatos.csv no modelo comum: um período de exercício por linha (inclui exercícios anteriores a 1999)
gravar_csv("mandatos.csv", [dict(
    pessoa_id=PID.get(s["codigo"], ""), cargo="senador", uf="AM", cod_ibge="", inicio=e["inicio"] or m["inicio"] or "",
    fim=e["fim"] or "", origem="eleição" if (m["participacao"] or "").startswith("Titular") else "posse de suplente",
    observacao="; ".join(x for x in (f"mandato {data_br(m['inicio'])} a {data_br(m['fim'])} ({m['participacao']})",
                                     f"afastamento: {e['causa_afastamento']}" if e.get("causa_afastamento") else "",
                                     "em exercício" if not e["fim"] else "") if x),
    fonte=f"https://legis.senado.leg.br/dadosabertos/senador/{s['codigo']}/mandatos")
    for s in sens for m in s["mandatos"] for e in m["exercicios"]])

NOTA = ("\n---\nFontes: Senado Federal (Dados Abertos: senador, mandatos, autorias, processo, votação, discursos; CEAPS), "
        f"Portal da Transparência/CGU (emendas). Gerado em {data_br(HOJE)} por `scripts/gerar.py`. Método e limites em "
        "[METODOLOGIA.md](../METODOLOGIA.md); verificação em [VERIFICACAO.md](../VERIFICACAO.md).\n")
os.makedirs(os.path.join(BASE_DIR, "senadores"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "legislaturas"), exist_ok=True)

# ------------------------------------------------------------------ dossiê de cada senador
for s in sens:
    c = s["codigo"]
    o = [f"# {s['nome']}\n"]
    if os.path.exists(os.path.join(BASE_DIR, "fotos", PID.get(c, "-") + ".jpg")):  # foto oficial da Casa, gravada por tse.py
        o.append(f"<img src=\"../fotos/{PID[c]}.jpg\" width=\"110\" align=\"right\">\n")
    o.append(tabela(("Campo", "Dado"), [
        ("Nome completo", s.get("nome_completo") or "—"),
        ("Nascimento", f"{data_br(s.get('nascimento'))} — {s.get('naturalidade') or '—'}/{s.get('uf_naturalidade') or '—'}"),
        ("Partidos (filiações)", ", ".join(f"{f['partido']} ({data_br(f['filiacao'])}{' a ' + data_br(f['desfiliacao']) if f.get('desfiliacao') else ''})" for f in s["filiacoes"]) or "—"),
        ("Página oficial", s.get("pagina") or "—")]))
    o.append(trajetoria(PID.get(c, "")))
    o.append("\n## Mandatos pelo AM\n")
    o.append(tabela(("Mandato", "Condição", "Titular", "Suplentes", "Exercícios"), [
        (f"{data_br(m['inicio'])} a {data_br(m['fim'])}", m["participacao"] or "—", m.get("titular") or "—", "; ".join(m["suplentes"]) or "—",
         "; ".join(f"{data_br(e['inicio'])} a {data_br(e['fim']) if e['fim'] else 'atual'}" + (f" ({e['causa_afastamento']})" if e.get("causa_afastamento") else "")
                   for e in m["exercicios"]) or "não exerceu") for m in s["mandatos"]]))
    L_ = s["legislaturas"]
    o.append("\n## Indicadores por legislatura\n")
    o.append(tabela(("Indicador",) + tuple(nome_leg(L) for L in L_), [
        (rot,) + tuple(f(IDX[(c, L)]) for L in L_) for rot, f in [
            ("Dias em exercício", lambda r: r["dias_exercicio"]),
            ("Matérias apresentadas (todos os tipos)", lambda r: r["materias"]),
            ("Projetos e PECs como 1º autor", lambda r: r["legislativas_principal"]),
            ("Requerimentos", lambda r: r["requerimentos"]),
            ("**Normas geradas – 1º autor**", lambda r: f"**{r['normas_principal']}**"),
            ("Normas geradas – coautor", lambda r: r["normas_coautor"]),
            ("Votações nominais: presente", lambda r: f"{r['presente']}/{r['votacoes']} ({pct(r['presente'], r['votacoes'])})" if r["votacoes"] else "sem dado"),
            ("Ausência justificada (licença, missão, atividade parlamentar)", lambda r: r["ausencia_justificada"]),
            ("Não compareceu (sem justificativa)", lambda r: r["nao_compareceu"]),
            ("Discursos", lambda r: r["discursos"]),
            ("CEAPS (cota)", lambda r: brl(r["ceaps"]) if r["ceaps"] else "—"),
            ("Emendas empenhadas", lambda r: brl(r["emendas_empenhado"]) if r["emendas_empenhado"] else "—"),
            ("Emendas pagas", lambda r: brl(r["emendas_pago"]) if r["emendas_pago"] else "—")]]))
    nr = sorted([i for i in autorias.get(c, []) if i["norma"]], key=lambda i: i["norma_data"])
    o.append(f"\n## Normas geradas por matérias de sua autoria ({len(nr)})\n")
    o.append(tabela(("Matéria", "Norma", "Data", "Autoria", "Ementa"), [
        (f"[{i['identificacao']}]({i['url']})", i["norma"], data_br(i["norma_data"]), "1º autor" if i["principal"] else "coautor",
         (i.get("ementa") or "")[:180]) for i in nr]) if nr else "Nenhuma.\n")
    cnt = Counter(i["sigla"] for i in autorias.get(c, []))
    cp = Counter(i["sigla"] for i in autorias.get(c, []) if i["principal"])
    o.append(f"\n## Produção por tipo ({sum(cnt.values())} matérias)\n")
    o.append(tabela(("Tipo", "Descrição", "Total", "Como 1º autor"), [(t, NOME_TIPO.get(t, ""), n, cp[t]) for t, n in cnt.most_common()]))
    pls = sorted([i for i in autorias.get(c, []) if i["principal"] and i["sigla"] in LEGISLATIVOS], key=lambda i: i["data"] or "", reverse=True)
    if pls:
        o.append(f"\n### Projetos e PECs como 1º autor ({len(pls)})\n")
        o.append(tabela(("Matéria", "Apresentação", "Situação", "Ementa"),
                        [(f"[{i['identificacao']}]({i['url']})", data_br(i["data"]), i.get("situacao") or "—", (i.get("ementa") or "")[:150]) for i in pls]))
    vv = Counter(v["voto"] for v in votacoes.get(c, []) if v["voto"])
    if vv:
        o.append("\n## Registro nas votações nominais\n")
        o.append(tabela(("Registro", "Quantidade"), vv.most_common()))
    anos_c = sorted({a for (k, a) in ceaps if k == c})
    if anos_c:
        tot = Counter()
        for a in anos_c:
            tot.update(ceaps[(c, a)])
        T = sum(tot.values())
        o.append(f"\n## Cota (CEAPS) por tipo de despesa — {anos_c[0]} a {anos_c[-1]}\n\nTotal reembolsado: **{brl(T)}**.\n\n")
        o.append(tabela(("Tipo de despesa", "Valor", "%"), [(k, brl(v), pct(v, T)) for k, v in tot.most_common()]))
        o.append("\n### Por ano\n")
        o.append(tabela(("Ano", "Valor"), [(a, brl(sum(ceaps[(c, a)].values()))) for a in anos_c]))
        o.append("\n### Maiores fornecedores\n")
        o.append(tabela(("Fornecedor", "CNPJ", "Valor"), [(f, cn or "(pessoa física)", brl(v)) for (f, cn), v in ceaps_forn[c].most_common(10)]))
    anos_e = sorted({a for (k, a) in emendas if k == c})
    if anos_e:
        fun = defaultdict(lambda: [0.0, 0.0])
        for a in anos_e:
            for k, (e, p_) in emendas[(c, a)].items():
                fun[k][0] += e; fun[k][1] += p_
        te = sum(v[0] for v in fun.values())
        o.append(f"\n## Emendas parlamentares individuais — {anos_e[0]} a {anos_e[-1]}\n")
        o.append(f"Empenhado: **{brl(te)}** · pago: **{brl(sum(v[1] for v in fun.values()))}**.\n\n")
        o.append(tabela(("Segmento (função)", "Empenhado", "Pago", "%"), [(k, brl(e), brl(p_), pct(e, te)) for k, (e, p_) in sorted(fun.items(), key=lambda i: -i[1][0]) if e]))
        o.append("\n### Por ano\n")
        o.append(tabela(("Ano", "Emendas", "Empenhado", "Pago"), [(a, len(emendas_qtd[(c, a)]), brl(sum(v[0] for v in emendas[(c, a)].values())),
                                                                  brl(sum(v[1] for v in emendas[(c, a)].values()))) for a in anos_e]))
        o.append("\n### Principais destinos\n")
        o.append(tabela(("Localidade", "Empenhado"), [(m, brl(v)) for m, v in emendas_mun[c].most_common(10)]))
    if s["cargos"]:
        o.append(f"\n## Cargos em comissões ({len(s['cargos'])})\n")
        o.append(tabela(("Cargo", "Comissão", "Início", "Fim"), [(x["cargo"], x["comissao"] or "—", data_br(x["inicio"]), data_br(x["fim"])) for x in s["cargos"]]))
    tit = [x for x in s["comissoes"] if x["participacao"] == "Titular"]
    if tit:
        o.append(f"\nFoi titular de {len(tit)} comissões, entre elas: " + ", ".join(sorted({x['sigla'] for x in tit})[:40]) + ".\n")
    if s["licencas"]:
        tl = Counter(x["tipo"] for x in s["licencas"])
        o.append(f"\n## Licenças e afastamentos ({len(s['licencas'])})\n")
        o.append(tabela(("Tipo", "Quantidade"), tl.most_common()))
    o.append(NOTA)
    with open(os.path.join(BASE_DIR, "senadores", s["slug"] + ".md"), "w", encoding="utf-8") as f:
        f.write("\n".join(o))

# ------------------------------------------------------------------ dossiê de cada legislatura
for L in sorted({r["legislatura"] for r in RES}):
    rs = sorted([r for r in RES if r["legislatura"] == L], key=lambda r: (-r["normas_principal"], -r["legislativas_principal"]))
    a, b = leg_datas(L)
    o = [f"# {L}ª Legislatura ({data_br(a)} a {data_br(b)}) — senadores do Amazonas\n"]
    if b > HOJE:
        o.append(f"> Legislatura em curso: dados até {data_br(HOJE)}.\n")
    o.append(f"\n## Quem exerceu mandato ({len(rs)})\n")
    o.append("Presença = votações nominais em que o senador estava presente (votou, ou presente sem registrar voto) ÷ votações "
             "em que constava da lista. Ausência justificada = licença, missão ou atividade parlamentar; \"não compareceu\" = sem justificativa.\n\n")
    o.append(tabela(("Senador", "Dias", "Matérias", "Projetos/PECs 1º autor", "Normas 1º autor", "Normas coautor", "Presença",
                     "Não compareceu", "Discursos", "CEAPS", "Emendas empenhadas"),
                    [(f"[{S[r['codigo']]['nome']}](../senadores/{S[r['codigo']]['slug']}.md)", r["dias_exercicio"], r["materias"],
                      r["legislativas_principal"], r["normas_principal"], r["normas_coautor"],
                      pct(r["presente"], r["votacoes"]) if r["votacoes"] else "s/d", r["nao_compareceu"], r["discursos"],
                      brl(r["ceaps"]) if r["ceaps"] else "—", brl(r["emendas_empenhado"]) if r["emendas_empenhado"] else "—") for r in rs]))
    nr = sorted([(r["codigo"], i) for r in rs for i in autorias.get(r["codigo"], []) if i["norma_data"] and leg_de_data(i["norma_data"]) == L],
                key=lambda x: x[1]["norma_data"])
    o.append(f"\n## Normas geradas na legislatura por matérias da bancada ({len(nr)})\n")
    o.append(tabela(("Senador", "Matéria", "Norma", "Data", "Autoria", "Ementa"),
                    [(S[c]["nome"], f"[{i['identificacao']}]({i['url']})", i["norma"], data_br(i["norma_data"]),
                      "1º autor" if i["principal"] else "coautor", (i.get("ementa") or "")[:140]) for c, i in nr]) if nr else "Nenhuma.\n")
    anos = [str(x) for x in range(int(a[:4]), int(a[:4]) + 4)]
    seg = defaultdict(float)
    for r in rs:
        for x in anos:
            for k, (e, _) in emendas[(r["codigo"], x)].items():
                seg[k] += e
    if seg:
        ts = sum(seg.values())
        o.append("\n## Emendas individuais por segmento\n")
        o.append(tabela(("Segmento (função)", "Empenhado", "%"), [(k, brl(v), pct(v, ts)) for k, v in sorted(seg.items(), key=lambda i: -i[1]) if v]))
    o.append(NOTA)
    with open(os.path.join(BASE_DIR, "legislaturas", arq_leg(L)), "w", encoding="utf-8") as f:
        f.write("\n".join(o))

# ------------------------------------------------------------------ README
o = ["# Senadores do Amazonas (1999 em diante)\n",
     "Dossiê dos senadores que exerceram mandato pelo Amazonas desde 1999 (titulares e suplentes em exercício): mandatos, "
     "matérias apresentadas, normas geradas, presença nas votações nominais, discursos, cota parlamentar (CEAPS) e emendas "
     "ao orçamento. Só dados oficiais (Senado Federal e CGU), com verificação de integridade em [VERIFICACAO.md](VERIFICACAO.md).\n",
     f"Atualizado em {data_br(HOJE)}. O mandato de senador dura 8 anos (duas legislaturas).\n", "\n## Legislaturas\n"]
for L in sorted({r["legislatura"] for r in RES}):
    rs = [r for r in RES if r["legislatura"] == L]
    o.append(f"- [{nome_leg(L)}](legislaturas/{arq_leg(L)}) — {len(rs)} senadores em exercício")
o.append("\n\n## Senadores\n")
lin = []
for s in sorted(sens, key=lambda s: s["slug"]):
    rs = [IDX[(s["codigo"], L)] for L in s["legislaturas"]]
    lin.append((f"[{s['nome']}](senadores/{s['slug']}.md)", "; ".join(f"{data_br(a)} a {data_br(b)}" for a, b, _ in s["exercicio"]),
                sum(r["materias"] for r in rs), sum(1 for i in autorias.get(s["codigo"], []) if i["norma"] and i["principal"] and i["norma_data"] >= "1999-02-01"),
                pct(sum(r["presente"] for r in rs), sum(r["votacoes"] for r in rs)) if sum(r["votacoes"] for r in rs) else "s/d",
                brl(sum(r["ceaps"] for r in rs)), brl(sum(r["emendas_empenhado"] for r in rs))))
o.append(tabela(("Senador", "Exercício (desde 1999)", "Matérias", "Normas 1º autor", "Presença em votações", "CEAPS", "Emendas"), lin))
o.append("\n## Como atualizar\n\n```\npython -I scripts/coletar.py\npython -I scripts/tse.py      # pessoa_id, candidaturas e fotos (modelo comum da plataforma)\npython -I scripts/gerar.py\npython -I scripts/verificar.py\n```\n")
with open(os.path.join(BASE_DIR, "README.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(o))
print(len(sens), "senadores;", len(RES), "senador×legislatura; votos sem classificação:",
      Counter(v["voto"] for vs in votacoes.values() for v in vs if v["voto"] and v["voto"] not in PRESENTE | NAO_COMPARECEU))
print("emendas descartadas (sem exercício no cargo ao apresentar):", dict(emendas_fora))
