# ROS QII Independent Test API
This is an independent test backend. It is **not** the original Rules of Survival server and does not implement the game's private protocol, matchmaking, or battle simulation.

## Run
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
export ADMIN_TOKEN='replace-with-a-long-random-secret'
uvicorn main:app --host 0.0.0.0 --port 8000
```
Open `/docs` for API docs. SQLite persists player accounts and tickets. Change the admin token before exposing the service publicly; use HTTPS behind a reverse proxy.

New accounts receive 9,999,999 test diamonds and gold by default. Queue endpoints only acknowledge a test queue; they do not start a match.
