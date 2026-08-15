# OmniSight – Multimodal UI Self‑Healing RPA Agent

OmniSight is an end‑to‑end visual‑language‑model (VLM) powered platform that automatically **detects**, **diagnoses**, and **remediates** UI bugs in web applications. By combining computer‑vision, large language models, and programmable agents, OmniSight can capture screenshots, analyse layout anomalies, suggest CSS/HTML fixes, and apply them — all without human intervention.

---

## ✨ Key Features
- **Visual Bug Detection** – Playwright captures UI snapshots; VLM agents analyse visual defects.
- **AI‑Driven Remediation** – LangGraph orchestrates agents that generate and apply code patches.
- **Continuous Integration** – Hooks into CI/CD pipelines to trigger inspections on every deployment.
- **Azure‑Backed Persistence** – Stores artefacts, logs, and remediation history in Azure Blob Storage and PostgreSQL.
- **Dockerised & Scalable** – Fully containerised services for easy deployment.

---

## 🏗️ Architecture Overview
```mermaid
flowchart TD
    subgraph CI[CI/CD Pipeline]
        A[Push to Git]
    end
    subgraph Orchestrator[vlm_orchestrator (LangGraph)]
        B[Trigger API]
        C[Launch VLM Agents]
    end
    subgraph Capture[Playwright UI Capture]
        D[Grab Screenshots]
    end
    subgraph Analyse[Gemini / Gemini‑Flash]
        E[Visual Analysis]
    end
    subgraph DB[Remediation DB]
        F[Azure PostgreSQL]
    end
    A -->|Deploy| CI
    CI --> B
    B --> C
    C --> D
    D --> E
    E --> F
```

---

## 🚀 Getting Started
### 1️⃣ Project Setup
```bash
# Clone the repository (replace <url> and <branch> as needed)
git clone <url> -b <branch>
cd OmniSight
```
### 2️⃣ Python Environment
- **Check Python version**
  - Windows: `python --version`
  - Linux/macOS: `python3 --version`
- **Create a virtual environment**
```bash
python -m venv venv   # use `python3` on Linux/macOS if needed
```
- **Activate**
  - Linux/macOS: `source venv/bin/activate`
  - Windows: `venv\Scripts\activate.bat`
### 3️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```
### 4️⃣ Configure Secrets
Copy the example env file and fill in your credentials:
```bash
cp .env.example .env
```
The `.env` must contain Azure storage keys, PostgreSQL URI, VLM API keys, etc.
### 5️⃣ Database Preparation
```bash
# Ensure PostgreSQL is running and create the database
psql -U <user> -c "CREATE DATABASE omnisight;"
# Run migrations (if any)
alembic upgrade head
```
---

## ▶️ Running the Individual Services
| Service | Command |
|--------|---------|
| **Mock Store** (static UI for testing) | `cd trailhead-mock-store && python3 -m http.server 8080` |
| **Navigator** (UI navigation script) | `python3 navigator/navigator.py` |
| **Gateway API** (FastAPI entry‑point) | `fastapi dev getway_api.py` |
| **Orchestrator** (LangGraph VLM driver) | `python -m vlm.vlm_orchestrator` |
---

## 🧪 Playwright Automation
```bash
pip install playwright
playwright install            # installs Chromium, Firefox, WebKit browsers
sudo playwright install-deps # Linux dependencies (Ubuntu/Debian) – run with sudo
```
Use the scripts under `playwright/` to capture UI snapshots that feed into the VLM analysis pipeline.
---

## 📦 Deployment (Docker)
A `docker-compose.yml` is provided for full‑stack deployment.
```bash
# Bring up the stack (builds if necessary)
docker-compose up --build -d
```
The compose file starts:
- **gateway_api** (FastAPI)
- **orchestrator** (Python worker)
- **postgres** (Azure‑compatible PostgreSQL image)
- **playwright** (headless browser service)
Make sure the `.env` file is mounted into the containers.
---

## 🔄 CI/CD Integration
Add the following step to your pipeline after a successful build:
```yaml
- name: Trigger OmniSight Inspection
  run: |
    curl -X POST $OMNISIGHT_TRIGGER_URL \
      -H "Authorization: Bearer $OMNISIGHT_API_KEY" \
      -d '{"commit": "${GITHUB_SHA}"}'
```
The orchestrator will pull the latest container image, run visual inspections on the deployed UI, and push any remediation patches back to the repo.
---

## 📚 Documentation
- Detailed design docs, API reference, and deployment guides are available in the [Google Docs knowledge base](https://docs.google.com/document/d/1NYgRKwxUN5qFKeXg-jaxBCuV2fzkV7xSJ_pJ0asw2ws/edit?usp=sharing).
---

## 🤝 Contributing
Please read `CONTRIBUTING.md` for coding standards, testing guidelines, and pull‑request workflow.
---

## 📄 License
This project is licensed under the **MIT License** – see the `LICENSE` file for details.
---


Open an issue or reach out to the maintainers at `omnisight@your-org.com`.


OmniSight is an end‑to‑end visual‑language‑model (VLM) powered platform that automatically **detects**, **diagnoses**, and **remediates** UI bugs in web applications. By combining computer‑vision, large language models, and programmable agents, OmniSight can capture screenshots, analyse layout anomalies, suggest CSS/HTML fixes, and apply them — all without human intervention.

---

## ✨ Key Features
- **Visual Bug Detection** – Playwright captures UI snapshots; VLM agents analyse visual defects.
- **AI‑Driven Remediation** – LangGraph orchestrates agents that generate and apply code patches.
- **Continuous Integration** – Hooks into CI/CD pipelines to trigger inspections on every deployment.
- **Azure‑Backed Persistence** – Stores artefacts, logs, and remediation history in Azure Blob Storage and PostgreSQL.
- **Dockerised & Scalable** – Fully containerised services for easy deployment.

---

## 🏗️ Architecture Overview
```mermaid
flowchart TD
    subgraph CI[CI/CD Pipeline]
        A[Push to Git]
    end
    subgraph Orchestrator[vlm_orchestrator (LangGraph)]
        B[Trigger API]
        C[Launch VLM Agents]
    end
    subgraph Capture[Playwright UI Capture]
        D[Grab Screenshots]
    end
    subgraph Analyse[Gemini / Gemini‑Flash]
        E[Visual Analysis]
    end
    subgraph DB[Remediation DB]
        F[Azure PostgreSQL]
    end
    A -->|Deploy| CI --> B --> C --> D --> E --> F
```

---

## 🚀 Getting Started
### 1️⃣ Project Setup
```bash
# Clone the repository (replace <url> and <branch> as needed)
git clone <url> -b <branch>
cd OmniSight
```
### 2️⃣ Python Environment
- **Check Python version**
  - Windows: `python --version`
  - Linux/macOS: `python3 --version`
- **Create a virtual environment**
```bash
python -m venv venv   # use `python3` on Linux/macOS if needed
```
- **Activate**
  - Linux/macOS: `source venv/bin/activate`
  - Windows: `venv\Scripts\activate.bat`
### 3️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```
### 4️⃣ Configure Secrets
Create a `.env` file in the project root and populate it with the required credentials (Azure storage keys, PostgreSQL URI, VLM API keys, etc.). You can copy the template:
```bash
cp .env.example .env
```
### 5️⃣ Database Preparation
```bash
# Ensure PostgreSQL is running and create the database
psql -U <user> -c "CREATE DATABASE omnisight;"
# Run migrations (if any)
alembic upgrade head   # or the appropriate migration command
```
---

## ▶️ Running the Individual Services
| Service | Command |
|--------|---------|
| **Mock Store** (static UI for testing) | `cd trailhead-mock-store && python3 -m http.server 8080` |
| **Navigator** (UI navigation script) | `python3 navigator/navigator.py` |
| **Gateway API** (FastAPI entry‑point) | `fastapi dev getway_api.py` |
| **Orchestrator** (LangGraph VLM driver) | `python -m vlm.vlm_orchestrator` |
---

## 🧪 Playwright Automation
```bash
pip install playwright
playwright install            # installs Chromium, Firefox, WebKit browsers
sudo playwright install-deps # Linux dependencies (Ubuntu/Debian) – run with sudo
```
Use the `playwright` scripts under `playwright/` to capture UI snapshots that feed into the VLM analysis pipeline.
---

## 📦 Deployment (Docker)
A `docker-compose.yml` is provided for full‑stack deployment.
```bash
docker compose up --build -d
```
The compose file spins up:
- **gateway_api** (FastAPI)
- **orchestrator** (Python worker)
- **postgres** (Azure‑compatible PostgreSQL image)
- **playwright** (headless browser service)
Ensure the `.env` file is mounted into the containers.
---

## 🔄 CI/CD Integration
Add the following step to your pipeline after a successful build:
```yaml
- name: Trigger OmniSight Inspection
  run: |
    curl -X POST $OMNISIGHT_TRIGGER_URL \
      -H "Authorization: Bearer $OMNISIGHT_API_KEY" \
      -d '{"commit": "${GITHUB_SHA}"}'
```
The orchestrator will pull the latest container image, run visual inspections on the deployed UI, and push any remediation patches back to the repo.
---

## 📚 Documentation
- Detailed design docs, API reference, and deployment guides live in the [Google Docs knowledge base](https://docs.google.com/document/d/1NYgRKwxUN5qFKeXg-jaxBCuV2fzkV7xSJ_pJ0asw2ws/edit?usp=sharing).
---

## 🤝 Contributing
Please read `CONTRIBUTING.md` for coding standards, testing guidelines, and pull‑request workflow.
---

## 📄 License
This project is licensed under the **MIT License** – see the `LICENSE` file for details.
---

## 📞 Contact
Open an issue or reach out to the maintainers at `omnisight@your-org.com`.
---


OmniSight is an end‑to‑end visual‑language‑model (VLM) powered platform that automatically **detects**, **diagnoses**, and **remediates** UI bugs in web applications. By combining computer‑vision, large language models, and programmable agents, OmniSight can capture screenshots, analyse layout anomalies, suggest CSS/HTML fixes, and apply them — all without human intervention.

---

## ✨ Key Features
- **Visual Bug Detection** – Playwright captures UI snapshots; VLM agents analyse visual defects.
- **AI‑Driven Remediation** – LangGraph orchestrates agents that generate and apply code patches.
- **Continuous Integration** – Hooks into CI/CD pipelines to trigger inspections on every deployment.
- **Azure‑Backed Persistence** – Stores artefacts, logs, and remediation history in Azure Blob Storage and PostgreSQL.
- **Dockerised & Scalable** – Fully containerised services for easy deployment.

---

## 🏗️ Architecture Overview
```
┌─────────────────────┐
│   CI/CD Pipeline    │
└───────┬─────────────┘
        │
        ▼
┌─────────────────────┐   Deploy → Trigger API →
│   vlm_orchestrator  │──────────────────────►
│   (LangGraph)       │   Invoke VLM agents
└───────┬─────────────┘
        │
        ▼
┌─────────────────────┐   Capture UI via Playwright
│   Visual Capture    │──────────────────────►
└───────┬─────────────┘   Analyse with Gemini / Gemini‑Flash
        │
        ▼
┌─────────────────────┐   Generate patch & store
│   Remediation DB    │   (Azure PostgreSQL)
└─────────────────────┘
```

---

## 🚀 Getting Started
1. **Clone the repo**
   ```bash
   git clone https://github.com/your-org/OmniSight.git
   cd OmniSight
   ```
2. **Install dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Configure environment** – Copy `.env.example` to `.env` and fill in Azure credentials, API keys, etc.
4. **Run the orchestrator**
   ```bash
   python -m vlm.vlm_orchestrator
   ```

---

## 📚 Documentation
Full design docs, API reference, and deployment guides are available in the [Google Docs knowledge base](https://docs.google.com/document/d/1NYgRKwxUN5qFKeXg-jaxBCuV2fzkV7xSJ_pJ0asw2ws/edit?usp=sharing).

---

## 🤝 Contributing
Contributions are welcome! Please read the `CONTRIBUTING.md` for guidelines on coding standards, testing, and pull‑request workflow.

---

## 📄 License
This project is licensed under the **MIT License** – see the `LICENSE` file for details.
