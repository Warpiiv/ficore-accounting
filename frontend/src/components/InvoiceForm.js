import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

function InvoiceForm({ language }) {
  const [translations, setTranslations] = useState({});
  const [formData, setFormData] = useState({ customer_name: '', description: '', amount: '' });
  const navigate = useNavigate();
  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';

  useEffect(() => {
    fetch(`${backendUrl}/api/translations/${language}`)
      .then(res => res.json())
      .then(data => setTranslations(data));
  }, [language]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const response = await fetch(`${backendUrl}/api/invoices`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    });
    if (response.ok) {
      alert('Invoice saved!');
      navigate('/');
    } else {
      alert('Error saving invoice.');
    }
  };

  return (
    <div className="form-container">
      <h2>{translations.create_invoice}</h2>
      <form onSubmit={handleSubmit}>
        <label>
          {translations.customer_name}
          <input
            type="text"
            value={formData.customer_name}
            onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
            required
          />
        </label>
        <label>
          {translations.description}
          <input
            type="text"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            required
          />
        </label>
        <label>
          {translations.amount}
          <input
            type="number"
            value={formData.amount}
            onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
            required
            min="0"
          />
        </label>
        <button type="submit">
          <span role="img" aria-label="save">💾</span> {translations.save}
        </button>
      </form>
    </div>
  );
}

export default InvoiceForm;