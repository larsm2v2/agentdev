# n8n Workflows Directory

This directory contains n8n workflow definitions for the Enhanced Email Librarian system.

## Setup

The n8n service is configured to:

- Use a separate PostgreSQL database named `n8n`
- Mount this directory to `/home/node/.n8n/workflows`
- Enable basic authentication (admin/admin123)

## Access

- n8n Web Interface: http://localhost:5678
- Username: admin
- Password: admin123

## Database Configuration

n8n uses its own dedicated database:

- Database: `n8n`
- Host: `postgres` (Docker service)
- Port: 5432
- User: `librarian_user`
- Password: `secure_password_2024`

## Workflow Files

Place your n8n workflow JSON files in this directory. They will be automatically available in the n8n interface.
