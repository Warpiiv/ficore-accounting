import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Home from './components/Home';
import InvoiceForm from './components/InvoiceForm';
import TransactionForm from './components/TransactionForm';
import './App.css';

function App() {
  const [language, setLanguage] = useState('en');

  return (
    <Router>
      <div className="app">
        <header>
          <h1>Ficore Accounting</h1>
          <select onChange={(e) => setLanguage(e.target.value)} value={language}>
            <option value="en">English</option>
            <option value="ha">Hausa</option>
          </select>
        </header>
        <Routes>
          <Route path="/" element={<Home language={language} />} />
          <Route path="/invoices/create" element={<InvoiceForm language={language} />} />
          <Route path="/invoices/update/:invoiceId" element={<InvoiceForm language={language} />} />
          <Route path="/transactions" element={<TransactionForm language={language} />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
