"""Liga cada parlamentar ao cadastro de candidatos do TSE e gera as tabelas do modelo comum da plataforma
(projetos/pesquisa/PLATAFORMA-POLITICOS-AM.md): pessoa_id = sha1(título de eleitor)[:10].

O título é o mesmo em qualquer eleição, então quem foi prefeito, deputado e senador vira uma pessoa só
quando os repositórios (deputadosfederais, senadorAM, dossieprefeitosAM) forem juntados.

Fontes (TSE, Portal de Dados Abertos, cdn.tse.jus.br/estatistica/sead/odsele/):
  consulta_cand_<ano>.zip ............ candidatos das eleições gerais (membro do AM)
  votacao_candidato_munzona_<ano>.zip  votos (só o membro do AM é lido, por HTTP Range: o zip inteiro passa de 500 MB)
Saídas (dados/): pessoas.csv, identificadores.csv, candidaturas.csv, integridade/tse.md; fotos/<pessoa_id>.jpg
O mesmo arquivo serve aos dois repositórios: detecta deputados.json ou senadores.json.
Uso: python -I scripts/tse.py
"""
import csv, hashlib, io, json, os, re, shutil, time, unicodedata, urllib.request, zipfile
from collections import defaultdict

import truststore  # a rede da SEINFRA quebra a cadeia de certificados: usar os certificados do Windows
truststore.inject_into_ssl()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE_DIR, "_cache", "tse")
DADOS = os.path.join(BASE_DIR, "dados")
URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/{c}/{c}_{a}.zip"
ANOS = range(1994, time.localtime().tm_year + 1, 4)  # eleições gerais
UA = {"User-Agent": "Mozilla/5.0 (pesquisa DMOB/SEINFRA-AM)"}
csv.field_size_limit(2**31 - 1)

if os.path.exists(os.path.join(DADOS, "deputados.json")):
    SISTEMA, CARGO = "camara", "deputado_federal"
    PARL = [dict(id=str(d["id"]), nome=d["nome"], civil=d.get("nome_civil") or d["nome"], nasc=(d.get("nascimento") or "")[:10],
                 foto=d.get("foto")) for d in json.load(open(os.path.join(DADOS, "deputados.json"), encoding="utf-8"))]
else:
    SISTEMA, CARGO = "senado", "senador"
    PARL = [dict(id=str(s["codigo"]), nome=s["nome"], civil=s.get("nome_completo") or s["nome"], nasc=(s.get("nascimento") or "")[:10],
                 foto=s.get("foto")) for s in json.load(open(os.path.join(DADOS, "senadores.json"), encoding="utf-8"))]



def cargo(ds):
    """DS_CARGO do TSE -> vocabulário fixo do modelo comum (1º/2º suplente de senador viram suplente_senador)."""
    n = norm(ds)
    return "suplente_senador" if "SUPLENTE" in n else n.lower().replace("vice ", "vice-").replace(" ", "_")


def limpo(s):
    return "" if (s or "").startswith("#N") else s.strip()


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", s)).strip()


def pid(titulo):
    return hashlib.sha1(titulo.zfill(12).encode()).hexdigest()[:10]


def iso(d):
    """DD/MM/AAAA -> AAAA-MM-DD (o TSE usa o formato brasileiro; #NULO#/vazio -> '')."""
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", (d or "").strip())
    return f"{m[3]}-{m[2]}-{m[1]}" if m else ""


def abrir(url, h=None):
    for t in range(6):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=dict(UA, **(h or {}))), timeout=300)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = e
        except Exception as e:
            err = e
        time.sleep(5 * (t + 1))
    raise err


class HttpArquivo(io.RawIOBase):
    """Arquivo remoto só-leitura com seek, via HTTP Range: o zipfile lê o diretório central e um único membro."""

    def __init__(self, url):
        self.url, self.pos = url, 0
        r = abrir(url, {"Range": "bytes=0-0"})
        self.tam = int(r.headers["Content-Range"].split("/")[1])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.tam + off}[whence]
        return self.pos

    def readinto(self, b):
        if self.pos >= self.tam or not len(b):
            return 0
        fim = min(self.pos + len(b), self.tam) - 1
        for t in range(6):
            try:
                dados = abrir(self.url, {"Range": f"bytes={self.pos}-{fim}"}).read()
                if len(dados) == fim - self.pos + 1:
                    break
            except Exception:
                pass
            time.sleep(5 * (t + 1))
        else:
            raise IOError(f"leitura parcial falhou: {self.url} {self.pos}-{fim}")
        b[:len(dados)] = dados
        self.pos += len(dados)
        return len(dados)


def membro_am(c, ano, remoto=False):
    """Extrai o CSV do AM de <c>_<ano>.zip para _cache/tse/ e devolve o caminho (None se o TSE não tem o ano)."""
    destino = os.path.join(CACHE, f"{c}_{ano}_AM.csv")
    if os.path.exists(destino):
        return destino
    url = URL.format(c=c, a=ano)
    if remoto:
        try:
            fonte = io.BufferedReader(HttpArquivo(url), 1 << 22)
        except (AttributeError, TypeError):  # 404: abrir() devolveu None
            return None
    else:
        zp = os.path.join(CACHE, f"{c}_{ano}.zip")
        if not os.path.exists(zp):
            r = abrir(url)
            if r is None:
                return None
            esperado = int(r.headers.get("Content-Length", 0))
            with open(zp + ".part", "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            if esperado and os.path.getsize(zp + ".part") != esperado:
                raise IOError(f"download incompleto: {url}")
            os.replace(zp + ".part", zp)
        fonte = zp
    with zipfile.ZipFile(fonte) as z:
        am = [n for n in z.namelist() if n.upper().endswith("_AM.CSV")]
        if len(am) != 1:
            raise IOError(f"{url}: esperava 1 CSV do AM, achei {am}")
        info = z.getinfo(am[0])
        with z.open(am[0]) as src, open(destino + ".part", "wb") as dst:
            shutil.copyfileobj(src, dst, 1 << 20)  # o zipfile confere o CRC-32 ao terminar a leitura
    if os.path.getsize(destino + ".part") != info.file_size:
        raise IOError(f"{am[0]}: tamanho difere do zip")
    os.replace(destino + ".part", destino)
    with open(os.path.join(CACHE, "_proveniencia.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"url": url, "membro": am[0], "bytes": info.file_size, "crc32": f"{info.CRC:08x}",
                            "coletado_em": time.strftime("%Y-%m-%d")}) + "\n")
    log("TSE", c, ano, am[0], info.file_size, "bytes")
    return destino


def ler(p):
    with open(p, encoding="latin-1", newline="") as f:
        yield from csv.DictReader(f, delimiter=";")


def main():
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(os.path.join(DADOS, "integridade"), exist_ok=True)
    cand, votos, total_cargo = [], defaultdict(int), defaultdict(int)
    for ano in ANOS:
        p = membro_am("consulta_cand", ano)
        if not p:
            log("sem consulta_cand", ano); continue
        cand += [dict(r, _ano=ano) for r in ler(p)]
        v = membro_am("votacao_candidato_munzona", ano, remoto=True)
        if v:
            for r in ler(v):
                q = r.get("QT_VOTOS_NOMINAIS_VALIDOS") or r.get("QT_VOTOS_NOMINAIS") or "0"
                q = int(q) if q.lstrip("-").isdigit() else 0
                votos[(ano, r["SQ_CANDIDATO"], r["NR_TURNO"])] += q
                total_cargo[(ano, r["CD_CARGO"], r["NR_TURNO"])] += q

    # ---- ligação parlamentar -> título (nome civil + nascimento; depois só nome civil, se único)
    por_nome_nasc, por_nome = defaultdict(set), defaultdict(set)
    for r in cand:
        t = (r.get("NR_TITULO_ELEITORAL_CANDIDATO") or "").strip()
        if not t.isdigit() or int(t) == 0:
            continue
        por_nome_nasc[(norm(r["NM_CANDIDATO"]), iso(r.get("DT_NASCIMENTO")))].add(t)
        por_nome[norm(r["NM_CANDIDATO"])].add(t)
    lig, alertas = {}, []
    for x in PARL:
        a = por_nome_nasc.get((norm(x["civil"]), x["nasc"]), set())
        b = por_nome.get(norm(x["civil"]), set())
        if len(a) == 1:
            lig[x["id"]] = (next(iter(a)), "nome+nascimento")
        elif not a and len(b) == 1:
            lig[x["id"]] = (next(iter(b)), "nome")
            alertas.append(f"{x['nome']}: ligado só pelo nome civil (nascimento da {SISTEMA} {x['nasc'] or 'vazio'} não bate com o TSE)")
        else:
            alertas.append(f"{x['nome']}: **sem ligação** ao TSE ({len(a)} por nome+nascimento, {len(b)} por nome: '{x['civil']}')")
    titulos = {t for t, _ in lig.values()}

    # ---- candidaturas de quem foi ligado (todas as eleições gerais no AM)
    linhas, pessoas = [], {}
    # vice-governador e suplente de senador não recebem voto próprio: o resultado é o do titular da chapa (mesmo número)
    titular = {"vice-governador": "governador", "suplente_senador": "senador"}
    chapa = {(r["_ano"], r["NR_TURNO"], r["NR_CANDIDATO"], cargo(r["DS_CARGO"])): r for r in cand}
    for r in cand:
        tc = titular.get(cargo(r["DS_CARGO"]))
        tr = chapa.get((r["_ano"], r["NR_TURNO"], r["NR_CANDIDATO"], tc)) if tc else None
        if tr and not limpo(r.get("DS_SIT_TOT_TURNO")):
            r["DS_SIT_TOT_TURNO"] = f"{limpo(tr.get('DS_SIT_TOT_TURNO'))} (chapa de {tr['NM_URNA_CANDIDATO']})"
    for r in sorted(cand, key=lambda r: (r["_ano"], r["NR_TURNO"])):
        t = (r.get("NR_TITULO_ELEITORAL_CANDIDATO") or "").strip()
        if t not in titulos:
            continue
        ano, sq, turno = r["_ano"], r["SQ_CANDIDATO"], r["NR_TURNO"]
        v = votos.get((ano, sq, turno))
        tot = total_cargo.get((ano, r["CD_CARGO"], turno))
        linhas.append(dict(
            pessoa_id=pid(t), ano=ano, cargo=cargo(r["DS_CARGO"]),
            uf=r["SG_UF"], cod_ibge="", tipo_eleicao="suplementar" if "SUPLEMENTAR" in (r.get("NM_TIPO_ELEICAO") or "").upper() else "ordinária",
            turno=turno, partido=r["SG_PARTIDO"], numero=r["NR_CANDIDATO"], nome_urna=r["NM_URNA_CANDIDATO"],
            coligacao=(r.get("NM_COLIGACAO") or r.get("NM_FEDERACAO") or "").replace("#NULO#", "").strip(),
            situacao_candidatura=limpo(r.get("DS_SITUACAO_CANDIDATURA")), resultado=limpo(r.get("DS_SIT_TOT_TURNO")),
            votos="" if v is None else v, pct=round(100 * v / tot, 2) if v is not None and tot else "",
            sq_candidato=sq, fonte=f"TSE consulta_cand_{ano} + votacao_candidato_munzona_{ano} (SQ_CANDIDATO {sq})"))
        p = pessoas.setdefault(pid(t), {})
        p.update(nome=r["NM_CANDIDATO"].title(), nome_urna_mais_recente=r["NM_URNA_CANDIDATO"], nascimento=iso(r.get("DT_NASCIMENTO")) or p.get("nascimento", ""),
                 genero=(r.get("DS_GENERO") or "").replace("#NULO#", "").title() or p.get("genero", ""),
                 uf_nascimento=(r.get("SG_UF_NASCIMENTO") or "").replace("#NULO#", "") or p.get("uf_nascimento", ""),
                 municipio_nascimento=(r.get("NM_MUNICIPIO_NASCIMENTO") or "").replace("#NULO#", "").title() or p.get("municipio_nascimento", ""))

    # ---- fotos oficiais da Casa (melhores que as do TSE), 240 px, em fotos/<pessoa_id>.jpg
    from PIL import Image
    pasta = os.path.join(BASE_DIR, "fotos"); os.makedirs(pasta, exist_ok=True)
    idents = []
    for x in PARL:
        if x["id"] not in lig:
            continue
        t, como = lig[x["id"]]
        p = pid(t)
        idents.append(dict(pessoa_id=p, sistema=SISTEMA, valor=x["id"], ano="", ligacao=como))
        destino = os.path.join(pasta, f"{p}.jpg")
        if x.get("foto") and not os.path.exists(destino):
            try:
                img = Image.open(io.BytesIO(abrir(x["foto"].replace("http://", "https://")).read())).convert("RGB")
                img.thumbnail((240, 10000)); img.save(destino, "JPEG", quality=80)
            except Exception as e:
                alertas.append(f"{x['nome']}: foto oficial ({SISTEMA}) não baixada ({e}); tentada a do TSE")
        fonte = x.get("foto") or ""
        # sem foto da Casa: a da candidatura mais recente no TSE (foto_cand<ano>_AM_div.zip, membro AM<sq>_div.jpg)
        for l in sorted((l for l in linhas if l["pessoa_id"] == p), key=lambda l: l["ano"], reverse=True):
            if os.path.exists(destino):
                break
            url = f"https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes{l['ano']}/fotos/foto_cand{l['ano']}_AM_div.zip"
            try:
                z = zipfile.ZipFile(HttpArquivo(url))
                m = next((n for n in z.namelist() if re.fullmatch(rf"F?AM{l['sq_candidato']}_div\.jpe?g", n, re.I)), None)
                if m:
                    img = Image.open(io.BytesIO(z.read(m))).convert("RGB")
                    img.thumbnail((240, 10000)); img.save(destino, "JPEG", quality=80)
                    fonte = f"{url}#{m}"
            except Exception as e:
                alertas.append(f"{x['nome']}: foto do TSE {l['ano']} não baixada ({e})")
        pessoas[p]["foto"] = f"fotos/{p}.jpg" if os.path.exists(destino) else ""
        pessoas[p]["foto_fonte"] = fonte
    for l in linhas:
        idents.append(dict(pessoa_id=l["pessoa_id"], sistema="tse_sq", valor=l["sq_candidato"], ano=l["ano"], ligacao="titulo"))
    idents = list({tuple(i.values()): i for i in idents}.values())

    def gravar(nome, rows):
        with open(os.path.join(DADOS, nome), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    gravar("pessoas.csv", [dict(pessoa_id=k, **v) for k, v in sorted(pessoas.items(), key=lambda i: i[1]["nome"])])
    gravar("identificadores.csv", idents)
    gravar("candidaturas.csv", linhas)

    # ---- integridade
    ok = [f"{len(PARL)} parlamentares; {len(lig)} ligados ao TSE "
          f"({sum(c == 'nome+nascimento' for _, c in lig.values())} por nome+nascimento, {sum(c == 'nome' for _, c in lig.values())} só por nome)",
          f"{len(linhas)} candidaturas em eleições gerais no AM ({ANOS[0]}–{ANOS[-1]}) de {len(pessoas)} pessoas",
          f"{sum(l['votos'] != '' for l in linhas)} candidaturas com votos somados de votacao_candidato_munzona"]
    falhas = []
    # cada parlamentar ligado deve ter candidatura ao próprio cargo (o suplente de senador pode ter sido só suplente)
    for x in PARL:
        if x["id"] in lig:
            p = pid(lig[x["id"]][0])
            cs = {l["cargo"] for l in linhas if l["pessoa_id"] == p}
            if CARGO not in cs and not (CARGO == "senador" and "suplente_senador" in cs):
                falhas.append(f"{x['nome']}: ligado, mas sem candidatura a {CARGO} no AM ({sorted(cs)})")
    if len({pid(t) for t, _ in lig.values()}) != len(lig):
        falhas.append("dois parlamentares caíram no mesmo pessoa_id")
    with open(os.path.join(DADOS, "integridade", "tse.md"), "w", encoding="utf-8") as f:
        f.write(f"# Integridade: ligação ao TSE ({time.strftime('%Y-%m-%d')})\n\n## Passou\n" + "".join(f"- {s}\n" for s in ok)
                + "\n## Falhou\n" + ("".join(f"- {s}\n" for s in falhas) or "- nada\n")
                + "\n## Alertas (verificação humana)\n" + ("".join(f"- {s}\n" for s in alertas) or "- nenhum\n"))
    log("\n".join(ok))
    log(f"{len(falhas)} falhas, {len(alertas)} alertas -> dados/integridade/tse.md")


if __name__ == "__main__":
    main()
