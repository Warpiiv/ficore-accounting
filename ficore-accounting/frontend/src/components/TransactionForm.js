import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

function TransactionForm({ language }) {
  const [translations, setTranslations] = useState({});
  const [formData, setFormData] = useState({
    type: 'income',
    category: 'Sales',
    amount: '',
    description: '',
    tags: '',
    isRecurring: false,
    recurringPeriod: 'none',
  });
  const [suggestedCategories, setSuggestedCategories] = useState([]);
  const [errors, setErrors] = useState({});
  const navigate = useNavigate();
  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';

  useEffect(() => {
    fetch(`${backendUrl}/api/translations/${language}`)
      .then(res => res.json())
      .then(data => setTranslations(data));
  }, [language]);

  useEffect(() => {
    // Suggest categories based on description
    const description = formData.description.toLowerCase();
    const suggestions = [];
    if (description.includes('sale') || description.includes('revenue')) suggestions.push('Sales');
    if (description.includes('utility') || description.includes('bill')) suggestions.push('Utilities');
    if (description.includes('transport') || description.includes('travel')) suggestions.push('Transport');
    if (description.includes('misc') || description.includes('other')) suggestions.push('Other');
    setSuggestedCategories([...new Set(suggestions)]); // Remove duplicates
  }, [formData.description]);

  const validateForm = () => {
    const newErrors = {};
    if (!formData.amount || formData.amount <= 0) {
      newErrors.amount = translations.invalid_amount || 'Amount must be greater than zero';
    }
    if (!formData.description.trim()) {
      newErrors.description = translations.required_field || 'Description is required';
    }
    if (formData.tags && formData.tags.length > 200) {
      newErrors.tags = translations.tags_too_long || 'Tags cannot exceed 200 characters';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) {
      return;
    }
    const response = await fetch(`${backendUrl}/api/transactions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...formData,
        tags: formData.tags.split(',').map(tag => tag.trim()).filter(tag => tag),
      }),
    });
    if (response.ok) {
      alert(translations.transaction_saved || 'Transaction saved!');
      navigate('/');
    } else {
      alert(translations.error_saving || 'Error saving transaction.');
    }
  };

  return (
    <div className="form-container p-3">
      <h2>{translations.track_transaction || 'Add Transaction'}</h2>
      <form onSubmit={handleSubmit} className="needs-validation" noValidate>
        <div className="mb-3">
          <label className="form-label">{translations.type || 'Type'}</label>
          <select
            className="form-select"
            value={formData.type}
            onChange={(e) => setFormData({ ...formData, type: e.target.value })}
            required
          >
            <option value="income">{translations.money_in || 'Money In'}</option>
            <option value="expense">{translations.money_out || 'Money Out'}</option>
          </select>
        </div>
        <div className="mb-3">
          <label className="form-label">{translations.category || 'Category'}</label>
          <select
            className="form-select"
            value={formData.category}
            onChange={(e) => setFormData({ ...formData, category: e.target.value })}
            required
          >
            <option value="Sales">{translations.sales || 'Sales'}</option>
            <option value="Utilities">{translations.utilities || 'Utilities'}</option>
            <option value="Transport">{translations.transport || 'Transport'}</option>
            <option value="Other">{translations.other || 'Other'}</option>
            {suggestedCategories.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>
        <div className="mb-3">
          <label className="form-label">{translations.amount || 'Amount'}</label>
          <input
            type="number"
            className={`form-control ${errors.amount ? 'is-invalid' : ''}`}
            value={formData.amount}
            onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
            required
            min="0.01"
            step="0.01"
          />
          {errors.amount && <div className="invalid-feedback">{errors.amount}</div>}
        </div>
        <div className="mb-3">
          <label className="form-label">{translations.description || 'Description'}</label>
          <input
            type="text"
            className={`form-control ${errors.description ? 'is-invalid' : ''}`}
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            required
          />
          {errors.description && <div className="invalid-feedback">{errors.description}</div>}
        </div>
        <div className="mb-3">
          <label className="form-label">{translations.tags || 'Tags'}</label>
          <input
            type="text"
            className={`form-control ${errors.tags ? 'is-invalid' : ''}`}
            value={formData.tags}
            onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
            placeholder={translations.tags_placeholder || 'Enter tags, separated by commas'}
          />
          {errors.tags && <div className="invalid-feedback">{errors.tags}</div>}
        </div>
        <div className="mb-3 form-check">
          <input
            type="checkbox"
            className="form-check-input"
            checked={formData.isRecurring}
            onChange={(e) => setFormData({ ...formData, isRecurring: e.target.checked })}
          />
          <label className="form-check-label">{translations.recurring || 'Recurring Transaction'}</label>
        </div>
        {formData.isRecurring && (
          <div className="mb-3">
            <label className="form-label">{translations.recurring_period || 'Recurring Period'}</label>
            <select
              className="form-select"
              value={formData.recurringPeriod}
              onChange={(e) => setFormData({ ...formData, recurringPeriod: e.target.value })}
            >
              <option value="none">{translations.none || 'None'}</option>
              <option value="weekly">{translations.weekly || 'Weekly'}</option>
              <option value="monthly">{translations.monthly || 'Monthly'}</option>
              <option value="yearly">{translations.yearly || 'Yearly'}</option>
            </select>
          </div>
        )}
        <button type="submit" className="btn btn-primary w-100">
          <span role="img" aria-label="save">💾</span> {translations.save || 'Save'}
        </button>
      </form>
    </div>
  );
}

export default TransactionForm;
