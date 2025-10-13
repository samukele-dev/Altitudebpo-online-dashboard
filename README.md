# Altitudebpo-online-dashboard
Call Centre Performance Dashboard built with Flask and Tailwind CSS. Features KPI tracking and team filtering.

This project is a modern, responsive web application designed to track and visualize call centre performance metrics (KPIs) in real-time. Built with Flask and styled using Tailwind CSS, it provides managers and analysts with a clean interface for data analysis and performance monitoring.

# Key Features
KPI Tracking: Instantly view high-level metrics (Total Target, Total Current, Total Shortfall) across all filtered teams.

Team Filtering: Utilize a multi-select filter to dynamically narrow down the data shown in the table to specific teams.

Dynamic Data Table: Displays detailed performance statistics per team, including Target, Current, and Shortfall, with color-coded status badges (Achieved/Behind).

File Upload Utility: Securely upload new performance data via an Excel file to update the dashboard.

Responsive Design: Optimized for viewing on desktops, tablets, and mobile devices (using Tailwind CSS).

Automatic Flash Messages: Success/Error messages automatically dismiss after a few seconds for better user experience.

# Technology Stack
Backend: Python (Flask)

Database: (Assuming local file processing, if using a DB, list it here)

Frontend Styling: Tailwind CSS

Templating: Jinja2

Data Processing: Pandas / Openpyxl (for Excel file handling)

Deployment: Ready for deployment on platforms like Render or Heroku (using Gunicorn).

# Deployment Instructions
Clone the repository.

Install dependencies: pip install -r requirements.txt

Set up environment variables (SECRET_KEY).

Run locally: python app.py (or use the Gunicorn command for production)
