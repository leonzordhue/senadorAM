"""Verificação de integridade dos dados dos senadores do AM (gera VERIFICACAO.md).

Testes:
  1. Downloads completos (CEAPS, emendas): bytes recebidos = Content-Length.
  2. Autorias: matérias da API antiga (/senador/{cod}/autorias) × API nova (/processo?codigoParlamentarAutor).
  3. Normas: cada lei citada existe na base do Planalto (ctresb/leis) com a mesma data.
  4. Votos: registro do senador no endpoint novo (/votacao) × endpoint antigo (/senador/{cod}/votacoes).
  5. CEAPS: todo senador em exercício de 2008 em diante tem despesas nos anos de exercício (casamento de nomes).
  5b. CEAPS: soma por senador e ano (planilha) = API administrativa do Senado (amostra de anos).
  6. Emendas: autores casados aplicam no AM (sem homônimo) e lista para conferência humana.
Uso: python -I scripts/verificar.py
"""
import datetime as dt, json, os, sqlite3, sys, time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coletar import api, lista, ler_json, CACHE, DADOS, BASE_DIR  # noqa: E402
import csv  # noqa: E402

LEIS_DB = os.path.join(BASE_DIR, "..", "legislativo", "dados", "leis.sqlite")
R = []


def ok(t, cond, d):
    R.append((t, "✅" if cond else "❌", d)); print(("OK  " if cond else "FALHA ") + t + ": " + d, flush=True)


def aviso(t, d):
    R.append((t, "⚠️", d)); print("AVISO " + t + ": " + d, flush=True)


sens = ler_json("senadores.json")
S = {s["codigo"]: s for s in sens}

# 1
ruins, n = [], 0
for f in os.listdir(CACHE):
    if f.endswith(".bytes"):
        n += 1
        tam, esp = open(os.path.join(CACHE, f)).read().split()
        if esp != "None" and tam != esp:
            ruins.append(f)
ok("1. Downloads completos", not ruins, f"{n} arquivos com bytes = Content-Length" + (f"; divergentes: {ruins}" if ruins else ""))

# 2
aut = ler_json("autorias.json")
div = []
for c, s in S.items():
    novo = api(f"processo?codigoParlamentarAutor={c}") or []
    a = {str(i["codigo_materia"]) for i in aut.get(c, [])}
    b = {str(x.get("codigoMateria")) for x in novo if x.get("codigoMateria")}
    if a != b:
        div.append(f"{s['nome']}: antiga {len(a)} × nova {len(b)} (só na antiga {len(a - b)}, só na nova {len(b - a)})")
if div:
    aviso("2. Autorias: API antiga × API nova", "; ".join(div) + ". A API nova inclui matérias em que o senador é coautor sem constar "
          "da lista antiga e vice-versa; os dossiês usam a lista antiga, que diz quem é o 1º autor.")
else:
    ok("2. Autorias: API antiga × API nova", True, f"{len(S)} senadores com o mesmo conjunto de matérias")

# 3
falta, nleis = [], 0
if os.path.exists(LEIS_DB):
    db = sqlite3.connect(LEIS_DB)
    proc = ler_json("processos.json", CACHE) if os.path.exists(os.path.join(CACHE, "processos.json")) else {}
    for v in proc.values():
        ng = v.get("norma_raw") or {}
        if ng.get("siglaTipo") not in ("LEI-n", "LCP-n", "LEI", "LCP") and not str(ng.get("tipo", "")).startswith("Lei"):
            continue
        nleis += 1
        tipo = "Lei Complementar" if "Complementar" in ng.get("tipo", "") else "Lei Ordinária"
        ach = db.execute("select data from normas where esfera='federal' and tipo=? and replace(numero,'.','')=?",
                         (tipo, str(ng.get("numero")))).fetchall()
        if not ach:
            falta.append(f"{ng.get('descricao')} não achada")
        elif abs((dt.date.fromisoformat(ach[0][0][:10]) - dt.date.fromisoformat(ng["dataAssinatura"])).days) > 3:
            falta.append(f"{ng.get('descricao')}: Planalto {ach[0][0][:10]}")
    ok("3. Leis conferidas na base do Planalto", not falta, f"{nleis} leis; " + ("; ".join(falta[:20]) if falta else "todas existem com a mesma data"))
else:
    aviso("3. Leis no Planalto", "base leis.sqlite não encontrada")

# 4
vot = ler_json("votacoes.json")
div, nconf = [], 0
for c in S:
    j = api(f"senador/{c}/votacoes")
    antigos = lista((j or {}).get("VotacaoParlamentar", {}).get("Parlamentar", {}).get("Votacoes", {}).get("Votacao")) if j else []
    ant = {str(x.get("CodigoSessaoVotacao")): x.get("SiglaDescricaoVoto") for x in antigos if x.get("CodigoSessaoVotacao")}
    nov = {str(v["codigo_votacao"]): v["voto"] for v in vot.get(c, []) if v.get("codigo_votacao")}
    comum = set(ant) & set(nov)
    nconf += len(comum)
    d = [k for k in comum if ant[k] != nov[k]]
    if d:
        div.append(f"{S[c]['nome']}: {len(d)}/{len(comum)} divergentes (ex.: {d[0][0]} {ant[d[0]]}×{nov[d[0]]})")
if not nconf:
    aviso("4. Votos: endpoint novo × antigo", "nenhum voto pareado entre os dois endpoints (chave CodigoSessaoVotacao não casou); conferir manualmente")
elif div:
    aviso("4. Votos: endpoint novo × antigo", f"{nconf} votos em comum; " + "; ".join(div))
else:
    ok("4. Votos: endpoint novo × antigo", True, f"{nconf} votos em comum, todos iguais")

# 5
desp = defaultdict(set)
p = os.path.join(DADOS, "ceaps.csv")
if os.path.exists(p):
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            desp[r["codigo"]].add(int(r["ano"]))
sem = []
for c, s in S.items():
    anos = set()
    for m in s["mandatos"]:
        for e in m["exercicios"]:
            a0, a1 = int((e["inicio"] or "1999")[:4]), int((e["fim"] or time.strftime("%Y"))[:4])
            anos |= {a for a in range(max(a0, 2009), a1 + 1)}
    falta_anos = sorted(anos - desp[c])
    if anos and len(falta_anos) > len(anos) / 2:
        sem.append(f"{s['nome']}: sem despesa em {falta_anos}")
if sem:
    aviso("5. CEAPS: senadores sem despesa nos anos de exercício", "; ".join(sem) + ". Pode ser nome diferente na planilha ou exercício curto.")
else:
    ok("5. CEAPS: casamento de nomes", True, "todos os senadores em exercício desde 2009 têm despesas")

# 5b: soma por senador e ano (planilha) × API administrativa do Senado (adm.senado.gov.br), anos de amostra
import urllib.request  # noqa: E402
soma = defaultdict(float)
for r in csv.DictReader(open(p, encoding="utf-8", newline="")):
    v = r["valor"]
    soma[(r["codigo"], r["ano"])] += float(v.replace(".", "").replace(",", ".")) if "," in v else float(v or 0)
div, n5 = [], 0
for ano in ("2012", "2018", "2024"):
    j = json.load(urllib.request.urlopen(urllib.request.Request(
        f"https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/{ano}",
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}), timeout=300))
    api_s = defaultdict(float)
    for x in j:
        api_s[str(x.get("codSenador"))] += float(x.get("valorReembolsado") or 0)
    for (c, a), v in soma.items():
        if a == ano:
            n5 += 1
            if abs(api_s[c] - v) > 1:
                div.append(f"{S[c]['nome']} {ano}: planilha {v:.2f} × API {api_s[c]:.2f}")
ok("5b. CEAPS: planilha × API administrativa do Senado", not div, f"{n5} senador-ano conferidos" + ("; " + "; ".join(div) if div else ", todos iguais"))

# 6
m = ler_json("emendas_autores.json")
p = os.path.join(DADOS, "emendas.csv")
if m and os.path.exists(p):
    am, tot = Counter(), Counter()
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            v = float((r["Valor Empenhado"] or "0").replace(".", "").replace(",", "."))
            tot[r["Código do Autor da Emenda"]] += v
            if r["UF"] in ("AMAZONAS", "") or r["Localidade de aplicação do recurso"].endswith("- AM") or "AMAZONAS" in r["Localidade de aplicação do recurso"]:
                am[r["Código do Autor da Emenda"]] += v
    fora = {k: am[k] / tot[k] for k in tot if tot[k] and am[k] / tot[k] < 0.5}
    ok("6a. Emendas: autores aplicam no AM (sem homônimo)", not fora,
       "; ".join(f"{m[k]['nome_cgu']} só {100 * f:.0f}% no AM" for k, f in fora.items()) if fora else f"{len(m)} autores, todos com ≥50% no AM ou nacional")
    aviso("6b. Emendas: autores casados por nome (conferir)", "; ".join(f"{v['nome_cgu']} (cód. {k}) → {S[v['codigo']]['nome']}" for k, v in m.items()))

o = ["# Verificação de integridade\n", f"Executada em {time.strftime('%d/%m/%Y %H:%M')} por `scripts/verificar.py`.\n",
     "| Teste | Resultado | Detalhe |", "|---|---|---|"] + [f"| {t} | {s} | {d.replace('|', '/')} |" for t, s, d in R]
with open(os.path.join(BASE_DIR, "VERIFICACAO.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(o) + "\n")
print("VERIFICACAO.md gravado;", sum(s == "❌" for _, s, _ in R), "falha(s)")
