# Senadores do Amazonas (1999 em diante)

Dossiê dos senadores que exerceram mandato pelo Amazonas desde 1999 (titulares e suplentes em exercício): mandatos, matérias apresentadas, normas geradas, presença nas votações nominais, discursos, cota parlamentar (CEAPS) e emendas ao orçamento. Só dados oficiais (Senado Federal e CGU), com verificação de integridade em [VERIFICACAO.md](VERIFICACAO.md).

Atualizado em 16/10/2026. O mandato de senador dura 8 anos (duas legislaturas).


## Legislaturas

- [51ª (1999–2003)](legislaturas/51-1999-2003.md) — 3 senadores em exercício
- [52ª (2003–2007)](legislaturas/52-2003-2007.md) — 5 senadores em exercício
- [53ª (2007–2011)](legislaturas/53-2007-2011.md) — 5 senadores em exercício
- [54ª (2011–2015)](legislaturas/54-2011-2015.md) — 5 senadores em exercício
- [55ª (2015–2019)](legislaturas/55-2015-2019.md) — 4 senadores em exercício
- [56ª (2019–2023)](legislaturas/56-2019-2023.md) — 3 senadores em exercício
- [57ª (2023–2027)](legislaturas/57-2023-2027.md) — 3 senadores em exercício


## Senadores

| Senador | Exercício (desde 1999) | Matérias | Normas 1º autor | Presença em votações | CEAPS | Emendas |
|---|---|---|---|---|---|---|
| [Alfredo Nascimento](senadores/alfredo-nascimento.md) | 01/02/2007 a 29/03/2007; 01/04/2010 a 31/12/2010; 08/07/2011 a 31/01/2015 | 127 | 1 | 99,3% | R$ 828.199,47 | R$ 0,00 |
| [Arthur Virgílio](senadores/arthur-virgilio.md) | 01/02/2003 a 31/01/2011 | 2825 | 4 | 91,2% | R$ 286.820,14 | R$ 0,00 |
| [Bernardo Cabral](senadores/bernardo-cabral.md) | 01/02/1999 a 31/01/2003 | 25 | 2 | 87,2% | R$ 0,00 | R$ 0,00 |
| [Eduardo Braga](senadores/eduardo-braga.md) | 01/02/2011 a 01/01/2015; 22/04/2016 a 31/01/2019; 01/02/2019 a 16/10/2026 | 1134 | 16 | 86,3% | R$ 5.876.052,53 | R$ 368.458.605,30 |
| [Gilberto Mestrinho](senadores/gilberto-mestrinho.md) | 01/02/1999 a 17/11/2004; 31/03/2005 a 31/01/2007 | 9 | 0 | 95,9% | R$ 0,00 | R$ 0,00 |
| [Gilberto Miranda](senadores/gilberto-miranda.md) | 23/11/2004 a 30/03/2005 | 7 | 1 | 40,9% | R$ 0,00 | R$ 0,00 |
| [Jefferson Peres](senadores/jefferson-peres.md) | 01/02/1999 a 31/01/2003; 01/02/2003 a 23/05/2008 | 89 | 1 | 90,7% | R$ 0,00 | R$ 0,00 |
| [Jefferson Praia](senadores/jefferson-praia.md) | 03/06/2008 a 31/01/2011 | 94 | 0 | 85,9% | R$ 160.721,34 | R$ 0,00 |
| [João Pedro](senadores/joao-pedro.md) | 03/04/2007 a 31/03/2010; 06/01/2011 a 07/07/2011 | 94 | 0 | 93,1% | R$ 353.269,37 | R$ 0,00 |
| [João Thomé Mestrinho](senadores/joao-thome-mestrinho.md) | 18/11/2004 a 22/11/2004 | 1 | 0 | s/d | R$ 0,00 | R$ 0,00 |
| [Omar Aziz](senadores/omar-aziz.md) | 01/02/2015 a 31/01/2023; 01/02/2023 a 16/10/2026 | 544 | 2 | 92,1% | R$ 5.536.134,55 | R$ 366.639.831,30 |
| [Plínio Valério](senadores/plinio-valerio.md) | 01/02/2019 a 16/10/2026 | 882 | 4 | 98,9% | R$ 3.128.062,66 | R$ 309.233.585,07 |
| [Sandra Braga](senadores/sandra-braga.md) | 01/01/2015 a 22/04/2016 | 79 | 1 | s/d | R$ 478.785,09 | R$ 8.768.259,00 |
| [Vanessa Grazziotin](senadores/vanessa-grazziotin.md) | 01/02/2011 a 31/01/2019 | 1980 | 9 | 91,4% | R$ 3.838.774,55 | R$ 38.228.707,87 |


## Como atualizar

```
python -I scripts/coletar.py
python -I scripts/tse.py      # pessoa_id, candidaturas e fotos (modelo comum da plataforma)
python -I scripts/gerar.py
python -I scripts/verificar.py
```
