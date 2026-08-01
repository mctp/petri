# Petri Setup (Simplified)

```
          ┌─────────────────────────────────────────────┐
          │              USER                           │
          │  Browser :2718     Terminal (pi)            │
          └──────┬──────────────┬───────────────────────┘
                 │              │
                 │ HTTP         │ bash execute-code.sh
                 │      ┌───────▼───────┐
                 │      │     pi        │  ◄── LLM: Laguna-S-2.1
                 │      │ (coding       │      (local-llama)
                 │      │  agent)       │
                 │      └───┬───────┬───┘
                 │          │       │
                 │  Skills  │       │
                 │  ┌───────┴──┐    │
                 │  │marimo-   │    │
                 │  │pair      │    │
                 │  │(cm API)  │    │
                 │  └─────┬────┘    │
                 │        │         │
                 │  ┌─────▼────┐    │
                 │  │ analyst  │    │
                 │  │(analysis │    │
                 │  │  rules)  │    │
                 │  └─────┬────┘    │
                 │        │         │
                 └────────┼─────────┘
                          │ Kernel RPC
                ┌─────────▼─────────┐
                │  marimo Kernel    │  ◄── source of truth
                │  (reactive DAG)   │
                └─────────┬─────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
     ┌───▼───┐        ┌───▼───┐      ┌─────▼─────┐
     │Python │        │   R   │      │  Files    │
     │  (uv) │        │(renv) │      │           │
     │       │        │       │      │data/      │
     │numpy, │        │ggplot2│      │outputs/   │
     │polars,│        │limma  │      │           │
     │scipy  │        │       │      │           │
     └───────┘        └───────┘      └───────────┘
```

```mermaid
graph LR
    User["User<br/>Browser :2718"]
    Terminal["Terminal<br/>pi agent"]
    Pi["pi + Laguna LLM"]
    MP["marimo-pair skill"]
    Analyst["analyst skill"]
    Kernel["marimo Kernel<br/>(source of truth)"]
    Python["Python (uv)"]
    R["R (renv)"]
    Files["data/ & outputs/"]

    User <-->|"HTTP"| Kernel
    Terminal <-->|"execute-code.sh"| Pi
    Pi --> MP
    Pi --> Analyst
    MP <-->|"cm API"| Kernel
    Analyst <-->|"plans"| Kernel
    Kernel --> Python
    Kernel --> R
    Kernel --> Files

    classDef node fill:#fff,stroke:#333,stroke-width:1px
    classDef user fill:#e3f2fd
    classDef pi fill:#f3e5f5
    classDef marimo fill:#e8f5e4

    class User,Terminal user
    class Pi,MP,Analyst pi
    class Kernel,Python,R,Files marimo
```

### Flow

1. **User** views the notebook in the browser at `localhost:2718` and runs **pi** in the terminal
2. **pi** (powered by **Laguna** LLM) loads two skills: **marimo-pair** (for kernel control) and **analyst** (for analysis methodology)
3. **marimo-pair** bridges pi to the **marimo kernel** via bash scripts and the `cm` API
4. The **kernel** is the source of truth — it runs all Python/R code and writes results to `data/` and `outputs/`
