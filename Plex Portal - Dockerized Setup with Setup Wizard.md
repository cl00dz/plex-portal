# Plex Portal - Dockerized Setup with Setup Wizard

This document provides instructions for deploying the Plex Portal application using Docker and Portainer.

## Overview

The Plex Portal application has been dockerized with the following components:

1. **Flask Application**: The main Plex Portal web application
2. **MySQL Database**: For storing user data and application state
3. **Setup Wizard**: First-run configuration interface for easy setup

## Prerequisites

- Docker and Docker Compose installed on your server
- Portainer installed (for stack deployment)
- A Plex server with API access
- Overseerr installed and configured (optional)

## First-Run Setup Wizard

Plex Portal now includes a setup wizard that runs automatically when you first start the container. This makes configuration much easier:

1. Deploy the application using Docker Compose or Portainer Stack (instructions below)
2. Access the application at `http://your-server-ip:5000`
3. You'll be automatically redirected to the setup wizard
4. Enter your Plex server URL, Plex token, Overseerr URL, and Overseerr API key
5. Click "Save Configuration" to complete the setup

The setup wizard will save your configuration and make it persistent across container restarts. You only need to complete this setup once.

## Environment Variables

While the setup wizard is the recommended way to configure the application, you can still use environment variables if preferred:

### Application Settings
- `SECRET_KEY`: Secret key for Flask sessions (change this in production)
- `DEBUG`: Set to "True" for development, "False" for production
- `PORT`: The port to expose the application on (default: 5000)

### Plex Integration
- `PLEX_SERVER_URL`: URL of your Plex server (e.g., http://192.168.1.100:32400)
- `PLEX_TOKEN`: Your Plex authentication token

### Overseerr Integration
- `OVERSEERR_URL`: URL of your Overseerr instance (e.g., http://192.168.1.100:5055)
- `OVERSEERR_API_KEY`: Your Overseerr API key

### Database Settings
- `DB_HOST`: MySQL host (default: db)
- `DB_PORT`: MySQL port (default: 3306)
- `DB_USERNAME`: MySQL username (default: plex_portal)
- `DB_PASSWORD`: MySQL password (change this in production)
- `DB_NAME`: MySQL database name (default: plex_portal_db)
- `MYSQL_ROOT_PASSWORD`: Root password for MySQL (change this in production)

## Deployment Instructions

### Option 1: Using Docker Compose

1. Clone the repository to your server
2. Navigate to the project directory
3. Create a `.env` file with your environment variables (optional with setup wizard)
4. Run the following command:

```bash
docker-compose up -d
```

### Option 2: Using Portainer Stack

1. Log in to your Portainer instance
2. Go to Stacks → Add stack
3. Upload the `docker-compose.yml` file or paste its contents
4. Configure your environment variables (optional with setup wizard)
5. Deploy the stack

## Accessing the Application

Once deployed, the application will be available at:

```
http://your-server-ip:5000
```

If this is your first time running the application, you'll be automatically redirected to the setup wizard.

## Persistent Data

The application uses Docker volumes to ensure your configuration and database data persist across container restarts and updates:

- `plex-portal-data`: Stores application configuration and setup state
- `plex-portal-db`: Stores the MySQL database

## Maintenance

### Viewing Logs

```bash
docker logs plex-portal
```

### Updating the Application

1. Pull the latest code
2. Rebuild and restart the containers:

```bash
docker-compose down
docker-compose up -d --build
```

Your configuration will be preserved during updates thanks to the persistent volumes.

### Backing Up the Database

```bash
docker exec plex-portal-db mysqldump -u root -p plex_portal_db > backup.sql
```

### Resetting the Setup Wizard

If you need to run the setup wizard again:

```bash
docker exec plex-portal rm -f /app/src/data/setup_complete.json
docker restart plex-portal
```
