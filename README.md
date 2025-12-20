# Frontend — Task Dashboard

Part of the [dsti-devops suite](https://github.com/sacumesh/dsti-devops). This repository provides the web frontend for the Task Dashboard.

![Task Dashboard Screenshot](./images/image1.png)

## Technology Stack
- Python
- Flask

## Features
- Web dashboard for managing tasks
- Integrates with a backend REST API
- Displays task title, status, and description

## Endpoints
| Method | Endpoint  | Description           |
| ------ | --------- | --------------------- |
| GET    | `/`       | Task dashboard UI     |
| GET    | `/health` | Frontend health check |

## CI/CD

### GitHub Actions
- Branches: `develop`, `main`
- Triggers:
    - On push or pull request:
        - Build Docker image (no tests)
    - Manual (`workflow_dispatch`):
        - Input: tag (e.g., `v1.2.0`)
        - Login using GitHub Secrets
        - Build and push to Docker Hub

### References
- Workflows: https://github.com/sacumesh/devops-task-dashboard/tree/main/.github/workflows
- Docker Hub: https://hub.docker.com/layers/sacumesh/devops-task-dashboard/1.0.0

## Docker
```bash
docker build --no-cache -t <your-namespace>/<your-repo>:<tag> .
```
