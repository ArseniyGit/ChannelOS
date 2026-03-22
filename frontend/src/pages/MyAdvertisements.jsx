import { useState, useEffect } from 'react';
import Notification from '../components/Notification';
import { useNotification } from '../hooks/useNotification';
import { buildAuthHeaders, getInitData, getTelegramWebApp } from '../utils/telegramAuth';
import { firstResolvedMediaUrl } from '../utils/mediaUrl';

export default function MyAdvertisements({ onNavigate }) {
  const [advertisements, setAdvertisements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAd, setSelectedAd] = useState(null);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [isPaying, setIsPaying] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const { notification, showNotification, hideNotification } = useNotification();

  useEffect(() => {
    loadAdvertisements();
    loadUser();
    // loadAdvertisements is intentionally stable for first-load behavior.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadUser = async () => {
    try {
      const initData = getInitData();
      
      if (initData) {
        const response = await fetch(`${import.meta.env.VITE_API_URL}/api/auth`, {
          method: 'POST',
          headers: buildAuthHeaders()
        });
        
        const data = await response.json();
        if (data.success) {
          setCurrentUser(data.user);
        }
      }
    } catch (err) {
      console.error('Error loading user:', err);
    }
  };

  const loadAdvertisements = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/advertisements/my`, {
        headers: buildAuthHeaders({}, { requireInitData: true })
      });

      const data = await response.json();
      
      if (data.success) {
        setAdvertisements(data.advertisements);
      }
    } catch (err) {
      console.error('Error loading advertisements:', err);
      showNotification('❌ Ошибка при загрузке рекламы', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handlePay = async (ad) => {
    setSelectedAd(ad);
    setShowPaymentModal(true);
  };

  const handlePaymentMethod = async (method) => {
    if (!selectedAd || isPaying) return;
    setIsPaying(true);

    try {
      const tg = getTelegramWebApp();
      
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/advertisements/${selectedAd.id}/pay`, {
        method: 'POST',
        headers: buildAuthHeaders(
          { 'Content-Type': 'application/json' },
          { requireInitData: true }
        ),
        body: JSON.stringify({ payment_method: method })
      });

      const data = await response.json();
      
      if (data.success) {
        if (method === 'stars' && data.invoice_link) {
          if (!tg?.openInvoice) {
            showNotification('❌ Оплата Stars доступна только внутри Telegram Mini App', 'error');
            setIsPaying(false);
            return;
          }
          tg.openInvoice(data.invoice_link, async (status) => {
            if (status === 'paid') {
              showNotification('✅ Реклама оплачена и отправлена на модерацию.', 'success');
              await loadAdvertisements();
              setShowPaymentModal(false);
              
              setTimeout(() => {
                showNotification('💡 После одобрения администратором реклама будет опубликована', 'info');
              }, 3000);
            } else if (status === 'cancelled') {
              showNotification('❌ Оплата отменена', 'warning');
            } else if (status === 'failed') {
              showNotification('❌ Ошибка при оплате', 'error');
            }
            setIsPaying(false);
          });
        } else if (method === 'stripe' && data.checkout_url) {
          if (data.session_id) {
            localStorage.setItem('pending_stripe_session', data.session_id);
          }
          if (tg && tg.openLink) {
            tg.openLink(data.checkout_url);
            showNotification('💳 Открываем страницу оплаты Stripe...', 'info');
          } else {
            window.location.href = data.checkout_url;
          }
          return;
        }
      } else {
        showNotification(`❌ ${data.detail || 'Ошибка при создании платежа'}`, 'error');
      }
    } catch (err) {
      console.error('Error creating payment:', err);
      showNotification('❌ Ошибка при создании платежа', 'error');
    } finally {
      setIsPaying(false);
    }
  };

  const getStatusBadge = (ad) => {
    if (ad.is_published) {
      return <span style={{ color: '#4caf50', fontWeight: '600' }}>✓ Опубликована</span>;
    }
    if (ad.status === 'pending') {
      return <span style={{ color: '#ff9800', fontWeight: '600' }}>⏳ На модерации</span>;
    }
    if (ad.status === 'unpaid') {
      return <span style={{ color: '#f44336', fontWeight: '600' }}>💳 Ожидает оплаты</span>;
    }
    if (ad.status === 'approved') {
      return <span style={{ color: '#2196f3', fontWeight: '600' }}>✓ Одобрена</span>;
    }
    if (ad.status === 'rejected') {
      return <span style={{ color: '#f44336', fontWeight: '600' }}>✗ Отклонена</span>;
    }
    return <span>—</span>;
  };

  if (loading) {
    return (
      <div className="page">
        <h1 className="title">Загрузка...</h1>
      </div>
    );
  }

  return (
    <div className="page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', width: '100%', flexWrap: 'wrap', gap: '10px' }}>
        <h1 className="title" style={{ margin: 0 }}>📢 Мои рекламы</h1>
        <button
          onClick={() => onNavigate('submit-advertisement')}
          className="access-btn"
          style={{ width: 'auto', minWidth: '140px' }}
        >
          + Подать рекламу
        </button>
      </div>

      {advertisements.length === 0 ? (
        <div className="channel-card" style={{ textAlign: 'center', padding: '40px 20px', flexDirection: 'column' }}>
          <div style={{ fontSize: '48px', marginBottom: '15px' }}>📢</div>
          <div style={{ fontSize: '18px', fontWeight: '600', marginBottom: '10px', color: '#1a1a1a' }}>
            У вас пока нет рекламы
          </div>
          <div style={{ fontSize: '14px', color: '#666', marginBottom: '20px' }}>
            Создайте первую рекламу для размещения в каналах и группах
          </div>
          <button
            onClick={() => onNavigate('submit-advertisement')}
            className="buy-btn"
            style={{ width: 'auto', padding: '12px 30px' }}
          >
            Подать рекламу
          </button>
        </div>
      ) : (
        <div className="channels-list">
          {advertisements.map((ad) => (
            <div
              key={ad.id}
              className="channel-card"
              style={{ flexDirection: 'column', alignItems: 'stretch' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px', width: '100%' }}>
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600', color: '#1a1a1a', flex: 1 }}>
                  {ad.title}
                </h3>
                <div style={{ marginLeft: '10px' }}>
                  {getStatusBadge(ad)}
                </div>
              </div>
              
              <p style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#666', lineHeight: '1.5' }}>
                {ad.content}
              </p>

              {ad.media_url && (
                <div style={{ marginBottom: '12px' }}>
                  <img
                    src={firstResolvedMediaUrl(ad.media_url)}
                    alt={ad.title}
                    style={{
                      maxWidth: '100%',
                      borderRadius: '8px',
                      marginTop: '10px'
                    }}
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px', width: '100%', flexWrap: 'wrap', gap: '10px' }}>
                <div style={{ fontSize: '13px', color: '#666' }}>
                  <div>Цена: <strong style={{ color: '#1a1a1a' }}>${parseFloat(ad.price).toFixed(2)}</strong></div>
                  <div style={{ marginTop: '5px' }}>
                    Создано: {new Date(ad.created_at).toLocaleDateString('ru-RU')}
                  </div>
                </div>
                
                {ad.status === 'unpaid' && !ad.is_published && (
                  <button
                    onClick={() => handlePay(ad)}
                    className="access-btn"
                    style={{ width: 'auto', minWidth: '120px' }}
                  >
                    💳 Оплатить
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showPaymentModal && selectedAd && (
        <div 
          className="modal-overlay" 
          onClick={() => setShowPaymentModal(false)}
        >
          <div 
            className="modal-content" 
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="modal-title">Оплата рекламы</h2>
            <div className="modal-tariff-info">
              <p className="modal-tariff-name">{selectedAd.title}</p>
              <p className="payment-price">
                ${parseFloat(selectedAd.price).toFixed(2)}
              </p>
            </div>

            <div className="payment-methods">
              <button
                onClick={() => handlePaymentMethod('stars')}
                className="payment-method-btn stars-btn"
                disabled={isPaying}
              >
                <div className="payment-icon">⭐</div>
                <div className="payment-name">Telegram Stars</div>
              </button>

              <button
                onClick={() => handlePaymentMethod('stripe')}
                className="payment-method-btn stripe-btn"
                disabled={isPaying}
              >
                <div className="payment-icon">💳</div>
                <div className="payment-name">Банковская карта</div>
              </button>
            </div>

            <button
              onClick={() => setShowPaymentModal(false)}
              className="modal-close-btn"
            >
              Отмена
            </button>
          </div>
        </div>
      )}

      {/* Нижнее меню навигации */}
      <div className="bottom-nav">
        <button className="nav-btn active" onClick={() => onNavigate('channels')}>
          <span>📢</span>
          <span>Каналы</span>
        </button>
        <button className="nav-btn" onClick={() => onNavigate('catalog')}>
          <span>📋</span>
          <span>Каталог</span>
        </button>
        <button className="nav-btn" onClick={() => onNavigate('subscription')}>
          <span>⭐</span>
          <span>Звание</span>
        </button>
        {currentUser?.is_admin && (
          <button className="nav-btn nav-btn-admin" onClick={() => onNavigate('admin')}>
            <span>🔧</span>
            <span>Админка</span>
          </button>
        )}
      </div>

      {notification && (
        <Notification
          message={notification.message}
          type={notification.type}
          onClose={hideNotification}
        />
      )}
    </div>
  );
}
