import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

function Home({ language }) {
  const [translations, setTranslations] = useState({});
  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';

  useEffect(() => {
    fetch(`${backendUrl}/api/translations/${language}`)
      .then(res => res.json())
      .then(data => setTranslations(data.translations));
  }, [language]);

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-6">
      <h1 className="text-4xl font-bold mb-8">{translations.welcome || 'Welcome to Ficore Accounting'}</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl w-full">
        <Link
          to="/invoices/invoice_dashboard"
          className="bg-blue-600 text-white rounded-lg p-6 text-center hover:bg-blue-700 transition"
        >
          <h2 className="text-2xl font-semibold">{translations.core_invoices || 'Manage Invoices'}</h2>
          <p className="mt-2">{translations.invoices_desc || 'Create, edit, and track invoices'}</p>
        </Link>
        <Link
          to="/transactions"
          className="bg-green-600 text-white rounded-lg p-6 text-center hover:bg-green-700 transition"
        >
          <h2 className="text-2xl font-semibold">{translations.transactions || 'Manage Transactions'}</h2>
          <p className="mt-2">{translations.transactions_desc || 'Record and view transactions'}</p>
        </Link>
        <Link
          to="/feedback"
          className="bg-purple-600 text-white rounded-lg p-6 text-center hover:bg-purple-700 transition"
        >
          <h2 className="text-2xl font-semibold">{translations.feedback || 'Provide Feedback'}</h2>
          <p className="mt-2">{translations.feedback_desc || 'Share your thoughts on the app'}</p>
        </Link>
        <Link
          to="/dashboard/admin"
          className="bg-red-600 text-white rounded-lg p-6 text-center hover:bg-red-700 transition"
        >
          <h2 className="text-2xl font-semibold">{translations.admin_dashboard || 'Admin Dashboard'}</h2>
          <p className="mt-2">{translations.admin_dashboard_desc || 'Manage users and settings'}</p>
        </Link>
      </div>
    </div>
  );
}

export default Home;
