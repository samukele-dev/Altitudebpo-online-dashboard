# Altitudebpo-online-dashboard
Call Centre Performance Dashboard built with Flask and Tailwind CSS. Live KPI tracking per floor and team.

This project is a responsive web application that shows call centre performance in real time. Team stats are
**pulled live from the Call Centre Reporting Suite backend** (which reads the call-centre database), so this app
never connects to the database itself and does **not** need its IP whitelisted.

# Key Features
Live team stats: for every team, today's **Target**, **Current** (sales), **Shortfall** and **Avg Talk Time**, with a
**floor total row** at the bottom (the total average talk time is weighted: total talk time ÷ total answered calls).

Floors: Floor 1 (Assupol, Hollard, 1Life), Floor 2 (Vodacom Funeral) and a read-only Global view of both.

Editable targets: Floor 1 / Floor 2 managers edit a team's Target right in the table (saved in the Reporting Suite, since
the database holds no targets). Global is read-only.

Auto refresh: the numbers re-load every 30 seconds without a page reload. If the Reporting Suite is unreachable the
last numbers are shown with a warning.

Sales Breakdown: still uploaded by hand (Excel) per floor.

# How the data flows
`Browser → this dashboard (Flask) → Reporting Suite backend → call-centre DB`

- "Today" is South African time (midnight to now).
- **Current** = calls today whose outcome carries the database's own sale flag.
- **Avg Talk Time** = total talk time ÷ number of answered calls (talk time > 0), shown as m:ss.
- Which database teams count toward each dashboard row is configured in the Reporting Suite admin
  (**Dashboard teams** → *source team names*). Rows not linked yet show zeros and a "not linked" tag.
  `python manage.py list_active_teams` (in the Suite backend) lists today's real team names to choose from.

# Technology Stack
Backend: Python (Flask) + Flask-SocketIO

Data: Reporting Suite backend API (`requests`) — no database in this app

Frontend Styling: Tailwind CSS · Templating: Jinja2

Data Processing: Pandas / Openpyxl (Sales Breakdown upload only)

Deployment: Render or Heroku.

# Deployment Instructions
1. Clone the repository and `pip install -r requirements.txt`.
2. On the **Reporting Suite backend**: run `python manage.py migrate`, then `python manage.py dashboard_api_token`
   (prints the token), and add the teams in the admin under **Dashboard teams**.
3. On this dashboard set the environment variables:
   - `SECRET_KEY`
   - `SUITE_API_URL` — the Reporting Suite backend URL (e.g. `https://call-centre-backend.onrender.com`)
   - `SUITE_API_TOKEN` — the token from step 2
4. Run locally: `python app.py` (or the Gunicorn command for production).
