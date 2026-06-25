# Simulador de Memória Virtual

Aluno: João Vítor Dallarosa

## Objetivo

Implementar um simulador de memória virtual que replica o funcionamento de uma MMU (Memory Management Unit), com tradução de endereços virtuais para físicos, detecção de falta de página e substituição de páginas via algoritmo LRU.

## Especificações do sistema

| Parâmetro | Valor |
|---|---|
| Memória principal | 64 KB |
| Memória virtual | 1 MB |
| Tamanho da página / frame | 8 KB |
| Número de frames | 8 |
| Número de páginas | 128 |
| Algoritmo de substituição | LRU (Least Recently Used) |
| Processos leves | 2 threads rodando em paralelo |

## Como funciona

Dois processos leves são criados com tamanhos aleatórios e passam a gerar acessos a endereços virtuais. Para cada acesso, a MMU:

1. Calcula a página e o offset a partir do endereço virtual
2. Consulta a tabela de páginas do processo
3. Se a página estiver na memória — **HIT** — calcula o endereço físico e retorna o conteúdo
4. Se não estiver — **FALTA DE PÁGINA** — verifica se há frame livre:
   - Se sim, carrega a página no frame livre
   - Se não, o algoritmo LRU escolhe a página menos recentemente usada para substituir

Ao final, o simulador exibe o estado da memória principal e a tabela de páginas de cada processo.

## Estrutura do código

| Classe | Responsabilidade |
|---|---|
| `PageTableEntry` | Entrada da tabela de páginas: presente, frame mapeado, timestamp LRU |
| `Frame` | Frame da memória principal: livre/ocupado, processo dono, conteúdo |
| `MainMemory` | Gerencia os 8 frames: buscar livre, carregar, despejar |
| `LightProcess` | Processo leve com espaço virtual e tabela de páginas próprios |
| `MMU` | Tradução de endereços, detecção de falta de página, algoritmo LRU |
| `VirtualMemorySimulator` | Orquestra os processos e threads |

## Como executar

Requisitos: Python 3.8 ou superior. Não há dependências externas.

```bash
python simulador_memoria.py
```
