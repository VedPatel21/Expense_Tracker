Expense Tracker Web Application

Demo Video:- https://youtu.be/QKeGjSqJGvM

Description:
The Expense Tracker Web Application is a robust and user-friendly platform designed to assist users in efficiently managing their financial transactions. It empowers users to monitor their expenses, track income, set monthly budgets, and receive alerts for overspending. The application features a clean, intuitive interface and leverages Flask for backend operations and SQLite for database management.

This project was developed as part of the CS50 Final Project and meets the course’s requirements for complexity, functionality, and design.

Features:-

User Authentication:
Secure registration and login functionality.
Ensures that user data remains private and accessible only to authenticated users.

Expense Management:
Add, edit, delete, and view expenses, categorized for better financial analysis.

Income Management:
Add and track income entries to maintain a balanced financial overview.

Budgeting and Notifications:
Users can set monthly budgets for each category.
Automatic notifications are triggered if expenses exceed the set budgets.

Recurring Expenses:
Manage recurring expenses with automated tracking.

Data Visualization:
Generate graphical reports for a clear view of spending patterns.

Dark Mode:
Optional dark mode for better accessibility and a comfortable user experience.

File Structure
Root Directory
app.py: The main Python script containing the Flask application logic.
expense_tracker.db: SQLite database file for storing user data, expenses, income, and budget information.
Static Directory
styles.css: Primary stylesheet for the application's user interface.
dark-mode.css: Additional stylesheet for enabling dark mode.
Templates Directory
Here is a detailed list of all HTML pages in the project:

Base Templates:

layout.html: The base layout template reused across all pages for a consistent design.

Authentication:

register.html: Allows users to register for a new account.
login.html: Login page for returning users.
logout.html: Logs users out of their accounts securely.

Dashboard:

dashboard.html: The main dashboard with navigation options for all features.
Expense Management:

add_expense.html: Form to add new expense entries.
view_expenses.html: Displays all expense entries categorized and sorted.
add_recurring_expense.html: Page for adding and managing recurring expenses.
view_recurring_expenses.html: Displays recurring expense details.
import_expenses.html: Allows importing of expense data from external files.

Income Management:

add_income.html: Form to add income entries.
view_income.html: Displays income entries for tracking financial gains.

Budget Management:

set_budget.html: Allows users to set their monthly budgets for various categories.
view_budget.html: Displays the budget utilization and remaining amount for each category.

Shared Expenses:

share_expense.html: Facilitates sharing expenses with other users.
view_shared_expenses.html: Displays shared expenses with relevant details.

Data Visualization and Reporting:

generate_report.html: Page for generating detailed financial reports.
graphical_reports.html: Visual representation of financial trends through graphs and charts.

Notifications:

notifications.html: Displays alerts and notifications related to budgets and activities.

User Profile and Settings:

profile.html: Manage user profile details like name and email.
settings.html: Update application preferences and account settings.

Home Page:
index.html: The landing page where users are introduced to the application.

Design Decisions

Flask Framework:
Flask was chosen for its simplicity, scalability, and ease of integration with SQLite, making it suitable for this project’s needs.

SQLite Database:
SQLite provides a lightweight, file-based database solution for securely storing user and financial data.

Frontend Design:
The user interface prioritizes simplicity and responsiveness, ensuring compatibility across devices.

Notification System:
A key feature that helps users stay informed when spending exceeds predefined budgets.

Graphical Reports:
Data visualization was implemented to help users quickly grasp their financial situation through visual summaries.

How to Run the Application

Step 1: Clone the Repository
bash
git clone (https://github.com/VedPatel21/Expense_Tracker.git)

Step 2: Set Up the Virtual Environment
bash
cd Project  
python -m venv venv  
source venv/bin/activate  # For Mac/Linux  
venv\Scripts\activate     # For Windows  

Step 3: Install Dependencies
bash
Copy code
pip install -r requirements.txt  

Step 4: Run the Application
bash
Copy code
flask run  
Step 5: Access the Application
Visit http://127.0.0.1:5000/ in your web browser.

Acknowledgments
This project was created as part of CS50x 2024, leveraging knowledge gained from lectures and problem sets throughout the course. Special thanks to the CS50 team for their invaluable guidance.
