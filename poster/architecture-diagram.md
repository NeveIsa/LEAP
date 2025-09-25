# Software Architecture Diagram

```mermaid
graph TB
    subgraph "Client Layer"
        C1[Python Client]
        C2[Jupyter Notebook]
        C3[Web Browser]
        C4[CLI/curl]
    end
    
    subgraph "FastAPI Server"
        API[FastAPI Application]
        
        subgraph "Core Endpoints"
            EP1[/functions - List Activities]
            EP2[/call - Invoke Functions]
            EP3[/logs - Query Interactions]
            EP4[/experiments - Metadata]
            EP5[/health - Status Check]
        end
        
        subgraph "Auth & Security"
            AUTH[PBKDF2 Authentication]
            SESS[Session Middleware]
            CORS[CORS Middleware]
        end
    end
    
    subgraph "Experiment Container"
        EXP[Experiment Directory]
        
        subgraph "Experiment Components"
            FUNCS[funcs/ - Python Functions]
            UI[ui/ - Dashboard & Quizzes]
            QUIZ[quiz/ - Markdown Assessments]
            CREDS[admin_credentials.json]
        end
    end
    
    subgraph "Data Layer"
        DB[(DuckDB Database)]
        LOGS[Interaction Logs]
        META[Metadata Tables]
        STATS[Analytics Views]
    end
    
    subgraph "Visualization Layer"
        DASH[Interactive Dashboards]
        CHARTS[Real-time Charts]
        EXPORT[CSV Export]
    end
    
    %% Client connections
    C1 --> API
    C2 --> API
    C3 --> API
    C4 --> API
    
    %% API to endpoints
    API --> EP1
    API --> EP2
    API --> EP3
    API --> EP4
    API --> EP5
    
    %% Security flow
    API --> AUTH
    API --> SESS
    API --> CORS
    
    %% Experiment integration
    EP1 --> FUNCS
    EP2 --> FUNCS
    EP3 --> LOGS
    UI --> QUIZ
    
    %% Database operations
    EP2 --> DB
    EP3 --> DB
    DB --> LOGS
    DB --> META
    DB --> STATS
    
    %% Visualization
    LOGS --> DASH
    STATS --> CHARTS
    LOGS --> EXPORT
    
    %% Experiment isolation
    EXP --> FUNCS
    EXP --> UI
    EXP --> QUIZ
    EXP --> CREDS
    
    %% Styling
    classDef clientNode fill:#e1f5fe,stroke:#0277bd,stroke-width:2px
    classDef serverNode fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef dataNode fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef expNode fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
    
    class C1,C2,C3,C4 clientNode
    class API,EP1,EP2,EP3,EP4,EP5,AUTH,SESS,CORS serverNode
    class DB,LOGS,META,STATS dataNode
    class EXP,FUNCS,UI,QUIZ,CREDS expNode
```