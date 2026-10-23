# Smart Rental System - RentNest

Flask + SQLite rental management project with Owner and Tenant workflows.

## Features
- Owner and Tenant registration/login
- Owner dashboard and property management
- Add, edit and delete properties with image upload
- Dynamic property listing with search, property type and maximum-rent filters
- Property details and tenant rental requests
- Owner accepts/rejects rental requests
- Property status changes to Rented after acceptance
- Tenant booking/request history
- Tenant maintenance requests and owner status updates
- Owner rent records: add, edit, delete and mark as paid
- Tenant rent records
- Profile page
- Responsive CSS UI

## Run on Windows
1. Install Python 3.10+.
2. Open this folder in VS Code.
3. Open Terminal.
4. Run: python -m venv venv
5. Activate: venv\\Scripts\\activate
6. Install: pip install -r requirements.txt
7. Start: python app.py
8. Open: http://127.0.0.1:5000

SQLite is used, so MySQL/XAMPP is not required.
The database file rental.db is created/updated automatically.

## Main files
- app.py - Flask routes and application logic
- database.py - SQLite connection and table creation
- templates/ - HTML pages
- static/style.css - UI styling
- static/uploads/ - uploaded property images
