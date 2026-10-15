# Verificação de integridade

Executada em 15/10/2026 17:50 por `scripts/verificar.py`.

| Teste | Resultado | Detalhe |
|---|---|---|
| 1. Downloads completos | ✅ | 20 arquivos com bytes = Content-Length |
| 2. Autorias: API antiga × API nova | ⚠️ | Jefferson Peres: antiga 125 × nova 126 (só na antiga 0, só na nova 1); Vanessa Grazziotin: antiga 1981 × nova 1995 (só na antiga 0, só na nova 14); Alfredo Nascimento: antiga 127 × nova 129 (só na antiga 0, só na nova 2); Eduardo Braga: antiga 1134 × nova 1140 (só na antiga 0, só na nova 6); Plínio Valério: antiga 882 × nova 888 (só na antiga 0, só na nova 6); Omar Aziz: antiga 544 × nova 546 (só na antiga 0, só na nova 2). A API nova inclui matérias em que o senador é coautor sem constar da lista antiga e vice-versa; os dossiês usam a lista antiga, que diz quem é o 1º autor. |
| 3. Leis conferidas na base do Planalto | ✅ | 19 leis; todas existem com a mesma data |
| 4. Votos: endpoint novo × antigo | ✅ | 10012 votos em comum, todos iguais |
| 5. CEAPS: casamento de nomes | ✅ | todos os senadores em exercício desde 2009 têm despesas |
| 5b. CEAPS: planilha × API administrativa do Senado | ✅ | 9 senador-ano conferidos, todos iguais |
| 6a. Emendas: autores aplicam no AM (sem homônimo) | ✅ | 7 autores, todos com ≥50% no AM ou nacional |
| 6b. Emendas: autores casados por nome (conferir) | ⚠️ | ALFREDO NASCIMENTO (cód. 2637) → Alfredo Nascimento; EDUARDO BRAGA (cód. 2909) → Eduardo Braga; VANESSA GRAZZIOTIN (cód. 2910) → Vanessa Grazziotin; ALFREDO NASCIMENTO (cód. 3807) → Alfredo Nascimento; OMAR AZIZ (cód. 3794) → Omar Aziz; SANDRA BRAGA (cód. 3802) → Sandra Braga; PLINIO VALERIO (cód. 4137) → Plínio Valério |
