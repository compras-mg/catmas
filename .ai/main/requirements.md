# Requirements

## Problem
Brazilian government procurement teams need to browse and search the CATMAS catalog (201,785 items) without requiring a backend server.

## User needs
- Filter catalog items by tipo (Material/Serviço), grupo, classe, código, and nome
- Filter by situação (Ativo / Suspenso para compra), agricultura familiar (Sim/Não), sustentável (Sim/Não)
- Cascading filters: tipo → grupo → classe
- Paginated results (manageable page sizes)
- Deployable as a static site (GitHub Pages)

## Constraints
- Full database is 1.1 GB with 75 columns — must serve only the 5 needed columns
- No backend — all querying happens client-side
- Must keep download size reasonable for browser loading
