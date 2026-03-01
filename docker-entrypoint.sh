#!/bin/bash
set -e

# Create data directory if it doesn't exist
mkdir -p /app/src/data

# Print startup message
if [ ! -f "/app/src/data/setup_complete.json" ]; then
    echo "============================================================"
    echo "  First-time setup required!"
    echo "  Open http://<your-server-ip>:${PORT:-5000} to run the"
    echo "  setup wizard — it only takes about 2 minutes."
    echo "============================================================"
else
    echo "Setup complete. Starting Plex Portal..."
fi

# Start with Gunicorn (production WSGI server)
# Workers: 2×CPU+1 is a common rule of thumb; default to 2 for low-spec servers.
exec gunicorn \
    --workers "${GUNICORN_WORKERS:-2}" \
    --bind "0.0.0.0:${PORT:-5000}" \
    --timeout 120 \
    --preload \
    --access-logfile - \
    --error-logfile - \
    "src.main:app"
