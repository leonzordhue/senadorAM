"""Coleta dados oficiais dos senadores do Amazonas que exerceram mandato de 1999 em diante.

Fontes (todas oficiais e abertas):
  - API Dados Abertos do Senado ....... legis.senado.leg.br/dadosabertos (senador, mandatos, autorias, processo, votacao)
  - CEAPS (cota do Senado) ............ senado.leg.br/transparencia/LAI/verba/despesa_ceaps_<ano>.csv
  - Emendas parlamentares (CGU) ....... portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares/UNICO

Uso: python -I scripts/coletar.py [etapa ...]
  etapas: senadores autorias votacoes discursos ceaps emendas   (sem argumento = todas)
Retomável: o que já foi baixado fica em _cache/.
"""
import csv, io, json, os, re, sys, time, unicodedata, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor

import truststore  # a rede da SEINFRA quebra a cadeia de certificados: usar os certificados do Windows
truststore.inject_into_ssl()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE_DIR, "_cache")
DADOS = os.path.join(BASE_DIR, "dados")
API = "https://legis.senado.leg.br/dadosabertos/"
INICIO = "1999-02-01"
ANO_FIM = time.localtime().tm_year
UA = {"User-Agent": "Mozilla/5.0 (pesquisa DMOB/SEINFRA-AM)", "Accept": "application/json"}
# tipos de proposição que podem virar norma
LEGISLATIVOS = {"PLS", "PL", "PLC", "PEC", "PLP", "PDS", "PDL", "PRS", "PLV", "MPV"}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def api(path, timeout=180):
    for t in range(5):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(API + path, headers=UA), timeout=timeout))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if 400 <= e.code < 500:
                raise
            err = e
        except Exception as e:
            err = e
        time.sleep(5 * (t + 1))
    raise err


def baixar_arquivo(url, destino):
    """Baixa o arquivo inteiro para o disco, retomando com Range se a conexão cair, e só aceita
    o resultado se o tamanho bater com o Content-Length do servidor. Devolve None em 404."""
    if os.path.exists(destino):
        return destino
    tmp = destino + ".part"
    for t in range(10):
        pos = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        # sem o Accept: application/json do UA, que o servidor do Senado recusa (406) para CSV
        h = {"User-Agent": UA["User-Agent"], **({"Range": f"bytes={pos}-"} if pos else {})}
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=600)
            if pos and r.status != 206:  # servidor ignorou o Range: recomeça
                pos = 0
            esperado = pos + int(r.headers["Content-Length"]) if r.headers.get("Content-Length") else None
            with open(tmp, "ab" if pos else "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 416 and pos:  # já estava completo
                esperado = pos
            else:
                time.sleep(5 * (t + 1)); continue
        except Exception:
            time.sleep(5 * (t + 1)); continue
        tam = os.path.getsize(tmp)
        if esperado is None or tam == esperado:
            os.replace(tmp, destino)
            with open(destino + ".bytes", "w") as f:  # prova de integridade: bytes recebidos = Content-Length
                f.write(f"{tam} {esperado}")
            return destino
    raise IOError(f"download incompleto após 10 tentativas: {url}")


def api_tudo(path):
    sep = "&" if "?" in path else "?"
    out, pag = [], 1
    while True:
        j = api(f"{path}{sep}itens=100&pagina={pag}")
        if not j:
            return out
        out += j["dados"]
        if not any(l["rel"] == "next" for l in j.get("links", [])):
            return out
        pag += 1


def salvar_json(nome, obj):
    with open(os.path.join(DADOS, nome), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def ler_json(nome):
    with open(os.path.join(DADOS, nome), encoding="utf-8") as f:
        return json.load(f)


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9 ]", "", s).strip()


def lista(x):
    return x if isinstance(x, list) else ([] if x is None else [x])


def salvar_json(nome, obj, pasta=DADOS):
    with open(os.path.join(pasta, nome), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def ler_json(nome, pasta=DADOS):
    with open(os.path.join(pasta, nome), encoding="utf-8") as f:
        return json.load(f)


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9 ]", "", s).strip()


# ---------------------------------------------------------------- senadores
def etapa_senadores():
    j = api("senador/lista/legislatura/51/57?uf=AM")
    cods = {p["IdentificacaoParlamentar"]["CodigoParlamentar"] for p in
            lista(j["ListaParlamentarLegislatura"]["Parlamentares"]["Parlamentar"])}
    sens = []
    for c in sorted(cods, key=int):
        det = api(f"senador/{c}")["DetalheParlamentar"]["Parlamentar"]
        ide, db = det["IdentificacaoParlamentar"], det.get("DadosBasicosParlamentar", {})
        mand = lista(api(f"senador/{c}/mandatos")["MandatoParlamentar"]["Parlamentar"].get("Mandatos", {}).get("Mandato"))
        mandatos, exercicios = [], []
        for m in mand:
            if m.get("UfParlamentar") != "AM":
                continue
            ex = [{"inicio": e.get("DataInicio"), "fim": e.get("DataFim"), "causa_afastamento": e.get("DescricaoCausaAfastamento")}
                  for e in lista(m.get("Exercicios", {}).get("Exercicio"))]
            mandatos.append({"codigo": m.get("CodigoMandato"), "participacao": m.get("DescricaoParticipacao"),
                             "legislaturas": [m[k]["NumeroLegislatura"] for k in ("PrimeiraLegislaturaDoMandato", "SegundaLegislaturaDoMandato") if k in m],
                             "inicio": m.get("PrimeiraLegislaturaDoMandato", {}).get("DataInicio"),
                             "fim": m.get("SegundaLegislaturaDoMandato", m.get("PrimeiraLegislaturaDoMandato", {})).get("DataFim"),
                             "titular": (m.get("Titular") or {}).get("NomeParlamentar"),
                             "suplentes": [s["NomeParlamentar"] + " (" + s["DescricaoParticipacao"] + ")" for s in lista(m.get("Suplentes", {}).get("Suplente"))],
                             "exercicios": ex})
            exercicios += ex
        # só entra quem exerceu de fato a partir de 1999
        if not any((e["fim"] or "9999") >= INICIO for e in exercicios):
            log("sem exercício desde 1999:", c, ide["NomeParlamentar"]); continue
        fil = lista(api(f"senador/{c}/filiacoes")["FiliacaoParlamentar"]["Parlamentar"].get("Filiacoes", {}).get("Filiacao"))
        com = lista(api(f"senador/{c}/comissoes")["MembroComissaoParlamentar"]["Parlamentar"].get("MembroComissoes", {}).get("Comissao"))
        lic = api(f"senador/{c}/licencas")
        lic = lista(lic["LicencaParlamentar"]["Parlamentar"].get("Licencas", {}).get("Licenca")) if lic else []
        car = api(f"senador/{c}/cargos")
        car = lista(car["CargoParlamentar"]["Parlamentar"].get("Cargos", {}).get("Cargo")) if car else []
        sens.append(dict(
            codigo=c, nome=ide["NomeParlamentar"], nome_completo=ide.get("NomeCompletoParlamentar"),
            sexo=ide.get("SexoParlamentar"), foto=ide.get("UrlFotoParlamentar"), pagina=ide.get("UrlPaginaParlamentar"),
            nascimento=db.get("DataNascimento"), naturalidade=db.get("Naturalidade"), uf_naturalidade=db.get("UfNaturalidade"),
            mandatos=mandatos,
            filiacoes=[{"partido": f["Partido"]["SiglaPartido"], "filiacao": f.get("DataFiliacao"), "desfiliacao": f.get("DataDesfiliacao")} for f in fil],
            comissoes=[{"sigla": x["IdentificacaoComissao"].get("SiglaComissao"), "nome": x["IdentificacaoComissao"].get("NomeComissao"),
                        "casa": x["IdentificacaoComissao"].get("SiglaCasaComissao"), "participacao": x.get("DescricaoParticipacao"),
                        "inicio": x.get("DataInicio"), "fim": x.get("DataFim")} for x in com],
            licencas=[{"inicio": x.get("DataInicio"), "fim": x.get("DataFim"), "tipo": x.get("DescricaoTipoAfastamento")} for x in lic],
            cargos=[{"cargo": x.get("DescricaoCargo"), "comissao": (x.get("IdentificacaoComissao") or {}).get("NomeComissao"),
                     "inicio": x.get("DataInicio"), "fim": x.get("DataFim")} for x in car]))
        log("senador", c, ide["NomeParlamentar"], [e["inicio"] for e in exercicios])
    salvar_json("senadores.json", sens)
    log(len(sens), "senadores com exercício desde 1999")


# ---------------------------------------------------------------- autorias + situação/norma
def etapa_autorias():
    sens = ler_json("senadores.json")
    out = ler_json("autorias.json") if os.path.exists(os.path.join(DADOS, "autorias.json")) else {}
    proc_cache = ler_json("processos.json", CACHE) if os.path.exists(os.path.join(CACHE, "processos.json")) else {}
    for s in sens:
        c = s["codigo"]
        if c in out:
            continue
        j = api(f"senador/{c}/autorias")
        aut = lista(j["MateriasAutoriaParlamentar"]["Parlamentar"].get("Autorias", {}).get("Autoria")) if j else []
        itens = [{"codigo_materia": a["Materia"]["Codigo"], "id_processo": a["Materia"].get("IdentificacaoProcesso"),
                  "sigla": a["Materia"]["Sigla"], "numero": a["Materia"]["Numero"], "ano": a["Materia"]["Ano"],
                  "identificacao": a["Materia"]["DescricaoIdentificacao"], "ementa": a["Materia"].get("Ementa"),
                  "data": a["Materia"].get("Data"), "principal": a.get("IndicadorAutorPrincipal") == "Sim"} for a in aut]
        alvo = [i["id_processo"] for i in itens if i["sigla"] in LEGISLATIVOS and i["id_processo"] and i["id_processo"] not in proc_cache]

        def um(pid):
            d = api(f"processo/{pid}") or {}
            ng = d.get("normaGerada") or {}
            return pid, {"situacao": d.get("situacaoAtual"), "data_situacao": d.get("dataSituacaoAtual"),
                         "norma": ng.get("descricao") or "", "norma_tipo": ng.get("tipo") or "",
                         "norma_data": ng.get("dataAssinatura") or "",
                         "norma_raw": ng, "autores": [a.get("autor") for a in d.get("autoriaIniciativa", [])],
                         "outros_numeros": [f"{o.get('sigla')} {int(o['numero']) if str(o.get('numero','')).isdigit() else o.get('numero')}/{o.get('ano')}"
                                            for o in d.get("outrosNumeros", [])]}

        with ThreadPoolExecutor(6) as ex:
            for pid, v in ex.map(um, alvo):
                proc_cache[pid] = v
        salvar_json("processos.json", proc_cache, CACHE)
        for i in itens:
            i.update({k: v for k, v in proc_cache.get(i["id_processo"], {}).items() if k != "norma_raw"})
        out[c] = itens
        salvar_json("autorias.json", out)
        log("autorias", s["nome"], len(itens), "matérias;", len(alvo), "processos lidos")


# ---------------------------------------------------------------- votações nominais
def etapa_votacoes():
    sens = ler_json("senadores.json")
    pasta = os.path.join(CACHE, "votacoes"); os.makedirs(pasta, exist_ok=True)
    out = {}
    for s in sens:
        anos = set()
        for m in s["mandatos"]:
            for e in m["exercicios"]:
                a0 = max(int((e["inicio"] or INICIO)[:4]), 1999)
                a1 = int((e["fim"] or f"{ANO_FIM}")[:4])
                anos |= set(range(a0, a1 + 1))
        votos = []
        for ano in sorted(anos):
            arq = os.path.join(pasta, f"{s['codigo']}-{ano}.json")
            if not os.path.exists(arq) or ano == ANO_FIM:
                vs = api(f"votacao?codigoParlamentar={s['codigo']}&dataInicio={ano}-01-01&dataFim={ano}-12-31", 300) or []
                salvar_json(os.path.basename(arq), vs, pasta)
            for v in ler_json(os.path.basename(arq), pasta):
                meu = [x for x in v.get("votos", []) if str(x.get("codigoParlamentar")) == s["codigo"]]
                votos.append({"data": v.get("dataSessao"), "codigo_votacao": v.get("codigoSessaoVotacao"),
                              "materia": v.get("identificacao"), "descricao": (v.get("descricaoVotacao") or "")[:200],
                              "secreta": v.get("votacaoSecreta"), "resultado": v.get("resultadoVotacao"),
                              "voto": meu[0].get("siglaVotoParlamentar") if meu else None})
        out[s["codigo"]] = votos
        log("votações", s["nome"], len(votos))
    salvar_json("votacoes.json", out)


# ---------------------------------------------------------------- discursos (contagem)
def etapa_discursos():
    sens = ler_json("senadores.json")
    out = {}
    for s in sens:
        d = []
        for m in s["mandatos"]:
            for e in m["exercicios"]:
                a0 = max(int((e["inicio"] or INICIO)[:4]), 1999); a1 = int((e["fim"] or f"{ANO_FIM}")[:4])
                for ano in range(a0, a1 + 1):
                    j = api(f"senador/{s['codigo']}/discursos?dataInicio={ano}0101&dataFim={ano}1231")
                    p = j["DiscursosParlamentar"]["Parlamentar"] if j else {}
                    for x in lista((p.get("Pronunciamentos") or {}).get("Pronunciamento")):
                        d.append({"data": x.get("DataPronunciamento"), "tipo": x.get("TipoUsoPalavra", {}).get("Descricao"),
                                  "resumo": (x.get("TextoResumo") or "")[:300], "url": x.get("UrlTexto")})
        uniq = {(x["data"], x["resumo"]): x for x in d}
        out[s["codigo"]] = sorted(uniq.values(), key=lambda x: x["data"] or "")
        log("discursos", s["nome"], len(out[s["codigo"]]))
    salvar_json("discursos.json", out)


# ---------------------------------------------------------------- CEAPS
def etapa_ceaps():
    sens = ler_json("senadores.json")
    nomes = {norm(s["nome"]): s["codigo"] for s in sens}
    linhas, total = [], {}
    for ano in range(2008, ANO_FIM + 1):
        arq = os.path.join(CACHE, f"ceaps-{ano}.csv")
        if not os.path.exists(arq) or ano == ANO_FIM:
            if os.path.exists(arq):
                os.remove(arq)
            baixar_arquivo(f"https://www.senado.leg.br/transparencia/LAI/verba/despesa_ceaps_{ano}.csv", arq)
        with open(arq, encoding="latin-1", newline="") as f:
            f.readline()  # "ULTIMA ATUALIZACAO"
            rd = csv.DictReader(f, delimiter=";")
            n = 0
            for row in rd:
                n += 1
                c = nomes.get(norm(row["SENADOR"]))
                if c:
                    doc = re.sub(r"\D", "", row["CNPJ_CPF"])
                    linhas.append({"codigo": c, "ano": row["ANO"], "mes": row["MES"], "tipo": row["TIPO_DESPESA"],
                                   "cnpj": row["CNPJ_CPF"] if len(doc) == 14 else "",  # CPF fica fora (LGPD)
                                   "fornecedor": row["FORNECEDOR"], "data": row["DATA"],
                                   "valor": row["VALOR_REEMBOLSADO"]})
            total[ano] = n
    with open(os.path.join(DADOS, "ceaps.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0])); w.writeheader(); w.writerows(linhas)
    salvar_json("ceaps_linhas_lidas.json", total, CACHE)
    log(len(linhas), "despesas CEAPS")


# ---------------------------------------------------------------- emendas (CGU)
def etapa_emendas():
    sens = ler_json("senadores.json")
    nomes = {norm(s["nome"]): s["codigo"] for s in sens}
    zp = os.path.join(CACHE, "EmendasParlamentares.zip")
    if not os.path.exists(zp):
        baixar_arquivo("https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares/UNICO", zp)
    with zipfile.ZipFile(zp) as z:
        rd = csv.reader(io.TextIOWrapper(z.open("EmendasParlamentares.csv"), encoding="latin-1", newline=""), delimiter=";")
        cab = next(rd)
        linhas, autores = [], {}
        for r in rd:
            c = nomes.get(norm(r[4]))
            if c:
                linhas.append([c] + r); autores[r[3]] = {"nome_cgu": r[4], "codigo": c}
    with open(os.path.join(DADOS, "emendas.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["codigoSenador"] + cab); w.writerows(linhas)
    salvar_json("emendas_autores.json", autores)
    log(len(linhas), "linhas de emenda;", autores)


ETAPAS = {"senadores": etapa_senadores, "autorias": etapa_autorias, "votacoes": etapa_votacoes,
          "discursos": etapa_discursos, "ceaps": etapa_ceaps, "emendas": etapa_emendas}

# as fotos ficam em scripts/tse.py (fotos/<pessoa_id>.jpg, modelo comum da plataforma)

if __name__ == "__main__":
    os.makedirs(CACHE, exist_ok=True); os.makedirs(DADOS, exist_ok=True)
    for e in sys.argv[1:] or ETAPAS:
        log("== etapa", e); ETAPAS[e]()
