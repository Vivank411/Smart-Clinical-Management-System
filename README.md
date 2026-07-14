# 🏥 Smart Clinical Management System

A comprehensive **Full-Stack Healthcare Management Platform** developed to digitize hospital and clinic workflows. The application enables seamless patient registration, queue management, doctor consultation, clinical image management, electronic prescriptions, and administration through secure role-based access.

---

## 📖 Overview

The Smart Clinical Management System is designed to replace traditional paper-based clinical workflows with a centralized digital platform.

The system allows receptionists, doctors, junior doctors, and administrators to collaborate efficiently while maintaining secure patient records and improving healthcare delivery.

---

# ✨ Features

## 🔐 Authentication

- Secure Login
- JWT Authentication
- Role-Based Access Control (RBAC)
- Protected Routes
- Session Management

---

# 👩‍💼 Receptionist Module

### Dashboard

- Total Registered Patients
- Checked-In Patients
- Patients in Consultation
- Completed Visits
- Doctors On Duty
- Today's Queue
- Doctor Availability

### Patient Registration

- Register New Patient
- Personal Information
- Contact Details
- Insurance Information
- Emergency Contact
- Duplicate Patient Validation
- Auto Generated Patient ID

### Patient Search

- Search by
  - Patient ID
  - Name
  - Mobile Number
- View Patient Details
- Pagination
- Check-In Existing Patient

### Patient Check-In

- Select Existing Patient
- Assign Doctor
- Visit Date
- Visit Time
- Visit Type
- Priority
- Reason for Visit
- Symptoms
- Notes
- Confirm Check-In

---

# 👨‍⚕️ Junior Doctor Module

### Dashboard

- Patient Queue
- Search Patients
- Reviewed Patients
- Awaiting Review
- Consultation Status

---

# 👨‍⚕️ Doctor Module

## Dashboard

- Today's Queue
- Waiting Patients
- Completed Consultations
- Queue Status

---

## Clinical Consultation

### Clinical Details

- Presenting Symptoms
- Blood Pressure
- Pulse Rate
- Temperature
- SpO₂
- Weight
- Height
- Diagnosis

### Clinical Images

- Upload Images
- Drag & Drop Upload
- Image Preview
- Image Annotation
- Save Draft
- Complete Consultation

---

# 💊 Electronic Prescription

- Select Consulted Patient
- Add Multiple Medicines
- Dosage Selection
- Frequency Selection
- Duration
- Additional Notes
- Digital Prescription Generation

---

# 👨‍💼 Administration

## User Management

- Create User
- Edit User
- Delete User
- Activate User
- Deactivate User
- Role Assignment

## Doctor Management

- Add Doctor
- Edit Doctor
- Specialization
- Availability

## Audit Logs

- Login Logs
- User Activity
- System Events

## System Settings

- Hospital Information
- Working Hours
- Configuration Settings

---

# 🏥 Complete Workflow

```
Login
      │
      ▼
Receptionist Dashboard
      │
      ▼
Patient Registration
      │
      ▼
Search Patient
      │
      ▼
Patient Check-In
      │
      ▼
Doctor Queue
      │
      ▼
Doctor Consultation
      │
      ├──────────────► Clinical Details
      │
      ├──────────────► Clinical Images
      │
      ▼
Complete Consultation
      │
      ▼
Generate E-Prescription
      │
      ▼
Patient Records Updated
      │
      ▼
Visit Completed
```

---

# 🖥️ Technology Stack

## Frontend

- Angular 17
- TypeScript
- PrimeNG
- Angular Material
- HTML5
- SCSS
- RxJS

---

## Backend

- FastAPI
- Python
- SQLAlchemy
- Pydantic
- JWT Authentication

---

## Database

- PostgreSQL

---

## API

- REST API
- Swagger UI
- OpenAPI Documentation

---

## Development Tools

- Git
- GitHub
- VS Code
- Postman
- Figma

---

# 📁 Project Structure

```
Smart Clinical Management System
│
├── frontend
│   ├── auth
│   ├── receptionist
│   ├── doctor
│   ├── junior-doctor
│   ├── admin
│   ├── shared
│   ├── guards
│   ├── services
│   ├── models
│   └── assets
│
├── backend
│   ├── authentication
│   ├── patients
│   ├── doctors
│   ├── consultations
│   ├── prescriptions
│   ├── clinical_images
│   ├── appointments
│   ├── admin
│   ├── reports
│   ├── database
│   └── utils
│
└── database
    └── PostgreSQL
```

---

# 🧪 Testing

## Frontend Testing

✔ Login

✔ Reception Dashboard

✔ Patient Registration

✔ Search Patient

✔ Patient Check-In

✔ Doctor Dashboard

✔ Junior Doctor Dashboard

✔ Clinical Consultation

✔ Clinical Images

✔ Electronic Prescription

✔ Role-Based Navigation

✔ Form Validation

---

## Backend Testing

- Swagger UI
- REST API Testing
- CRUD Operations
- Authentication APIs
- Validation Testing
- Exception Handling
- Response Verification

---

# 🔒 User Roles

| Role | Responsibilities |
|------|------------------|
| Receptionist | Register patients, Search patients, Check-In patients |
| Junior Doctor | Review patient queue, View patient details |
| Doctor | Consultation, Diagnosis, Clinical Images, Prescription |
| Administrator | User Management, Doctor Management, Audit Logs, System Settings |

---

# 📸 Application Modules

### Authentication

- Secure Login

### Reception Portal

- Dashboard
- Registration
- Search
- Check-In

### Doctor Portal

- Dashboard
- Consultation
- Clinical Images
- E-Prescription
- Patient Records

### Junior Doctor Portal

- Queue
- Patient Review

### Admin Portal

- Dashboard
- Users
- Doctors
- Audit Logs
- Settings

---

# 🚀 Installation

## Clone Repository

```bash
git clone https://github.com/yourusername/smart-clinical-management-system.git
```

---

## Frontend

```bash
cd frontend

npm install

ng serve
```

Runs on

```
http://localhost:4200
```

---

## Backend

```bash
cd backend

pip install -r requirements.txt

uvicorn main:app --reload
```

Runs on

```
http://localhost:8000
```

---

## Swagger Documentation

```
http://localhost:8000/docs
```

---

---

# 👨‍💻 Developer

**Vivank Tyagi**

B.Tech Electrical Engineering (Computer Science Specialization)

Dayalbagh Educational Institute, Agra

**Gagan Singh**
B.Tech Electrical Engineering (Computer Science Specialization)

Dayalbagh Educational Institute, Agr


# 📊 Key Functionalities

- Secure Authentication
- Role-Based Authorization
- Patient Registration
- Queue Management
- Doctor Consultation
- Clinical Images
- Diagnosis
- Electronic Prescription
- Audit Logging
- Dashboard Analytics

---

# 🌟 Future Enhancements

- AI Disease Prediction
- Medical Image Analysis
- OCR Prescription Recognition
- WhatsApp Appointment Notifications
- SMS Notifications
- Billing Module
- Laboratory Module
- Pharmacy Integration
- Video Consultation
- Online Appointment Booking
- Patient Mobile Application
- Cloud Deployment

---

# 🎯 Real-World Problem Solved

Traditional clinics often rely on paper-based records, causing delays, duplication, and inefficient coordination between healthcare staff.

This system provides:

- Digital patient records
- Faster registration
- Efficient queue management
- Reduced paperwork
- Secure access control
- Electronic prescriptions
- Better doctor collaboration
- Improved patient experience
- Enhanced hospital productivity

---

# 📈 Project Highlights

- Full-Stack Healthcare Application
- Enterprise-Level Architecture
- Angular + FastAPI + PostgreSQL
- RESTful APIs
- JWT Authentication
- Role-Based Access
- Swagger API Documentation
- Responsive UI
- Modular Design
- Scalable Architecture


# 📄 License

This project is developed for educational, academic, and portfolio purposes.

© 2026 Vivank Tyagi. All Rights Reserved.
