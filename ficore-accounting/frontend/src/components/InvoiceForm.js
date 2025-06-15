import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

function InvoiceForm({ language }) {
  const [translations, setTranslations] = useState({});
  const [formData, setFormData] = useState({
    customer_name: '',
    description: '',
    amount: '',
    status: 'pending',
    due_date: '',
    settled_date: ''
  });
  const navigate = useNavigate();
  const { invoiceId } = useParams();
  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';

  useEffect(() => {
    fetch(`${backendUrl}/api/translations/${language}`)
      .then(res => res.json())
      .then(data => setTranslations(data));
    
    if (invoiceId) {
      fetch(`${backendUrl}/api/invoices/${invoiceId}`)
        .then(res => res.json())
        .then(data => {
          setFormData({
            customer_name: data.customer_name,
            description: data.description,
            amount: data.amount,
            status: data.status,
            due_date: data.due_date ? data.due_date.split('T')[0] : '',
            settled_date: data.settled_date ? data.settled_date.split('T')[0] : ''
          });
        });
    }
  }, [language, invoiceId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const url = invoiceId ? `${backendUrl}/api/invoices/${invoiceId}` : `${backendUrl}/api/invoices`;
    const method = invoiceId ? 'PUT' : 'POST';
    
    const response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...formData,
        amount: parseFloat(formData.amount),
        due_date: formData.due_date || null,
        settled_date: formData.status === 'settled' ? (formData.settled_date || new Date().toISOString()) : null
      }),
    });
    
    if (response.ok) {
      alert(invoiceId ? translations.invoice_updated : translations.invoice_created);
      navigate('/');
    } else {
      alert(translations.error_saving);
    }
  };

  return (
    <div className="form-container max-w-2xl mx-auto p-6 bg-white rounded-lg shadow">
      <h2 className="text-2xl font-bold mb-6">{invoiceId ? translations.edit_invoice : translations.create_invoice}</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">
            {translations.customer_name}
            <input
              type="text"
              value={formData.customer_name}
              onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
              required
              className="mt-1 block w-full border border-gray-300 rounded-md p-2"
            />
          </label>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">
            {translations.description}
            <input
              type="text"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              required
              className="mt-1 block w-full border border-gray-300 rounded-md p-2"
            />
          </label>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">
            {translations.amount}
            <input
              type="number"
              value={formData.amount}
              onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
              required
              min="0"
              step="0.01"
              className="mt-1 block w-full border border-gray-300 rounded-md p-2"
            />
          </label>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">
            {translations.status}
            <select
              value={formData.status}
              onChange={(e) => setFormData({ ...formData, status: e.target.value })}
              className="mt-1 block w-full border border-gray-300 rounded-md p-2"
            >
              <option value="pending">{translations.pending}</option>
              <option value="settled">{translations.settled}</option>
            </select>
          </label>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">
            {translations.due_date}
            <input
              type="date"
              value={formData.due_date}
              onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
              className="mt-1 block w-full border border-gray-300 rounded-md p-2"
            />
          </label>
        </div>
        {formData.status === 'settled' && (
          <div>
            <label className="block text-sm font-medium text-gray-700">
              {translations.settled_date}
              <input
                type="date"
                value={formData.settled_date}
                onChange={(e) => setFormData({ ...formData, settled_date: e.target.value })}
                className="mt-1 block w-full border border-gray-300 rounded-md p-2"
              />
            </label>
          </div>
        )}
        <button
          type="submit"
          className="w-full bg-blue-600 text-white rounded-md py-2 hover:bg-blue-700"
        >
          <span role="img" aria-label="save">💾</span> {translations.save}
        </button>
      </form>
    </div>
  );
}

export default InvoiceForm;
