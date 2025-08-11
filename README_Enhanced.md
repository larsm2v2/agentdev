# Enhanced Email Librarian System

Enterprise-grade email organization system with AI agents, vector search, workflow automation, and comprehensive observability.

## 🏗️ Architecture Overview

The Enhanced Email Librarian is a sophisticated email processing system built with modern enterprise technologies:

### Core Components

- **FastAPI Backend Server** - High-performance async API server
- **CrewAI Agents** - Specialized AI agents for email processing tasks
- **Qdrant Vector Database** - Semantic search and email embeddings
- **PostgreSQL** - Relational data storage and job management
- **n8n Workflow Automation** - Visual workflow automation platform
- **LangFuse** - LLM observability and tracing
- **LangChain** - LLM framework integration

### System Capabilities

#### 🔄 **Shelving Agent** - Real-time Organization

- Processes incoming emails as they arrive
- AI-powered categorization and labeling
- Automatic archival and organization
- Real-time performance monitoring

#### 📚 **Cataloging Agent** - Historical Processing

- Batch processing of email archives
- Comprehensive email library creation
- Historical email analysis and categorization
- Large-scale processing optimization

#### 🏷️ **Reclassification Agent** - Label Optimization

- Intelligent email reclassification
- Label system optimization
- Category accuracy improvement
- Systematic email reorganization

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- OpenAI API key
- Gmail API credentials

### Installation

1. **Clone and Setup**

```bash
git clone <repository>
cd agentdev
python scripts/setup_enhanced_system.py
```

2. **Configure Environment**

```bash
cp .env.example .env
# Edit .env with your actual API keys and configurations
```

3. **Start Infrastructure Services**

```bash
docker-compose up -d
```

4. **Run Database Migrations**

```bash
alembic upgrade head
```

5. **Start the Email Librarian Server**

```bash
python -m src.core.enhanced_email_librarian_server
```

## 📊 Service Endpoints

| Service             | URL                             | Credentials    |
| ------------------- | ------------------------------- | -------------- |
| Email Librarian API | http://localhost:8000           | -              |
| API Documentation   | http://localhost:8000/docs      | -              |
| n8n Workflows       | http://localhost:5678           | admin/admin123 |
| Grafana Dashboard   | http://localhost:3000           | admin/admin123 |
| Prometheus Metrics  | http://localhost:9090           | -              |
| Qdrant Dashboard    | http://localhost:6333/dashboard | -              |

## 🔧 Configuration

### Environment Variables

Key configuration variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/email_librarian

# Vector Database
QDRANT_HOST=localhost
QDRANT_PORT=6333

# AI/LLM Services
OPENAI_API_KEY=sk-your_key_here
LANGFUSE_PUBLIC_KEY=pk-lf-your_key_here
LANGFUSE_SECRET_KEY=sk-lf-your_key_here

# Workflow Automation
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your_n8n_api_key

# Gmail API
GMAIL_CREDENTIALS_PATH=config/credentials.json
```

## 🤖 API Usage

### Create Email Processing Job

```python
import httpx

# Create a shelving job
job_data = {
    "job_type": "shelving",
    "parameters": {
        "batch_size": 10,
        "auto_archive": True
    },
    "enable_vector_storage": True,
    "enable_langfuse_tracking": True
}

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/jobs/create",
        json=job_data
    )
    job_id = response.json()["job_id"]
    print(f"Created job: {job_id}")
```

### Vector Search

```python
# Search similar emails
search_data = {
    "query": "meeting schedule next week",
    "limit": 10,
    "category_filter": "work"
}

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/search/vector",
        json=search_data
    )
    results = response.json()["results"]
```

### Execute AI Agent Task

```python
# Execute CrewAI agent task
agent_task = {
    "agent_type": "cataloging_agent",
    "task_description": "Process and catalog historical emails from last month",
    "config": {
        "start_date": "2024-06-01",
        "end_date": "2024-06-30",
        "batch_size": 100
    }
}

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/agents/execute",
        json=agent_task
    )
    execution_id = response.json()["execution_id"]
```

## 🔍 Vector Search & Embeddings

The system uses OpenAI's `text-embedding-3-large` model to create high-dimensional embeddings of email content. These embeddings enable:

- **Semantic Search** - Find emails by meaning, not just keywords
- **Similar Email Detection** - Identify related emails automatically
- **Category Clustering** - Group emails by content similarity
- **Duplicate Detection** - Find near-duplicate emails

### Vector Search Features

- **Hybrid Filtering** - Combine vector similarity with metadata filters
- **Real-time Updates** - Embeddings updated as emails are processed
- **Scalable Architecture** - Qdrant provides high-performance vector operations
- **Multi-modal Search** - Search by subject, content, sender, or labels

## 🔄 n8n Workflow Integration

Pre-built workflows for common email processing scenarios:

### Available Workflows

1. **Email Processing Main** - Individual email processing with AI categorization
2. **Email Cataloging Batch** - Bulk historical email processing
3. **Email Reclassification** - Label-based email reorganization
4. **Email Analytics** - Processing statistics and insights
5. **Notification Workflows** - Alert systems for important events

### Custom Workflow Creation

Access n8n at `http://localhost:5678` to create custom workflows:

- Visual workflow designer
- 200+ pre-built integrations
- Custom JavaScript functions
- Webhook triggers and HTTP requests
- Database operations and transformations

## 📈 Monitoring & Observability

### LangFuse Integration

- **LLM Call Tracing** - Complete visibility into AI agent execution
- **Performance Monitoring** - Token usage, latency, and cost tracking
- **Error Analysis** - Detailed error reporting and debugging
- **Usage Analytics** - Comprehensive usage statistics

### Prometheus Metrics

Key metrics exposed at `/metrics`:

- `email_processing_total` - Total emails processed
- `email_processing_duration_seconds` - Processing time distribution
- `agent_execution_total` - AI agent execution counts
- `vector_search_duration_seconds` - Search performance metrics
- `database_operations_total` - Database operation counts

### Grafana Dashboards

Pre-configured dashboards for:

- Email processing performance
- AI agent execution metrics
- Vector search analytics
- System resource utilization
- Error rates and debugging

## 🗃️ Database Schema

### Core Tables

- **email_processing_jobs** - Job queue and execution tracking
- **email_vectors** - Email embeddings and metadata
- **agent_executions** - AI agent task execution history

### Data Relationships

```mermaid
graph TD
    A[email_processing_jobs] --> B[agent_executions]
    B --> C[email_vectors]
    C --> D[Qdrant Collections]
    A --> E[n8n Workflows]
    B --> F[LangFuse Traces]
```

## 🔒 Security & Compliance

### Authentication & Authorization

- API key authentication for external integrations
- JWT tokens for user sessions
- Role-based access control (RBAC)
- OAuth 2.0 for Gmail API access

### Data Privacy

- Email content encryption at rest
- Secure vector embeddings storage
- GDPR compliance features
- Data retention policies

### Audit Trail

- Complete processing history
- LangFuse observability traces
- Database change logging
- API access logging

## 📦 Deployment Options

### Docker Compose (Development)

```bash
docker-compose up -d
```

### Kubernetes (Production)

```bash
kubectl apply -f k8s/
```

### Cloud Deployment

- **AWS ECS/EKS** with RDS and ElastiCache
- **Google Cloud Run** with Cloud SQL and Memorystore
- **Azure Container Instances** with Cosmos DB

## 🔧 Development

### Project Structure

```
agentdev/
├── src/
│   ├── core/                 # Core server and agents
│   ├── gmail/               # Gmail integration
│   └── integrations/        # External service integrations
├── config/                  # Configuration files
├── migrations/              # Database migrations
├── scripts/                 # Setup and utility scripts
├── monitoring/              # Monitoring configuration
├── n8n/                    # n8n workflow templates
└── docs/                   # Documentation
```

### Adding New Agents

1. Create agent class in `src/core/email_agents.py`
2. Define agent tools and capabilities
3. Add task creation methods
4. Register agent in EmailLibrarianAgents
5. Create corresponding API endpoints

### Custom Integrations

1. Create integration module in `src/integrations/`
2. Implement async interface methods
3. Add configuration options to `.env`
4. Register integration in main server
5. Add monitoring and error handling

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [docs/](docs/)
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: support@email-librarian.com

## 📋 Roadmap

### Current Version (v2.0)

- ✅ Enhanced AI agents with CrewAI
- ✅ Vector search with Qdrant
- ✅ n8n workflow automation
- ✅ LangFuse observability
- ✅ Comprehensive monitoring

### Upcoming Features (v2.1)

- 🔄 Multi-tenant support
- 🔄 Advanced email analytics
- 🔄 Mobile app integration
- 🔄 Calendar and task integration
- 🔄 Advanced security features

### Future Plans (v3.0)

- 🗺️ Multi-language support
- 🗺️ Advanced AI models (GPT-4, Claude)
- 🗺️ Enterprise SSO integration
- 🗺️ Advanced workflow templates
- 🗺️ API marketplace integrations
