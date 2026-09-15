# ServiceFlow - Simple Python Project

This version is intentionally organized for beginner Python students.

## Where everything is

- `app.py` - all Python pages and application logic
- `database.py` - MySQL connection functions
- `schema.sql` - database tables
- `templates` - HTML user-interface pages
- `static/style.css` - all page styling
- `requirements.txt` - Python packages

The `backups` folder contains the previous Django version and database backup.
You do not need it while working on the Flask project.

## Start the project

1. Start MySQL from XAMPP.
2. Open PowerShell in this folder.
3. Run `.venv\Scripts\python app.py`.
4. Open `http://127.0.0.1:8000`.

## Demo accounts

- Customer: `customer` / `Customer2026!`
- Technician: `technician` / `Tech2026!`
- Admin: `admin` / `Admin2026!`

Customers request a service and track their assigned technician. Technicians
accept available requests, schedule the visit, update the status, and control GPS
sharing from Customer Map. A customer can see only the assigned technician for a
Scheduled or In Progress request, and only while that technician is sharing.
New users can choose Customer or Technician on the Create Account page.

The map includes Street Map and Satellite buttons. The satellite view uses Esri
World Imagery so this classroom project does not need a paid Google Maps API key.
When the technician shares GPS, the map draws a live driving route and updates
the estimated distance and travel time. Technicians can also open the selected
customer destination in Waze for turn-by-turn navigation.

Browser GPS works on localhost during development. A deployed website must use
HTTPS before browsers will allow location access.
