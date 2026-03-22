import { useEffect, useRef, useState } from 'react';
import {
  buildAuthHeaders,
  getInitData,
  isTelegramMiniAppContext,
  redirectToTelegramBot,
} from '../utils/telegramAuth';

export default function PaymentSuccess({ onNavigate, refreshUser }) {
  const [isVerifying, setIsVerifying] = useState(true);
  const [error, setError] = useState(null);
  const [subscriptionInfo, setSubscriptionInfo] = useState(null);
  const [isAdvertisement, setIsAdvertisement] = useState(false);
  const [adRequiresModeration, setAdRequiresModeration] = useState(false);
  const [adPublished, setAdPublished] = useState(false);
  const hasVerifiedRef = useRef(false);

  useEffect(() => {
    if (hasVerifiedRef.current) {
      return;
    }
    hasVerifiedRef.current = true;

    const verifyPayment = async () => {
      try {
        const urlParams = new URLSearchParams(window.location.search);
        let sessionId = urlParams.get('session_id');
        const verifyToken = urlParams.get('vt');
        
        // Если session_id нет в URL, пытаемся получить из localStorage
        if (!sessionId) {
          sessionId = localStorage.getItem('pending_stripe_session');
          if (sessionId) {
            localStorage.removeItem('pending_stripe_session');
            console.log('Используем session_id из localStorage:', sessionId);
          }
        }
        
        if (!sessionId) {
          setError('Отсутствует session_id. Пожалуйста, проверьте URL или обратитесь в поддержку.');
          setIsVerifying(false);
          return;
        }

        console.log('Проверка платежа для session_id:', sessionId);

        const initData = getInitData();

        const verifyUrl = new URL(`${import.meta.env.VITE_API_URL}/api/verify-payment/${sessionId}`);
        if (verifyToken) {
          verifyUrl.searchParams.set('vt', verifyToken);
        } else if (!initData) {
          // Backward-compatible verification path for old Stripe sessions
          // that don't include verify-token in success URL.
          verifyUrl.searchParams.set('legacy', '1');
        }

        // Вызываем API для проверки и активации подписки
        const response = await fetch(verifyUrl.toString(), {
          method: 'GET',
          headers: buildAuthHeaders({ 'Content-Type': 'application/json' })
        });

        const data = await response.json();
        console.log('Результат проверки:', data);

        if (data.success) {
          console.log('✅ Платеж успешно обработан!', data);
          localStorage.removeItem('pending_stripe_session');
          setSubscriptionInfo(data.subscription);
          setIsAdvertisement(data.is_advertisement || false);
          if (data.is_advertisement) {
            setAdRequiresModeration(Boolean(data.requires_moderation));
            setAdPublished(Boolean(data.is_published));
          }

          // Обновляем данные пользователя в App
          if (refreshUser) {
            await refreshUser();
          }
        } else {
          setError(data.detail || 'Не удалось обработать платеж');
        }
      } catch (err) {
        console.error('❌ Ошибка проверки платежа:', err);
        setError('Ошибка при проверке платежа');
      } finally {
        setIsVerifying(false);
      }
    };

    verifyPayment();
  }, [refreshUser]);

  const handleNavigateHome = () => {
    if (!isTelegramMiniAppContext() && redirectToTelegramBot('home')) {
      return;
    }
    onNavigate('home');
  };

  const handleNavigateChannels = () => {
    if (!isTelegramMiniAppContext() && redirectToTelegramBot('channels')) {
      return;
    }
    onNavigate('channels');
  };

  const handleNavigateSecondary = () => {
    if (isAdvertisement) {
      if (!isTelegramMiniAppContext() && redirectToTelegramBot('my_advertisements')) {
        return;
      }
      onNavigate('my-advertisements');
      return;
    }

    if (!isTelegramMiniAppContext() && redirectToTelegramBot('subscription')) {
      return;
    }
    onNavigate('subscription');
  };

  return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
      {isVerifying ? (
        <>
          <div style={{ fontSize: '48px', marginBottom: '20px' }}>⏳</div>
          <h1 style={{ color: 'white', marginBottom: '10px' }}>Проверка платежа...</h1>
          <p style={{ color: '#999', textAlign: 'center', marginBottom: '30px' }}>
            Пожалуйста, подождите
          </p>
        </>
      ) : error ? (
        <>
          <div style={{ fontSize: '64px', marginBottom: '20px' }}>⚠️</div>
          <h1 style={{ color: 'white', marginBottom: '10px' }}>Внимание</h1>
          <p style={{ color: '#999', textAlign: 'center', marginBottom: '30px' }}>
            {error}<br />
            Попробуйте обновить страницу или обратитесь в поддержку.
          </p>
          <button className="buy-btn" onClick={handleNavigateHome}>
            {isTelegramMiniAppContext() ? 'На главную' : 'Открыть в Telegram'}
          </button>
        </>
      ) : (
        <>
          <div style={{ fontSize: '64px', marginBottom: '20px' }}>✅</div>
          <h1 style={{ color: 'white', marginBottom: '10px' }}>Оплата успешна!</h1>

          {subscriptionInfo && (
            <div style={{
              background: 'rgba(255, 255, 255, 0.1)',
              padding: '20px',
              borderRadius: '15px',
              marginBottom: '20px',
              width: '90%',
              maxWidth: '400px'
            }}>
              <div style={{ color: '#4CAF50', fontSize: '18px', fontWeight: 'bold', marginBottom: '10px' }}>
                🎉 {subscriptionInfo.tariff_name}
              </div>
              {subscriptionInfo.end_date && (
                <div style={{ color: '#999', fontSize: '14px', marginBottom: '5px' }}>
                  📅 Действует до: {new Date(subscriptionInfo.end_date).toLocaleDateString('ru-RU', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                  })}
                </div>
              )}
              {subscriptionInfo.amount && (
                <div style={{ color: '#999', fontSize: '14px' }}>
                  💰 Оплачено: ${parseFloat(subscriptionInfo.amount).toFixed(2)}
                </div>
              )}
            </div>
          )}

          <p style={{ color: '#999', textAlign: 'center', marginBottom: '30px' }}>
            {isAdvertisement ? (
              <>
                ✅ Спасибо за оплату!<br />
                Ваша реклама оплачена.<br />
                {adPublished
                  ? 'Реклама уже опубликована.'
                  : adRequiresModeration
                    ? 'Объявление отправлено на модерацию. Публикация будет выполнена после одобрения администратором.'
                    : 'Публикация будет выполнена администратором после проверки.'}
              </>
            ) : (
              <>
                Спасибо за покупку!<br />
                Ваша подписка активирована.<br />
                Теперь у вас есть полный доступ к каналу и группам!
              </>
            )}
          </p>

          <button className="buy-btn" onClick={handleNavigateChannels} style={{ marginBottom: '15px' }}>
            {isAdvertisement ? 'Перейти к каналам' : 'Перейти к каналам'}
          </button>

          {isAdvertisement ? (
            <button
              className="buy-btn"
              onClick={handleNavigateSecondary}
              style={{ background: 'transparent', border: '1px solid #007BFF', color: '#007BFF', marginBottom: '15px' }}
            >
              Мои рекламы
            </button>
          ) : (
            <button
              className="buy-btn"
              onClick={handleNavigateSecondary}
              style={{ background: 'transparent', border: '1px solid #007BFF', color: '#007BFF', marginBottom: '15px' }}
            >
              Мои подписки
            </button>
          )}

          <button
            className="buy-btn"
            onClick={handleNavigateHome}
            style={{ background: 'transparent', border: '1px solid #666', color: '#999' }}
          >
            {isTelegramMiniAppContext() ? 'На главную' : 'Открыть в Telegram'}
          </button>
        </>
      )}
    </div>
  );
}
