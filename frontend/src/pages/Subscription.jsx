import { useEffect, useState } from 'react';
import PrivacyButton from '../components/PrivacyButton';
import Notification from '../components/Notification';
import { useNotification } from '../hooks/useNotification';
import { buildAuthHeaders, getInitData, getTelegramWebApp } from '../utils/telegramAuth';

export default function Subscription({ onNavigate, refreshUser }) {
  const [subscription, setSubscription] = useState(null);
  const [tariffs, setTariffs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTariff, setSelectedTariff] = useState(null);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [paymentInfo, setPaymentInfo] = useState(null);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [rankInfo, setRankInfo] = useState(null);
  const [showRanksModal, setShowRanksModal] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const { notification, showNotification, hideNotification } = useNotification();

  useEffect(() => {
    const initData = getInitData();

    if (initData) {
      fetch(`${import.meta.env.VITE_API_URL}/api/auth`, {
        method: 'POST',
        headers: buildAuthHeaders()
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            setCurrentUser(data.user);
          }
        })
        .catch(err => console.error('Error loading user:', err));

      fetch(`${import.meta.env.VITE_API_URL}/api/subscription`, {
        headers: buildAuthHeaders()
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            setSubscription(data);
          }
        })
        .catch(err => console.error('Error loading subscription:', err));

      fetch(`${import.meta.env.VITE_API_URL}/api/my-rank`, {
        headers: buildAuthHeaders()
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            setRankInfo(data);
          }
        })
        .catch(err => console.error('Error loading rank:', err));
    }

    // Загружаем доступные тарифы (всегда показываем)
    fetch(`${import.meta.env.VITE_API_URL}/api/tariffs`, {
      headers: {
        'ngrok-skip-browser-warning': 'true'
      }
    })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setTariffs(data.tariffs);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error('Error loading tariffs:', err);
        setLoading(false);
      });
  }, []);

  const handleBuyTariff = async (tariff) => {
    setSelectedTariff(tariff);

    // Загружаем информацию о ценах
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/payment-info/${tariff.id}`, {
        headers: {
          'ngrok-skip-browser-warning': 'true'
        }
      });
      const data = await response.json();
      if (data.success) {
        setPaymentInfo(data);
        setShowPaymentModal(true);
      }
    } catch (err) {
      console.error('Error loading payment info:', err);
      showNotification('❌ Ошибка при загрузке информации о платеже', 'error');
    }
  };

  const handlePaymentMethod = async (method) => {
    const tg = getTelegramWebApp();
    const initData = getInitData();

    if (!initData) {
      showNotification('❌ Ошибка: не удалось получить данные Telegram', 'error');
      return;
    }

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/create-payment`, {
        method: 'POST',
        headers: buildAuthHeaders(
          { 'Content-Type': 'application/json' },
          { requireInitData: true }
        ),
        body: JSON.stringify({
          tariff_id: selectedTariff.id,
          payment_method: method
        })
      });

      const data = await response.json();

      if (data.success) {
        if (method === 'stars') {
          if (!tg?.openInvoice) {
            showNotification('❌ Оплата Stars доступна только внутри Telegram Mini App', 'error');
            return;
          }
          tg.openInvoice(data.invoice_link, async (status) => {
            if (status === 'paid') {
              showNotification('✅ Оплата успешна! Подписка активирована.', 'success');
              setShowPaymentModal(false);

              if (refreshUser) {
                await refreshUser();
              }

              window.location.reload();
            } else if (status === 'cancelled') {
              showNotification('❌ Оплата отменена', 'warning');
            } else if (status === 'failed') {
              showNotification('❌ Ошибка при оплате', 'error');
            }
          });
        } else if (method === 'stripe') {
          if (data.session_id) {
            localStorage.setItem('pending_stripe_session', data.session_id);
          }
          // Открываем страницу оплаты Stripe в браузере
          if (tg?.openLink) {
            tg.openLink(data.checkout_url);
          } else {
            window.location.href = data.checkout_url;
          }
          showNotification('💳 Открываем страницу оплаты Stripe...', 'info');
          setShowPaymentModal(false);
        }
      } else {
        throw new Error(data.detail || 'Payment creation failed');
      }
    } catch (err) {
      console.error('Error creating payment:', err);
      showNotification(`❌ Ошибка: ${err.message}`, 'error');
    }
  };

  const handleCancelSubscription = async () => {
    const initData = getInitData();

    if (!initData) {
      showNotification('❌ Ошибка: не удалось получить данные Telegram', 'error');
      return;
    }

    setIsCancelling(true);

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/cancel-subscription`, {
        method: 'POST',
        headers: buildAuthHeaders({}, { requireInitData: true })
      });

      const data = await response.json();

      if (data.success) {
        showNotification('✓ Подписка отменена', 'success');
        setShowCancelModal(false);

        if (refreshUser) {
          await refreshUser();
        }

        window.location.reload();
      } else {
        throw new Error(data.detail || 'Failed to cancel subscription');
      }
    } catch (err) {
      console.error('Error cancelling subscription:', err);
      showNotification(`❌ Ошибка при отмене подписки: ${err.message}`, 'error');
    } finally {
      setIsCancelling(false);
    }
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
      <h1 className="title">Мои подписки</h1>

      {rankInfo?.current_rank && (
        <div className="rank-card" style={{
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          borderRadius: '14px',
          padding: '16px',
          marginBottom: '20px',
          boxShadow: '0 8px 16px rgba(0,0,0,0.3)',
          width: '100%'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: 0 }}>
              <span style={{ fontSize: '40px', flexShrink: 0 }}>{rankInfo.current_rank.icon_emoji}</span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <h3 style={{
                  color: 'white',
                  margin: 0,
                  fontSize: '18px',
                  fontWeight: 'bold'
                }}>
                  {rankInfo.current_rank.name}
                </h3>
                <p style={{
                  color: 'rgba(255,255,255,0.8)',
                  margin: '4px 0 0 0',
                  fontSize: '12px',
                  lineHeight: '1.3'
                }}>
                  {rankInfo.current_rank.description}
                </p>
              </div>
            </div>
            <button
              onClick={() => setShowRanksModal(true)}
              style={{
                background: 'rgba(255,255,255,0.2)',
                border: 'none',
                borderRadius: '8px',
                color: 'white',
                padding: '6px 10px',
                fontSize: '12px',
                cursor: 'pointer',
                fontWeight: 'bold',
                flexShrink: 0,
                whiteSpace: 'nowrap'
              }}
            >
              Все звания
            </button>
          </div>

          <div style={{
            background: 'rgba(255,255,255,0.15)',
            borderRadius: '10px',
            padding: '10px'
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              color: 'white',
              marginBottom: '6px',
              fontSize: '13px'
            }}>
              <span>Дней подписки:</span>
              <span style={{ fontWeight: 'bold' }}>
                {rankInfo.current_rank.current_subscription_days}
              </span>
            </div>

            {rankInfo.next_rank && (
              <>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  color: 'rgba(255,255,255,0.9)',
                  marginBottom: '6px',
                  fontSize: '12px',
                  gap: '8px'
                }}>
                  <span>До следующего:</span>
                  <span style={{ fontWeight: 'bold', textAlign: 'right' }}>
                    {rankInfo.next_rank.icon_emoji} {rankInfo.next_rank.name}
                  </span>
                </div>

                <div style={{
                  background: 'rgba(0,0,0,0.2)',
                  borderRadius: '8px',
                  height: '6px',
                  overflow: 'hidden',
                  marginTop: '8px'
                }}>
                  <div style={{
                    background: 'linear-gradient(90deg, #4ade80, #22c55e)',
                    height: '100%',
                    width: `${Math.min(100, (rankInfo.current_rank.current_subscription_days / rankInfo.next_rank.required_days) * 100)}%`,
                    transition: 'width 0.3s ease'
                  }} />
                </div>

                <div style={{
                  color: 'rgba(255,255,255,0.7)',
                  fontSize: '11px',
                  marginTop: '6px',
                  textAlign: 'center'
                }}>
                  Осталось {rankInfo.next_rank.required_days - rankInfo.current_rank.current_subscription_days} дней
                </div>
              </>
            )}
          </div>
        </div>
      )}

      <div className="subscription-container">
        {subscription?.has_subscription ? (
          <div className="subscription-card subscription-active">
            <div className="subscription-header">
              <h2 className="subscription-title">Активная подписка</h2>
              <span className="subscription-badge badge-active">✓ Активна</span>
            </div>
            <div className="subscription-info">
              <div><strong>Тариф:</strong> {subscription.subscription.tariff_name}</div>
              <div><strong>Начало:</strong> {new Date(subscription.subscription.start_date).toLocaleDateString('ru-RU')}</div>
              <div><strong>Окончание:</strong> {new Date(subscription.subscription.end_date).toLocaleDateString('ru-RU')}</div>
              <div><strong>Осталось дней:</strong> {subscription.subscription.days_left}</div>
            </div>
            <button
              className="cancel-subscription-btn"
              onClick={() => setShowCancelModal(true)}
              style={{
                marginTop: '15px',
                width: '100%',
                padding: '12px',
                background: '#ff4444',
                color: 'white',
                border: 'none',
                borderRadius: '12px',
                fontSize: '16px',
                fontWeight: 'bold',
                cursor: 'pointer'
              }}
            >
              ❌ Отменить подписку
            </button>
          </div>
        ) : (
          <div className="subscription-card subscription-inactive">
            <div className="subscription-header">
              <h2 className="subscription-title">Подписка не активна</h2>
              <span className="subscription-badge badge-inactive">✗ Неактивна</span>
            </div>
            <div className="subscription-info">
              <div>У вас нет активной подписки. Выберите тариф ниже для получения доступа к каналу и группам.</div>
            </div>
          </div>
        )}
      </div>

      <h2 style={{ color: 'rgba(255, 255, 255, 0.95)', marginTop: '30px', marginBottom: '15px', fontWeight: 'bold', textShadow: '0 2px 8px rgba(0, 0, 0, 0.4)' }}>Доступные тарифы</h2>

      <div className="tariffs-list">
        {tariffs.length > 0 ? (
          tariffs.map((tariff) => (
            <div key={tariff.id} className="tariff-card">
              <div className="tariff-name">{tariff.name}</div>
              {tariff.description && (
                <div className="tariff-description">{tariff.description}</div>
              )}
              <div className="tariff-price">
                ${parseFloat(tariff.price_usd).toFixed(2)}
              </div>
              {tariff.price_stars && (
                <div style={{ color: '#FFD700', fontSize: '14px', marginTop: '5px' }}>
                  или ⭐ {tariff.price_stars} Stars
                </div>
              )}
              <div style={{ color: '#666', fontSize: '14px', marginBottom: '15px' }}>
                Срок действия: {tariff.duration_days} дней
              </div>
              <button className="buy-btn" onClick={() => handleBuyTariff(tariff)}>
                Оплатить
              </button>
            </div>
          ))
        ) : (
          <div style={{ textAlign: 'center', padding: '40px', color: 'rgba(255, 255, 255, 0.95)', fontWeight: 'bold', textShadow: '0 2px 8px rgba(0, 0, 0, 0.4)' }}>
            📋 Нет доступных тарифов
          </div>
        )}
      </div>

      {/* Модальное окно подтверждения отмены */}
      {showCancelModal && (
        <div className="modal-overlay" onClick={() => setShowCancelModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title" style={{ color: '#ff4444' }}>⚠️ Отмена подписки</h2>

            <p style={{ color: '#ccc', marginBottom: '20px', textAlign: 'center' }}>
              Вы уверены, что хотите отменить подписку?<br/>
              <strong>Доступ к каналам и группам будет немедленно закрыт.</strong>
            </p>

            <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
              <button
                className="modal-close-btn"
                onClick={() => setShowCancelModal(false)}
                disabled={isCancelling}
                style={{ flex: 1 }}
              >
                Нет, оставить
              </button>
              <button
                onClick={handleCancelSubscription}
                disabled={isCancelling}
                style={{
                  flex: 1,
                  padding: '12px',
                  background: '#ff4444',
                  color: 'white',
                  border: 'none',
                  borderRadius: '12px',
                  fontSize: '16px',
                  fontWeight: 'bold',
                  cursor: isCancelling ? 'not-allowed' : 'pointer',
                  opacity: isCancelling ? 0.5 : 1
                }}
              >
                {isCancelling ? 'Отмена...' : 'Да, отменить'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно выбора способа оплаты */}
      {showPaymentModal && selectedTariff && paymentInfo && (
        <div className="modal-overlay" onClick={() => setShowPaymentModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">Выберите способ оплаты</h2>

            <div className="modal-tariff-info">
              <div className="modal-tariff-name">{selectedTariff.name}</div>
              <div className="modal-tariff-duration">{selectedTariff.duration_days} дней</div>
            </div>

            <div className="payment-methods">
              {paymentInfo.price_stars && (
                <button
                  className="payment-method-btn stars-btn"
                  onClick={() => handlePaymentMethod('stars')}
                >
                  <div className="payment-icon">⭐</div>
                  <div className="payment-name">Telegram Stars</div>
                  <div className="payment-price">{paymentInfo.price_stars} Stars</div>
                  <div className="payment-note">≈ ${parseFloat(paymentInfo.price_usd).toFixed(2)}</div>
                </button>
              )}

              <button
                className="payment-method-btn stripe-btn"
                onClick={() => handlePaymentMethod('stripe')}
              >
                <div className="payment-icon">💳</div>
                <div className="payment-name">Банковская карта</div>
                <div className="payment-price">${parseFloat(paymentInfo.price_usd).toFixed(2)}</div>
                <div className="payment-note">Visa, Mastercard, МИР</div>
              </button>
            </div>

            <button className="modal-close-btn" onClick={() => setShowPaymentModal(false)}>
              Закрыть
            </button>
          </div>
        </div>
      )}

      {/* Модальное окно со всеми званиями */}
      {showRanksModal && rankInfo?.all_ranks && (
        <div className="modal-overlay" onClick={() => setShowRanksModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
            <h2 className="modal-title">🏆 Система званий</h2>

            <p style={{ color: '#ccc', marginBottom: '20px', textAlign: 'center', fontSize: '14px' }}>
              Звания присваиваются автоматически в зависимости от общей продолжительности вашей подписки
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {rankInfo.all_ranks.map((rank) => {
                const isCurrentRank = rankInfo.current_rank?.id === rank.id;
                const isAchieved = rankInfo.current_rank &&
                  rankInfo.current_rank.current_subscription_days >= rank.required_days;

                return (
                  <div
                    key={rank.id}
                    style={{
                      background: isCurrentRank
                        ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                        : isAchieved
                        ? 'rgba(34, 197, 94, 0.15)'
                        : 'rgba(255,255,255,0.05)',
                      border: isCurrentRank ? '2px solid #fff' : '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '12px',
                      padding: '16px',
                      position: 'relative',
                      transition: 'all 0.3s ease'
                    }}
                  >
                    {isCurrentRank && (
                      <div style={{
                        position: 'absolute',
                        top: '8px',
                        right: '8px',
                        background: 'rgba(255,255,255,0.3)',
                        borderRadius: '6px',
                        padding: '4px 8px',
                        fontSize: '10px',
                        fontWeight: 'bold',
                        color: 'white'
                      }}>
                        ТЕКУЩЕЕ
                      </div>
                    )}

                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{
                        fontSize: '36px',
                        filter: !isAchieved ? 'grayscale(100%) opacity(0.4)' : 'none'
                      }}>
                        {rank.icon_emoji}
                      </span>

                      <div style={{ flex: 1 }}>
                        <h3 style={{
                          color: isCurrentRank ? 'white' : isAchieved ? '#4ade80' : '#999',
                          margin: 0,
                          fontSize: '18px',
                          fontWeight: 'bold'
                        }}>
                          {rank.name}
                        </h3>

                        <p style={{
                          color: isCurrentRank ? 'rgba(255,255,255,0.9)' : '#888',
                          margin: '4px 0 0 0',
                          fontSize: '13px'
                        }}>
                          {rank.description}
                        </p>

                        <div style={{
                          color: isCurrentRank ? 'rgba(255,255,255,0.8)' : '#666',
                          fontSize: '12px',
                          marginTop: '6px',
                          fontWeight: 'bold'
                        }}>
                          {rank.required_days === 0
                            ? '📌 Базовое звание'
                            : `📅 Требуется: ${rank.required_days} дней подписки`
                          }
                        </div>

                        {isAchieved && !isCurrentRank && (
                          <div style={{
                            color: '#4ade80',
                            fontSize: '12px',
                            marginTop: '4px',
                            fontWeight: 'bold'
                          }}>
                            ✓ Получено
                          </div>
                        )}

                        {!isAchieved && rankInfo.current_rank && (
                          <div style={{
                            color: '#888',
                            fontSize: '12px',
                            marginTop: '4px'
                          }}>
                            🔒 Осталось {rank.required_days - rankInfo.current_rank.current_subscription_days} дней
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <button
              className="modal-close-btn"
              onClick={() => setShowRanksModal(false)}
              style={{ marginTop: '20px' }}
            >
              Закрыть
            </button>
          </div>
        </div>
      )}
      <PrivacyButton />


      <div className="bottom-nav">
        <button className="nav-btn" onClick={() => onNavigate('channels')}>
          <span>📢</span>
          <span>Каналы</span>
        </button>
        <button className="nav-btn" onClick={() => onNavigate('catalog')}>
          <span>📋</span>
          <span>Каталог</span>
        </button>
        <button className="nav-btn active" onClick={() => onNavigate('subscription')}>
          <span>⭐</span>
          <span>Подписка</span>
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
