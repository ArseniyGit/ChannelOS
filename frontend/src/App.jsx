import { useCallback, useEffect, useState } from 'react';
import Home from './pages/Home';
import Channels from './pages/Channels';
import Catalog from './pages/Catalog';
import Subscription from './pages/Subscription';
import SubmitAdvertisement from './pages/SubmitAdvertisement';
import MyAdvertisements from './pages/MyAdvertisements';
import PaymentSuccess from './pages/PaymentSuccess';
import AdvertisementPaymentSuccess from './pages/AdvertisementPaymentSuccess';
import PaymentCancel from './pages/PaymentCancel';
import Admin from './pages/Admin';
import './styles/App.css';
import { buildAuthHeaders, getInitData, getStartAppParam, getTelegramWebApp } from './utils/telegramAuth';

function App() {
  const [page, setPage] = useState('channels');
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const initData = getInitData();

    if (initData) {
      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL}/api/auth`, {
          method: 'POST',
          headers: buildAuthHeaders()
        });
        const data = await response.json();
        if (data.success) {
          setUser(data.user);
        }
      } catch (err) {
        console.error('Error refreshing user:', err);
      }
    }
  }, []);

  useEffect(() => {
    const tg = getTelegramWebApp();
    if (tg) {
      tg.ready();
      tg.expand();

      const currentPath = window.location.pathname;
      if (currentPath.includes('advertisement-payment-success')) {
        setPage('advertisement-payment-success');
      } else if (currentPath.includes('payment-success')) {
        setPage('payment-success');
      } else if (currentPath.includes('payment-cancel')) {
        setPage('payment-cancel');
      } else {
        const startParam = getStartAppParam();
        if (startParam === 'my_advertisements') {
          setPage('my-advertisements');
        } else if (startParam === 'submit_advertisement') {
          setPage('submit-advertisement');
        } else if (startParam === 'subscription') {
          setPage('subscription');
        } else if (startParam === 'admin') {
          setPage('admin');
        } else if (startParam === 'catalog') {
          setPage('catalog');
        } else if (startParam === 'home') {
          setPage('channels');
        }
      }

      const initData = getInitData();
      if (initData) {
        fetch(`${import.meta.env.VITE_API_URL}/api/auth`, {
          method: 'POST',
          headers: buildAuthHeaders()
        })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            setUser(data.user);
          }
          setLoading(false);
        })
        .catch(err => {
          console.error('Auth error:', err);
          setLoading(false);
        });
      } else {
        setLoading(false);
      }
    } else {
      const initData = getInitData({ persist: false });
      if (initData) {
        fetch(`${import.meta.env.VITE_API_URL}/api/auth`, {
          method: 'POST',
          headers: buildAuthHeaders()
        })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            setUser(data.user);
          }
        })
        .catch(err => {
          console.error('Auth error:', err);
        })
        .finally(() => {
          setLoading(false);
        });
      } else {
        setLoading(false);
      }
    }
  }, []);

  if (loading) {
    return (
      <div className="app">
        <div className="page">
          <h1 className="title">Загрузка...</h1>
        </div>
      </div>
    );
  }

  const renderPage = () => {
    switch(page) {
      case 'home':
        return <Home onNavigate={setPage} user={user} />;
      case 'channels':
        return <Channels onNavigate={setPage} user={user} refreshUser={refreshUser} />;
      case 'catalog':
        return <Catalog onNavigate={setPage} />;
      case 'subscription':
        return <Subscription onNavigate={setPage} refreshUser={refreshUser} />;
      case 'submit-advertisement':
        return <SubmitAdvertisement onNavigate={setPage} />;
      case 'my-advertisements':
        return <MyAdvertisements onNavigate={setPage} />;
      case 'payment-success':
        return <PaymentSuccess onNavigate={setPage} refreshUser={refreshUser} />;
      case 'advertisement-payment-success':
        return <AdvertisementPaymentSuccess onNavigate={setPage} refreshUser={refreshUser} />;
      case 'payment-cancel':
        return <PaymentCancel onNavigate={setPage} />;
      case 'admin':
        return <Admin onNavigate={setPage} />;
      default:
        return <Channels onNavigate={setPage} user={user} refreshUser={refreshUser} />;
    }
  };

  return <div className="app">{renderPage()}</div>;
}

export default App;
