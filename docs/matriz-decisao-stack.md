# Matriz de decisão de stack

## Objetivo

Comparar alternativas de stack para evolução do protótipo VozDoCliente, considerando implantação, custo, controle técnico, reprodutibilidade, segurança e manutenção.

Os pesos dos critérios foram definidos antes da atribuição das notas, conforme orientação da disciplina.

## Critérios e pesos

| Critério | Peso |
| --- | ---: |
| Facilidade de implantação | 20% |
| Custo operacional | 15% |
| Controle técnico e flexibilidade | 20% |
| Reprodutibilidade e versionamento | 15% |
| Segurança e gestão de credenciais | 15% |
| Manutenção e evolução | 15% |

## Alternativas avaliadas

1. n8n + LM Studio
2. n8n + OpenAI API
3. Make.com + OpenAI API

## Matriz

| Critério | Peso | n8n + LM Studio | n8n + OpenAI API | Make.com + OpenAI API |
| --- | ---: | ---: | ---: | ---: |
| Facilidade de implantação | 20% | 4 | 4 | 5 |
| Custo operacional | 15% | 5 | 3 | 3 |
| Controle técnico e flexibilidade | 20% | 5 | 5 | 3 |
| Reprodutibilidade e versionamento | 15% | 5 | 5 | 3 |
| Segurança e gestão de credenciais | 15% | 4 | 5 | 4 |
| Manutenção e evolução | 15% | 4 | 5 | 4 |

## Resultado ponderado

| Alternativa | Nota final |
| --- | ---: |
| n8n + OpenAI API | 4,55 |
| n8n + LM Studio | 4,50 |
| Make.com + OpenAI API | 3,65 |

## Justificativa das notas

### n8n + LM Studio
Apresenta baixo custo de uso do modelo e alto controle técnico. É adequado para desenvolvimento, testes e validação local. Como limitação, depende da disponibilidade da máquina que hospeda o modelo e não é a opção mais adequada para um serviço público de produção.

### n8n + OpenAI API
Mantém o controle, versionamento e flexibilidade do n8n, ao mesmo tempo em que remove a dependência de infraestrutura local para inferência. Possui custo variável por uso, mas oferece melhor adequação a um ambiente publicado e independente da máquina do desenvolvedor.

### Make.com + OpenAI API
Possui alta facilidade inicial de implantação por ser uma plataforma SaaS gerenciada. Em contrapartida, oferece menor controle sobre infraestrutura, versionamento e automação de deploy quando comparado ao n8n.

## Decisão

A alternativa escolhida para produção é **n8n + API de LLM externa**, por apresentar o melhor equilíbrio entre controle técnico, reprodutibilidade, segurança e manutenção.

Para desenvolvimento local, será mantida a alternativa **n8n + LM Studio**, permitindo testes sem consumo de API externa e preservando uma interface compatível com o fluxo de produção.