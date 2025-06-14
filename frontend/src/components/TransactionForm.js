import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

function TransactionForm({ language }) {
  const [translations, setTranslations] = useState({});
  const [formData, setFormData] = useState({ type: 'income', category: 'Sales', amount: '', description: '' });
  const navigate = useNavigate();
  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';

  useEffect(() => {
    fetch(`${backendUrl}/api/translations/${language}`)
      .then(res => res.json())
      .then(data => setTranslations(data));
  }, [language]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const response = await fetch(`${backendUrl}/api/transactions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    });
    if (response.ok) {
      alert('Transaction saved!');
      navigate('/');
    } else {
      alert('Error saving transaction.');
    }
  };

  return (
    <div className="form-container">
      <h2>{translations.track_transaction}</h2>
      <form onSubmit={handleSubmit}>
        <label>
          {translations.type}
          <select
            value={formData.type}
            onChange={(e) => setFormData({ ...formData, type: e.target.value })}
          >
            <option value="income">{translations.money_in}</option>
            <option value="expense">{translations.money_out}</option>
          </select>
        </label>
        <label>
          {translations.category}
          <select
            value={formData.category}
            onChange={(e) => setFormData({ ...formData, category: e.target.value })}
          >
            <option value="Sales">{translations.sales}</option>
            <option value="Utilities">{translations.utilities}</option>
            <option value="Transport">{translations.transport}</option>
            <option value="Other">{translations.other}</option>
          </select>
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
        <label>
          {translations.description}
          <input
            type="text"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            required
          />
        </label>
        <button type="submit">
          <span role="img" aria-label="save">💾</span> {translations.save}
        </button>
      </form>
    </div>
  );
}

export default TransactionForm;