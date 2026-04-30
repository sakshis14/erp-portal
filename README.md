
# ERP Portal – DevOps Project

A comprehensive ERP system for efficient **intern and employee management** built using **Flask and DevOps practices**.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Flask](https://img.shields.io/badge/Flask-Backend-black)
![GitHub](https://img.shields.io/badge/GitHub-VersionControl-orange)
![CI/CD](https://img.shields.io/badge/GitHub%20Actions-CI%2FCD-blue)
![Docker](https://img.shields.io/badge/Docker-Container-blue)
![Kubernetes](https://img.shields.io/badge/Kubernetes-Orchestration-blue)
CICD UPDATED

---

# Table of Contents

* [Overview](#overview)
* [Features](#features)
* [Technology Stack](#technology-stack)
* [DevOps Pipeline](#devops-pipeline)
* [Installation](#installation)
* [Running the Application](#running-the-application)
* [Project Structure](#project-structure)
* [Future Improvements](#future-improvements)

---

# Overview

The ERP Portal is designed to manage interns and employees efficiently within an organization.

The system provides functionalities such as:

* Intern management
* Attendance tracking
* Task assignment and monitoring
* Certificate generation
* Messaging system

This project also demonstrates **DevOps practices** including:

* Version control using Git & GitHub
* Continuous Integration using GitHub Actions
* Containerization using Docker
* Deployment using Kubernetes

---

# Features

* Intern Management System
* Attendance Tracking
* Task Management
* Messaging System
* Certificate Generation
* Admin Dashboard
* Submission Management

---

# Technology Stack

### Backend

* Python
* Flask

### Frontend

* HTML
* CSS
* JavaScript

### DevOps Tools

* Git
* GitHub
* GitHub Actions (CI/CD)
* Docker
* Kubernetes

---

# DevOps Pipeline

Developer pushes code → GitHub Repository → GitHub Actions CI Pipeline → Docker Containerization → Kubernetes Deployment

Whenever code is pushed to the repository, **GitHub Actions automatically runs the CI pipeline to validate the application**.

---

# Installation

Clone the repository:

```
git clone https://github.com/sakshis14/erp-portal.git
```

Navigate into the project directory:

```
cd erp-portal
```

Install dependencies:

```
pip install -r req.txt
```

---

# Running the Application

Run the Flask application:

```
python app.py
```

Open in browser:

```
http://localhost:5000
```

---

# Project Structure

ERP-Portal
│
├── app.py
├── req.txt
├── Dockerfile
├── README.md
├── .gitignore
│
├── static/
├── templates/
│
├── .github/
│   └── workflows/
│       └── ci.yml

---

# Future Improvements

* Docker build automation in CI pipeline
* Kubernetes deployment
* Monitoring with Prometheus and Grafana
* Cloud deployment on AWS
