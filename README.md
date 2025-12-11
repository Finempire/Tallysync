# TallySync - Tally ERP Automation SaaS Platform

A comprehensive multi-tenant SaaS platform for automating Tally ERP operations for Indian businesses. Competes with Suvit (₹8,999/year) and Vouchrit, offering bank statement automation, GST compliance, invoice OCR, and payroll management.

## 🚀 Features

### Phase 1: Foundation & Core (Months 1-4)
- ✅ Multi-tenant architecture (PostgreSQL schema-based isolation)
- ✅ JWT authentication with role-based access control
- ✅ Bank statement parsing (PDF/Excel/CSV) for 15+ Indian banks
- ✅ AI-powered ledger suggestion engine
- ✅ Tally XML voucher generation (Payment, Receipt, Journal, Contra)
- ✅ Desktop connector for TallyPrime integration
- ✅ Transaction mapping UI with bulk operations

### Phase 2: GST Compliance (Months 4-7)
- ✅ E-invoicing integration with IRN/QR generation
- ✅ GSTR-1 preparation (B2B, B2CL, B2CS, CDNR, exports)
- ✅ GSTR-3B computation (tax liability calculation)
- ✅ GSTR-2B reconciliation engine
- ✅ E-way bill generation (₹50,000+ threshold)
- ✅ GSP API integration (ClearTax/Masters India)

### Phase 3: Invoice OCR (Months 5-8)
- ✅ Multi-provider OCR (Google Vision, AWS Textract, Tesseract)
- ✅ Intelligent field extraction (GSTIN, invoice number, amounts)
- ✅ Duplicate invoice detection
- ✅ Auto-voucher creation from approved invoices
- ✅ Bulk invoice upload
- ✅ Manual correction tracking for ML improvement

### Phase 4: Payroll (Months 7-10)
- ✅ Employee master with statutory IDs (PAN, Aadhaar, UAN, ESIC)
- ✅ Flexible salary structure templates
- ✅ Statutory calculations:
  - PF: 12% employee + 12% employer (8.33% EPS + 3.67% EPF)
  - ESI: 0.75% employee + 3.25% employer (≤₹21,000)
  - Professional Tax (state-wise slabs)
  - TDS (old/new regime support)
- ✅ Monthly payroll processing
- ✅ Payslip generation (PDF)
- ✅ Tally voucher export

### Phase 5: Advanced Features (Months 10-14)
- ✅ Dashboard analytics & reporting
- ✅ Cash flow forecasting
- ✅ Compliance reminders (GST, TDS, PF, ESI)
- ✅ Multi-channel notifications (Email, SMS, WhatsApp)
- ✅ Custom report generation

## 📁 Project Structure

```
tally-automation/
├── backend/                    # Django Backend
│   ├── apps/
│   │   ├── tenants/           # Multi-tenancy
│   │   ├── users/             # Authentication & users
│   │   ├── companies/         # Company & ledger masters
│   │   ├── bank_statements/   # Bank statement parsing
│   │   ├── vouchers/          # Voucher management
│   │   ├── tally_connector/   # Tally XML integration
│   │   ├── gst/              # GST compliance
│   │   ├── invoices/         # Invoice OCR
│   │   ├── payroll/          # Payroll processing
│   │   ├── reports/          # Analytics & reporting
│   │   └── notifications/    # Alerts & reminders
│   ├── config/               # Django settings
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                  # React Frontend
│   ├── src/
│   │   ├── api/              # API client
│   │   ├── components/       # Reusable components
│   │   ├── pages/            # Page components
│   │   ├── hooks/            # Custom hooks
│   │   └── types/            # TypeScript types
│   ├── package.json
│   └── Dockerfile
├── desktop-connector/         # Windows Desktop App
│   ├── connector.py          # Main connector script
│   ├── requirements.txt
│   └── config.example.ini
├── nginx/                     # Nginx config
├── docker-compose.yml
├── .env.example
└── README.md
```

## 🛠️ Tech Stack

### Backend
- **Framework**: Django 5.0 + Django REST Framework
- **Database**: PostgreSQL 15 with django-tenants
- **Task Queue**: Celery + Redis
- **Authentication**: JWT (SimpleJWT)

### Frontend
- **Framework**: React 18 + TypeScript
- **UI Library**: Ant Design 5
- **State Management**: Zustand + React Query
- **Build Tool**: Vite

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Reverse Proxy**: Nginx
- **OCR**: Google Cloud Vision / AWS Textract
- **Payments**: Razorpay

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)

### Using Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/your-org/tallysync.git
cd tallysync

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Start all services
docker-compose up -d

# Run migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# Admin: http://localhost:8000/admin
```

### Local Development

#### Backend
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set up database
createdb tallysync
python manage.py migrate

# Run development server
python manage.py runserver
```

#### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

## 🔧 Desktop Connector Setup

The Desktop Connector bridges your local TallyPrime with the cloud platform.

### Requirements
- Windows 10+
- TallyPrime with ODBC Server enabled

### Installation
1. Download connector from Settings > Tally Connection
2. Run `TallySyncConnector.exe`
3. Configure API key from dashboard
4. Enable ODBC in TallyPrime (F12 > Advanced Configuration)

### Manual Setup
```bash
cd desktop-connector
pip install -r requirements.txt
cp config.example.ini config.ini
# Edit config.ini with your API key
python connector.py
```

## 💰 Pricing Plans

| Plan | Price | Features |
|------|-------|----------|
| Starter | ₹4,999/year | 1 company, 500 txns/month, Bank parsing, Tally sync |
| Professional | ₹8,999/year | 3 companies, Unlimited txns, GST compliance, E-invoicing |
| Business | ₹14,999/year | 10 companies, Payroll module, Priority support |
| Enterprise | Custom | Unlimited companies, API access, On-premise option |

## 📚 API Documentation

### Authentication
```bash
# Login
POST /api/v1/auth/login/
{
  "email": "user@example.com",
  "password": "password"
}

# Response
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

### Bank Statements
```bash
# Upload statement
POST /api/v1/bank-statements/upload/
Content-Type: multipart/form-data
- bank_account: 1
- file: statement.pdf

# Generate vouchers
POST /api/v1/bank-statements/generate-vouchers/
{
  "transaction_ids": [1, 2, 3],
  "company_id": 1
}
```

### Vouchers
```bash
# List vouchers
GET /api/v1/vouchers/

# Push to Tally
POST /api/v1/vouchers/{id}/push-tally/
```

### GST
```bash
# Generate e-invoice
POST /api/v1/gst/einvoices/{id}/generate/

# Get GSTR-1 summary
GET /api/v1/gst/{company_id}/gstr1-summary/?period=122024
```

### Payroll
```bash
# Process payroll
POST /api/v1/payroll/{company_id}/process/
{
  "month": 12,
  "year": 2024
}
```

## 🔐 Security

- Multi-tenant data isolation (PostgreSQL schemas)
- JWT authentication with refresh tokens
- Encrypted credential storage
- Role-based access control
- GSTIN/PAN validation
- Audit trails for all transactions

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## 📦 Deployment

### Production Deployment

```bash
# Build and deploy
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# SSL with Let's Encrypt
docker-compose exec nginx certbot --nginx -d app.tallysync.com
```

### Environment Variables
See `.env.example` for all required environment variables.

## 🤝 Support

- **Documentation**: https://docs.tallysync.com
- **Email**: support@tallysync.com
- **WhatsApp**: +91-XXXXXXXXXX

## 📄 License

Proprietary - All rights reserved

---

Built with ❤️ for Indian businesses
