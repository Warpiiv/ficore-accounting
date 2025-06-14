Ficore Accounting
A simple accounting web application built with Flask and MongoDB.
Project Structure
ficore-accounting/
├── ficore_accounting/
│   ├── __init__.py
│   ├── app.py
│   ├── invoices/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── templates/
│   │       └── invoices/
│   │           ├── create.html
│   │           └── view.html
│   ├── transactions/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── templates/
│   │       └── transactions/
│   │           ├── add.html
│   │           └── history.html
│   ├── users/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── templates/
│   │       └── users/
│   │           ├── login.html
│   │           └── profile.html
│   ├── translations.py
│   └── templates/
│       ├── errors/
│       │   ├── 404.html
│       │   └── 500.html
│       ├── general/
│       │   ├── about.html
│       │   ├── feedback.html
│       │   ├── index.html
│       │   └── tool_header.html
│       ├── auth/
│       │   ├── signin.html
│       │   ├── signup.html
│       │   ├── forgot_password.html
│       │   └── reset_password.html
│       └── dashboard/
│           ├── admin_dashboard.html
│           └── general_dashboard.html
├── static/
│   ├── css/
│   │   └── styles.css
│   ├── js/
│   │   ├── interactivity.js
│   │   └── scripts.js
│   └── img/
├── requirements.txt
└── README.md

Setup

Clone the repository:
git clone <repository-url>
cd ficore-accounting


Create a virtual environment and activate it:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate


Install dependencies:
pip install -r requirements.txt


Set environment variables:
export SECRET_KEY='your-secret-key'
export MONGO_URI='your-mongodb-uri'


Run the application:
python -m ficore_accounting.app



Usage

Access the application at http://localhost:10000
Default routes include:
/invoices: Invoice dashboard
/transactions: Transaction history
/users/login: User login
/about: About page
/feedback: Feedback page
/dashboard/admin: Admin dashboard
/dashboard/general: General dashboard



Contributing
Contributions are welcome! Please submit a pull request or open an issue for any improvements or bug fixes.
License
MIT License
