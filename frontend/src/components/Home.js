import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

function Home({ language }) {
  const [translations, setTranslations] = useState({});
  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';

  useEffect(() => {
    fetch(`${backendUrl}/api/translations/${language}`)
      .then(res => res.json())
      .then(data => setTranslations(data));
  }, [language]);

  return (
    <div className="home">
      <h2>{translations.welcome}</h2>
      <div className="button-container">
        <Link to="/invoice">
          <button className="large-button">
            <span role="img" aria-label="receipt">📜</span> {translations.create_invoice}
          </button>
        </Link>
        <Link to="/transaction">
          <button className="large-button">
            <span role="img" aria-label="wallet">💰</span> {translations.track_transaction}
          </button>
        </Link>
      </div>
    </div>
  );
}

export default Home;