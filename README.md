# 360Ghar Real Estate Platform Backend

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Framework](https://img.shields.io/badge/framework-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/database-PostgreSQL%20+%20PostGIS-blue.svg)](https://www.postgresql.org/)

A high-performance, modern backend for a Tinder-like real estate platform. Built with FastAPI and PostgreSQL, this API powers features like swipe-based property discovery, advanced geospatial search, agent-managed property visits, and short-stay bookings.

## Table of Contents

- [About The Project](#about-the-project)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [Getting Started](#getting-started)
- [Running with Docker](#running-with-docker)
- [Environment Configuration](#environment-configuration)
- [API Documentation](#api-documentation)
- [Key Implementation Details](#key-implementation-details)
- [Contributing](#contributing)
- [License](#license)

## About The Project

360Ghar revolutionizes property discovery through an engaging, swipe-based interface similar to dating apps, combined with powerful map-based search and professional agent assistance. The platform supports both traditional property search and short-stay bookings, making it a comprehensive real estate solution.

## Key Features

### Core Functionality
- **Tinder-like Property Swiping**: Intuitive swipe interface to like or pass on properties
- **Advanced Property Search**: Unified endpoint supporting geospatial, full-text, and filtered search
- **Property Visit Scheduling**: Agent-managed visit coordination with automatic assignment
- **Short-stay Bookings**: Complete booking system with availability checks and pricing
- **Agent Management**: Comprehensive agent system with load balancing and performance tracking
- **User Personalization**: Preference learning from user interactions and search history

### Technical Highlights
- **Modern & Fast**: Built with **FastAPI** for high performance and automatic API documentation
- **Fully Async**: Asynchronous architecture from API to database operations
- **Geospatial Powered**: **PostgreSQL + PostGIS** for efficient location-based queries
- **Secure Authentication**: **Supabase Auth** integration with phone-based primary authentication
- **Performance Optimized**: Designed for **PgBouncer** compatibility and scalable connection pooling
- **Production Ready**: **Sentry** integration, comprehensive logging, and error handling
- **Containerized**: Full **Docker** support with **Docker Compose** for development

## Tech Stack

| Category              | Technology                                                    |
| --------------------- | ------------------------------------------------------------- |
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/)                     |
| **Database**          | [PostgreSQL](https://www.postgresql.org/) + [PostGIS](https://postgis.net/) |
| **ORM**               | [SQLAlchemy 2.0+ (Async)](https://www.sqlalchemy.org/)      |
| **Data Validation**   | [Pydantic](https://docs.pydantic.dev/)                       |
| **Authentication**    | [Supabase Auth](https://supabase.com/docs/guides/auth)       |
| **Caching**           | [Redis](https://redis.io/) (optional)                        |
| **Migrations**        | [Supabase Migrations](https://supabase.com/docs/guides/cli) |
| **Observability**     | [Sentry](https://sentry.io/)                                 |
| **Containerization**  | [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/) |
| **Geospatial**        | [GeoAlchemy2](https://geoalchemy-2.readthedocs.io/)          |

## Project Structure

```
app/
├── api/                 # API endpoints and routing
│   └── api_v1/
│       └── endpoints/   # Individual endpoint modules
├── core/                # Core components (config, db, auth, logging)
├── middleware/          # Custom middleware (rate limiting, security)
├── models/              # SQLAlchemy ORM models and enums  
├── schemas/             # Pydantic schemas for data validation
├── services/            # Business logic and database operations
└── utils/               # Utility functions

supabase/
└── migrations/          # Database schema migrations

populate_data/           # Data population scripts
tests/                   # Test files
```

## API Endpoints

All endpoints are prefixed with `/api/v1`.

### 🔑 Authentication (`/auth`)
- `POST /login/`: Phone + password login via Supabase Auth
- `POST /register/`: User registration with phone as primary identifier

### 👤 Users (`/users`)  
- `GET /profile/`: Get current user profile
- `PUT /profile/`: Update user profile information
- `PUT /preferences/`: Update property search preferences
- `PUT /location/`: Update user's current location

### 🏠 Properties (`/properties`)
- `GET /`: **Unified Property Search** with geospatial, text search, and advanced filtering
- `GET /recommendations/`: Get personalized property recommendations  
- `GET /{property_id}/`: Get detailed property information
- `POST /`: Create new property (authenticated users)
- `PUT /{property_id}/`: Update property (property owners)
- `DELETE /{property_id}/`: Delete property (property owners)

### ↔️ Swipes (`/swipes`)
- `POST /`: Record property swipe (like/pass)
- `GET /`: Get swipe history with full search and filtering capabilities
- `DELETE /undo/`: Undo last swipe action
- `PUT /{swipe_id}/toggle/`: Toggle like status of previously swiped property
- `GET /stats/`: Get user swipe statistics

### 📅 Visits (`/visits`)
- `POST /`: Schedule property visit
- `GET /`: List user's visits (all/upcoming/past)  
- `GET /{visit_id}/`: Get visit details
- `POST /reschedule/`: Reschedule existing visit
- `POST /cancel/`: Cancel scheduled visit

### 🏨 Bookings (`/bookings`)
- `POST /`: Create short-stay booking
- `GET /`: List user's bookings  
- `GET /{booking_id}/`: Get booking details
- `POST /check-availability/`: Check property availability
- `POST /calculate-pricing/`: Get booking price breakdown
- `POST /cancel/`: Cancel booking

### 🧑‍💼 Agents (`/agents`)
- `GET /assigned/`: Get user's assigned agent
- `POST /assign/`: Assign agent to user (auto-assigns if no agent specified)
- `GET /available/`: List available agents
- `GET /{agent_id}/`: Get agent details
- `GET /{agent_id}/stats/`: Get agent performance statistics

## Getting Started

### Prerequisites

- [Python 3.10+](https://www.python.org/)
- [Docker](https://www.docker.com/get-started) and [Docker Compose](https://docs.docker.com/compose/install/)
- A [Supabase](https://supabase.com/) project for authentication

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/360ghar-backend.git
   cd 360ghar-backend
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit the `.env` file with your database, Supabase, and other credentials.

5. **Start database services:**
   ```bash
   docker-compose up -d db redis
   ```

6. **Apply database migrations:**
   ```bash
   supabase db push
   ```

7. **Load sample data (optional):**
   ```bash
   # Quick load (~51 properties)
   PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/load_comprehensive_data.py --quick
   
   # Full load (~300 properties)  
   PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/load_comprehensive_data.py
   ```

8. **Start the application:**

   **Option 1: Using Python (Recommended for simple development)**
   ```bash
   python run.py
   ```

   **Option 2: Using FastAPI CLI (Recommended for development with hot reload)**
   ```bash
   fastapi dev app/main.py --port 8000 --host 0.0.0.0
   ```

   **Option 3: Production-like environment**
   ```bash
   fastapi run app/main.py --port 8000 --host 0.0.0.0
   ```

The API will be available at `http://localhost:8000`.

> **💡 Development Tip**: FastAPI CLI provides better hot reload performance and additional development features. It's the recommended way for active development.

## Running with Docker

To run the entire stack in containers:

```bash
# Build and start all services
docker-compose up --build

# Or run in detached mode
docker-compose up -d --build
```

## Environment Configuration

Create a `.env` file based on `.env.example`:

```env
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/ghar360

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_SECRET_KEY=your_service_role_key
SUPABASE_STORAGE_BUCKET=property-images

# JWT Configuration
SECRET_KEY=your_jwt_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Optional Services
REDIS_URL=redis://localhost:6379
SENTRY_DSN=your_sentry_dsn_here

# Environment
ENVIRONMENT=development
```

## API Documentation

Once running, access the interactive API documentation:

- **Swagger UI**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **ReDoc**: [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc)
- **OpenAPI YAML**: [http://localhost:8000/api/v1/openapi.yaml](http://localhost:8000/api/v1/openapi.yaml)

Additional endpoints:
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **Config Info**: [http://localhost:8000/config](http://localhost:8000/config)

## Key Implementation Details

### Authentication System
- **Phone-First Authentication**: Uses phone numbers as primary identifiers with Supabase Auth
- **JWT Token Validation**: Local token verification for optimal performance
- **Flexible Verification**: Supports both email and phone verification
- **User Sync**: Automatic synchronization between Supabase and local database

### Database Architecture
- **Async SQLAlchemy 2.0+**: Modern async database operations
- **PostGIS Integration**: Efficient geospatial queries with proper indexing
- **PgBouncer Ready**: Configured for production connection pooling
- **Full-Text Search**: PostgreSQL native text search capabilities
- **Comprehensive Indexing**: Optimized indexes for common query patterns

### Property Search System
- **Unified Search Endpoint**: Single endpoint supporting multiple search types
- **Geospatial Optimization**: PostGIS `ST_DWithin` for radius-based searches
- **Full-Text Search**: PostgreSQL TSVECTOR for relevant text matching
- **Advanced Filtering**: Support for 25+ property filters
- **Pagination**: Efficient cursor-based pagination for large datasets

### Agent Management
- **Auto-Assignment**: Round-robin agent assignment based on workload
- **Load Balancing**: Distributes users across available agents
- **Performance Tracking**: Comprehensive agent statistics and metrics
- **Availability Management**: Real-time agent availability tracking

### Performance Optimizations
- **Async Throughout**: Non-blocking operations from API to database
- **Efficient Queries**: Optimized database queries with proper joins and indexes
- **Caching Ready**: Redis integration for caching expensive operations
- **Error Handling**: Comprehensive error handling with Sentry integration

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

**360Ghar Development Team** - [dev@360ghar.com](mailto:dev@360ghar.com)

Project Link: [https://github.com/your-username/360ghar-backend](https://github.com/your-username/360ghar-backend)