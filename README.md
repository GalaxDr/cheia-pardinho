# Cheia do Pardinho

Simulador da dinâmica da água na sub-bacia Alto-Médio Pardinho (Programa MUDA / UNISC), com dados ao vivo da Rede Hidrometeorológica da Defesa Civil RS.

## Rodar no computador

    node server.js

e abrir http://localhost:3000 (precisa de Node 18 ou mais novo).

## Publicar no Easypanel

1. Suba esta pasta para um repositório no GitHub.
2. No Easypanel: Create → App → Source: GitHub (escolha o repositório e a branch).
3. Build: Dockerfile (o arquivo já está na raiz).
4. Domains: porta 3000; ative HTTPS.
5. Deploy.

O servidor repassa só as duas consultas do guia da Defesa Civil (Tags_data e Historic) e guarda a resposta por 1 minuto (dados atuais) ou 5 minutos (séries), para respeitar o limite de 120 consultas por minuto.

## Estrutura

- `server.js`, `Dockerfile`, `package.json`: servidor Node sem dependências (serve `public/` e faz o repasse para a API da Defesa Civil RS).
- `public/`: o site pronto (index.html, dados em PNG, meta.json, ícones).
- `fonte/index.html`: fonte da página antes do empacotamento.
- `scripts/`: pipeline em Python que gera os dados a partir do MDE (ordem: hand → web → fluxo → solos_pontos → geo) e os empacotadores (`easypanel.py` gera `public/`, `bundle.py` gera um HTML único).

## Nível ao vivo

Por padrão o mapa mostra a cheia a partir do nível medido nas estações de Sinimbu e Santa Cruz do Sul: subida = nível atual − menor nível dos últimos 30 dias, interpolada ao longo do rio entre as duas estações pelo tempo de percurso até a foz. Mexer no controle de nível passa para o modo manual.
