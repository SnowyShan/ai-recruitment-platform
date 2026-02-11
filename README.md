# TalentBridge AI - AI-Powered Recruitment Platform

<p align="center">
  <img src="frontend/public/favicon.svg" alt="TalentBridge AI Logo" width="80" height="80">
</p>

<p align="center">
  <strong>Intelligent hiring, simplified.</strong>
</p>

<p align="center">
  AI-powered recruitment platform that helps you find the perfect candidates faster and smarter.
</p>

---

## 🚀 Features

- **📋 Job Management** - Create, publish, and manage job postings
- **👥 Candidate Pool** - Build and manage your talent database
- **📝 Smart Applications** - AI-powered candidate matching and scoring
- **🤖 AI Screenings** - Automated interview screening with scoring
- **📊 Analytics Dashboard** - Real-time hiring pipeline insights
- **🎯 Match Scoring** - Intelligent candidate-job matching (0-100%)

## 🛠 Tech Stack

### Backend
- **FastAPI** - Modern, fast Python web framework
- **SQLAlchemy** - SQL toolkit and ORM
- **PostgreSQL/SQLite** - Database
- **JWT** - Secure authentication
- **Pydantic** - Data validation

### Frontend
- **React 18** - UI library
- **Vite** - Next-gen frontend tooling
- **Tailwind CSS** - Utility-first CSS
- **React Router** - Client-side routing
- **Recharts** - Data visualization
- **Lucide React** - Beautiful icons

---

## 📦 Quick Start

### Prerequisites

- **Python 3.9+** installed
- **Node.js 18+** installed
- **npm** or **yarn** package manager

### 1. Clone & Setup

```bash
# Extract the zip file and navigate to the project
cd talentbridge-ai
```

### 2. Backend Setup

```bash
# Navigate to backend folder
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run the backend server
uvicorn app.main:app --reload --port 8000
```

The backend API will be running at: http://localhost:8000

- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 3. Frontend Setup

Open a **new terminal** and:

```bash
# Navigate to frontend folder
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be running at: http://localhost:5173

### 4. Access the Application

1. Open http://localhost:5173 in your browser
2. Click **"Create account"** to register
3. Start using the platform!

---

## 📁 Project Structure

```
talentbridge-ai/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application entry
│   │   ├── database.py          # Database configuration
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── auth.py              # Authentication utilities
│   │   └── routers/
│   │       ├── auth.py          # Authentication endpoints
│   │       ├── jobs.py          # Jobs CRUD
│   │       ├── candidates.py    # Candidates CRUD
│   │       ├── applications.py  # Applications CRUD
│   │       ├── screening.py     # AI Screening endpoints
│   │       └── dashboard.py     # Dashboard stats
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── auth/
│   │   │   │   └── ProtectedRoute.jsx
│   │   │   └── common/
│   │   │       ├── Layout.jsx
│   │   │       └── Sidebar.jsx
│   │   ├── context/
│   │   │   └── AuthContext.jsx
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   ├── Register.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Jobs.jsx
│   │   │   ├── Candidates.jsx
│   │   │   ├── Applications.jsx
│   │   │   └── Screenings.jsx
│   │   ├── services/
│   │   │   └── api.js
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
│
└── README.md
```

---

## 🔑 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | User login |
| GET | `/api/auth/me` | Get current user |

### Jobs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/jobs` | List all jobs |
| POST | `/api/jobs` | Create job |
| GET | `/api/jobs/{id}` | Get job details |
| PUT | `/api/jobs/{id}` | Update job |
| DELETE | `/api/jobs/{id}` | Delete job |
| POST | `/api/jobs/{id}/publish` | Publish job |
| POST | `/api/jobs/{id}/close` | Close job |

### Candidates
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/candidates` | List candidates |
| POST | `/api/candidates` | Add candidate |
| GET | `/api/candidates/{id}` | Get candidate |
| PUT | `/api/candidates/{id}` | Update candidate |
| DELETE | `/api/candidates/{id}` | Delete candidate |

### Applications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/applications` | List applications |
| POST | `/api/applications` | Create application |
| POST | `/api/applications/{id}/shortlist` | Shortlist |
| POST | `/api/applications/{id}/reject` | Reject |

### Screenings
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/screenings` | List screenings |
| POST | `/api/screenings` | Schedule screening |
| POST | `/api/screenings/{id}/start` | Start screening |
| POST | `/api/screenings/{id}/complete` | Complete screening |

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/stats` | Get stats |
| GET | `/api/dashboard/pipeline-overview` | Pipeline data |
| GET | `/api/dashboard/recent-applications` | Recent apps |
| GET | `/api/dashboard/top-jobs` | Top jobs |

---

## 🎨 Screenshots

### Dashboard
Modern analytics dashboard with pipeline visualization and quick actions.

### Jobs Management
Create and manage job postings with status tracking.

### Applications
Review applications with AI-powered match scoring.

### AI Screening
Automated screening interviews with comprehensive scoring.

---

## ⚙️ Configuration

### Backend Environment Variables

Create a `.env` file in the `backend` folder:

```env
# Database (SQLite for development)
DATABASE_URL=sqlite:///./talentbridge.db

# For PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost:5432/talentbridge

# JWT Configuration
SECRET_KEY=your-super-secret-key-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Frontend Environment Variables

Create a `.env` file in the `frontend` folder (optional):

```env
VITE_API_URL=http://localhost:8000
```

---

## 🧪 Testing the API

### Using the Interactive Docs

1. Go to http://localhost:8000/docs
2. Click "Authorize" and enter your JWT token
3. Test any endpoint directly from the browser

### Using cURL

```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123","full_name":"Test User"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

---

## 🚀 Deployment

### Backend (Production)

```bash
# Install production server
pip install gunicorn

# Run with gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Frontend (Production)

```bash
# Build for production
npm run build

# The build output will be in the `dist` folder
# Deploy to any static hosting (Vercel, Netlify, etc.)
```

---

## 📝 License

MIT License - feel free to use this project for learning and development.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📧 Support

If you have any questions or need help, please open an issue.

---

<p align="center">
  Made with ❤️ by TalentBridge AI Team
</p>
