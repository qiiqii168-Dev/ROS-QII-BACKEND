ROS QII Independent Test API — Render deployment

This is the independent test API backend, not the original Rules of Survival server.
It provides test login/register/profile/lobby endpoints only; no live game server,
real matchmaking, or battle gameplay.

Deploy as a Render Web Service:
  Runtime: Python 3
  Root Directory: (leave blank; these files are at repository root)
  Build Command: pip install -r requirements.txt
  Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
  Health Check Path: /health

Add environment variable:
  ADMIN_TOKEN = a long random secret (do not share it publicly)

For initial API connectivity testing, the default SQLite database is ephemeral.
Data may be lost when the free service restarts or redeploys. For durable player
accounts, configure persistent storage or migrate to a managed database before
using this beyond testing.

After deploy, test:
  https://YOUR-SERVICE.onrender.com/health
Then put the base URL (without /health) in the iOS app's SERVER field.
