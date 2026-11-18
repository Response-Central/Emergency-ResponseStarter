
# ResponseCentral — Emergency Response Management System

ResponseCentral is a centralized emergency response management system designed to improve the coordination of emergency calls, incidents, response units, and hospitals.

The project demonstrates how database management, full-stack development, containerization, and CI/CD can support emergency response operations.

**Project:** CSCI-4560 Database & System Management  
**Repository:** https://github.com/Response-Central/Emergency-ResponseStarter

## Project Overview

Emergency response operations require fast access to accurate information. Traditional systems may rely on disconnected databases, manual communication, and delayed updates.

ResponseCentral aims to centralize emergency information and provide a unified platform for managing emergency incidents and available response resources.

### Project Objectives

- Centralize emergency calls and incident information.
- Track emergency response units and their availability.
- Support dispatch coordination.
- Manage hospital information.
- Improve access to emergency response data.
- Demonstrate secure database and application development.
- Implement automated testing and container deployment.

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Frontend | React 19, Vite 8 | Web application |
| Backend | Python, Flask | REST API and business logic |
| Application Server | Gunicorn | Python application hosting |
| Database | PostgreSQL 17 | Relational data storage |
| Web Server | Nginx | Frontend hosting and API proxy |
| Containerization | Docker | Application packaging |
| Local Orchestration | Docker Compose | Multi-container development |
| Orchestration | Kubernetes | Container management |
| CI/CD | GitHub Actions | Automated testing and publishing |
| Container Registry | GitHub Container Registry | Docker image storage |
| Planned Cloud Hosting | AWS ECS Fargate | Managed container hosting |
| Planned Cloud Database | Amazon RDS | Managed PostgreSQL |
| Planned Monitoring | Amazon CloudWatch | Logs and monitoring |

## System Architecture

The application follows a three-tier architecture:

```text
                  USER
                    |
                    v
             React Frontend
                    |
                    v
              Nginx Proxy
                    |
                    v
              Flask REST API
                    |
                    v
             PostgreSQL DB
```

### Application Components

**Frontend**
- Provides the user interface.
- Communicates with the backend through API requests.
- Uses React and Vite.

**Backend**
- Processes application requests.
- Implements business logic.
- Handles database operations.
- Exposes REST API endpoints.

**Database**
- Stores emergency calls, incidents, response units, hospitals, and related records.
- Uses PostgreSQL for relational data management.

## Database Design

The project models emergency response information through related database entities.

Core concepts include:

- Emergency calls
- Incidents
- Response units
- Incident assignments
- Hospitals
- Hospital reservations
- Locations
- Administrator accounts and sessions

[![Architecture diagram of response-central/emergency-responsestarter](https://gitdiagram.com/response-central/emergency-responsestarter/diagram.png)](https://gitdiagram.com/response-central/emergency-responsestarter?utm_source=readme&utm_medium=picture)

The current PostgreSQL implementation contains the following tables:

```text
adminsession
adminuser
emergencycall
geocodecache
hospital
hospitalreservation
incident
incidentassignment
location
responseunit
```

The database schema is initialized through the project's Python management script.

## Getting Started

### Prerequisites

Install the following software:

- Git
- Docker Desktop
- Node.js and npm (for frontend development)
- Python 3 (for backend development)
- PostgreSQL (if running the database outside Docker)

### 1. Clone the Repository

```bash
git clone https://github.com/Response-Central/Emergency-ResponseStarter.git
cd Emergency-ResponseStarter
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Update the `.env` file with the appropriate local database credentials and application settings.

**Security:** Never commit `.env`, passwords, API keys, or access tokens to GitHub.

## Running with Docker Compose

Docker Compose runs the frontend, backend, and PostgreSQL database together.

### 1. Build and Start Containers

```bash
docker compose up -d --build
```

### 2. Initialize the Database

```bash
docker compose exec backend python manage.py init-db
```

### 3. Optional: Seed Response Units

```bash
docker compose exec backend python manage.py seed-units
```

### 4. Create an Administrator

```bash
docker compose exec backend python manage.py create-admin
```

### 5. Access the Application

| Service | URL |
|---|---|
| Frontend | http://localhost:8080 |
| Backend API health check | http://localhost:8080/api/health |

### 6. Stop Containers

```bash
docker compose down
```

To inspect running containers:

```bash
docker compose ps
```

To view logs:

```bash
docker compose logs -f
```

## Kubernetes Deployment

ResponseCentral also supports deployment to a local Kubernetes cluster using Docker Desktop.

### Kubernetes Configuration Files

```text
k8s/
├── namespace.yaml
├── postgres.yaml
├── backend.yaml
└── frontend.yaml
```

| File | Description |
|---|---|
| namespace.yaml | Creates the ResponseCentral namespace |
| postgres.yaml | PostgreSQL StatefulSet, storage, and service |
| backend.yaml | Flask backend Deployment and service |
| frontend.yaml | React frontend Deployment and service |

### 1. Enable Kubernetes

Enable Kubernetes in Docker Desktop.

Verify that the cluster is available:

```bash
kubectl get nodes
```

### 2. Create the Namespace

```bash
kubectl apply -f k8s/namespace.yaml
```

### 3. Configure Kubernetes Secrets

The deployment requires secrets for PostgreSQL credentials and access to the private GitHub Container Registry images.

Required secret names:

```text
postgres-credentials
ghcr-credentials
```

Create these secrets securely before applying the workload manifests.

Do not store real passwords or registry tokens in the repository.

### 4. Deploy Application Services

```bash
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
```

### 5. Verify Deployment

```bash
kubectl get pods -n responsecentral
kubectl get services -n responsecentral
```

Check the rollout:

```bash
kubectl rollout status deployment/backend -n responsecentral
kubectl rollout status deployment/frontend -n responsecentral
```

For a new database, initialize the schema using the backend management script before using database-dependent application features.

### 6. Access the Application

```bash
kubectl -n responsecentral port-forward service/frontend 8081:80
```

Open:

http://localhost:8081

Verify the API:

```bash
curl http://localhost:8081/api/health
```

Expected response:

```json
{
  "message": "Python API is running"
}
```

### Kubernetes Deployment Status

The local Kubernetes deployment has been verified with:

- PostgreSQL running successfully.
- Flask backend running successfully.
- React frontend running successfully.
- Backend health endpoint returning HTTP 200.
- Database schema initialized successfully.

## Docker Container Images

GitHub Actions builds and publishes two Docker images.

**Frontend:**

```text
ghcr.io/response-central/responsecentral-frontend:latest
```

**Backend:**

```text
ghcr.io/response-central/responsecentral-backend:latest
```

Both images support:

```text
linux/amd64
linux/arm64
```

The images are published to GitHub Container Registry and may require authentication to pull.

## CI/CD Pipeline

ResponseCentral uses GitHub Actions for continuous integration and container publishing.

### Continuous Integration

Workflow:

```text
.github/workflows/ci.yml
```

The CI pipeline performs:

1. Frontend dependency installation.
2. React production build.
3. npm security audit.
4. Backend integration testing with PostgreSQL.
5. Python dependency security audit.
6. Docker image build verification.

### Container Publishing

Workflow:

```text
.github/workflows/publish.yml
```

The publishing pipeline:

1. Authenticates with GitHub Container Registry.
2. Builds Docker images using Docker Buildx.
3. Produces AMD64 and ARM64 images.
4. Publishes frontend and backend images.
5. Tags images with `latest` and the Git commit SHA.

### CI/CD Architecture

```text
Developer
    |
    v
GitHub Repository
    |
    v
GitHub Actions
    |
    +------------------------+
    |                        |
    v                        v
Frontend Checks         Backend Checks
    |                        |
    +-----------+------------+
                |
                v
          Docker Build
                |
                v
      GitHub Container Registry
                |
                v
       Kubernetes Deployment
          (local cluster)
```

Kubernetes deployment is currently performed separately from the image-publishing workflow.

## AWS Cloud Deployment (In Progress)

The planned AWS deployment will use managed cloud services to host ResponseCentral.

### Proposed AWS Architecture

```text
                 Internet
                    |
                    v
        Application Load Balancer
                    |
          +---------+---------+
          |                   |
          v                   v
    Frontend Service     Backend Service
     ECS Fargate          ECS Fargate
                              |
                              v
                      Amazon RDS
                       PostgreSQL
```

### Planned AWS Services

| AWS Service | Purpose |
|---|---|
| Amazon ECR | Container image registry |
| Amazon ECS | Container orchestration |
| AWS Fargate | Serverless container compute |
| Amazon RDS | Managed PostgreSQL database |
| Application Load Balancer | HTTP/HTTPS traffic routing |
| AWS Secrets Manager | Secure application secrets |
| Amazon CloudWatch | Logging and monitoring |
| AWS IAM | Identity and access management |
| GitHub Actions OIDC | Secure CI/CD authentication |

### Deployment Status

**AWS deployment is currently in progress.**

The application has already been tested locally using Docker Compose and Kubernetes.

AWS infrastructure will be provisioned and verified separately.

## Security

ResponseCentral incorporates application and infrastructure security considerations.

### Application Security

- Administrator authentication and session management.
- Password hashing.
- Parameterized database queries.
- Input validation.
- Protected administrative endpoints.
- Environment-based configuration.

### Infrastructure Security

- Secrets excluded from source control.
- Kubernetes Secrets for sensitive configuration.
- Container vulnerability checks.
- Dependency security audits.
- IAM-based AWS access control.
- Planned HTTPS and encrypted cloud storage.
- Planned monitoring and restricted network access.

### Data Privacy

ResponseCentral is an academic demonstration project.

The system should use synthetic or non-sensitive demonstration data. It is not intended for live emergency dispatch or the storage of real patient information without additional security, operational, and regulatory safeguards.

**HIPAA compliance has not been established.**

## Testing and Verification

The project uses several verification methods:

| Component | Verification |
|---|---|
| React frontend | `npm run build` |
| JavaScript dependencies | `npm audit --audit-level=high` |
| Python dependencies | `pip-audit` |
| Backend | Automated Python tests |
| Database | PostgreSQL schema verification |
| Docker | Container build and startup |
| Kubernetes | Pod and rollout status |
| API | `/api/health` endpoint |
| CI/CD | GitHub Actions workflow results |

## Project Structure

```text
Emergency-ResponseStarter/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── publish.yml
├── database/
├── k8s/
│   ├── namespace.yaml
│   ├── postgres.yaml
│   ├── backend.yaml
│   └── frontend.yaml
├── src/
├── app.py
├── manage.py
├── database.py
├── dispatch.py
├── geocoding.py
├── hospitals.py
├── compose.yaml
├── Dockerfile.backend
├── Dockerfile.frontend
├── nginx.conf
├── package.json
├── package-lock.json
├── requirements.txt
├── vite.config.js
├── .env.example
└── README.md
```

## Future Improvements

Potential future enhancements include:

- AWS production-style deployment.
- Automated deployment through GitHub Actions.
- Improved response-unit availability tracking.
- Real-time incident updates.
- Database query and caching optimization.
- Additional monitoring and audit logging.
- Hospital capacity integration.
- Enhanced role-based access control.
- Automated database backup and recovery.

## Disclaimer

ResponseCentral is developed for educational and demonstration purposes.

It is not an official emergency dispatch system and should not be relied upon for real-world emergency response.

## Repository

**GitHub:** https://github.com/Response-Central/Emergency-ResponseStarter
