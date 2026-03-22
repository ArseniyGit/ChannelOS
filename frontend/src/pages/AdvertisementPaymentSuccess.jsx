import { useEffect, useRef, useState } from 'react';
import {
  buildAuthHeaders,
  getInitData,
  isTelegramMiniAppContext,
  redirectToTelegramBot,
} from '../utils/telegramAuth';

export default function AdvertisementPaymentSuccess({ onNavigate, refreshUser }) {
  const [isVerifying, setIsVerifying] = useState(true);
  const [error, setError] = useState(null);
  const [advertisementInfo, setAdvertisementInfo] = useState(null);
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

        console.log('Проверка платежа рекламы для session_id:', sessionId);

        const initData = getInitData();

        const verifyUrl = new URL(`${import.meta.env.VITE_API_URL}/api/verify-payment/${sessionId}`);
        if (verifyToken) {
          verifyUrl.searchParams.set('vt', verifyToken);
        } else if (!initData) {
          // Backward-compatible verification path for old Stripe sessions
          // that don't include verify-token in success URL.
          verifyUrl.searchParams.set('legacy', '1');
        }

        // Вызываем API для проверки и активации оплаты рекламы
        const response = await fetch(verifyUrl.toString(), {
          method: 'GET',
          headers: buildAuthHeaders({ 'Content-Type': 'application/json' })
        });

        const data = await response.json();
        console.log('Результат проверки:', data);

        if (data.success) {
          console.log('✅ Оплата рекламы успешно обработана!', data);
          localStorage.removeItem('pending_stripe_session');
          setAdvertisementInfo(data);

          // Обновляем данные пользователя
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

  const handleGoToMyAdvertisements = () => {
    if (!isTelegramMiniAppContext() && redirectToTelegramBot('my_advertisements')) {
      return;
    }
    onNavigate('my-advertisements');
  };

  const handleGoHome = () => {
    if (!isTelegramMiniAppContext() && redirectToTelegramBot('home')) {
      return;
    }
    onNavigate('channels');
  };

  return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', padding: '20px' }}>
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
          <button className="buy-btn" onClick={handleGoToMyAdvertisements}>
            {isTelegramMiniAppContext() ? 'Мои объявления' : 'Открыть в Telegram'}
          </button>
        </>
      ) : (
        <>
          <div style={{ fontSize: '64px', marginBottom: '20px' }}>✅</div>
          <h1 style={{ color: 'white', marginBottom: '10px' }}>Реклама оплачена!</h1>

          {advertisementInfo && (
            <div style={{
              background: 'rgba(255, 255, 255, 0.1)',
              padding: '20px',
              borderRadius: '15px',
              marginBottom: '20px',
              width: '90%',
              maxWidth: '400px'
            }}>
              <div style={{ color: '#4CAF50', fontSize: '18px', fontWeight: 'bold', marginBottom: '10px' }}>
                🎉 Оплата успешна!
              </div>
              {advertisementInfo.amount && (
                <div style={{ color: '#999', fontSize: '14px' }}>
                  💰 Оплачено: ${parseFloat(advertisementInfo.amount).toFixed(2)}
                </div>
              )}
            </div>
          )}

          <p style={{ color: '#999', textAlign: 'center', marginBottom: '30px' }}>
            ✅ Спасибо за оплату!<br />
            Ваша реклама оплачена.<br />
            {advertisementInfo?.is_published
              ? 'Реклама уже опубликована.'
              : advertisementInfo?.requires_moderation
                ? 'Объявление отправлено на модерацию. Публикация произойдет после одобрения.'
                : 'Публикация будет выполнена администратором после проверки.'}
          </p>

          <button
            className="buy-btn"
            onClick={handleGoToMyAdvertisements}
            style={{ marginBottom: '15px' }}
          >
            {isTelegramMiniAppContext() ? 'Мои объявления' : 'Открыть в Telegram'}
          </button>

          <button
            className="buy-btn"
            onClick={handleGoHome}
            style={{ background: 'transparent', border: '1px solid #007BFF', color: '#007BFF' }}
          >
            {isTelegramMiniAppContext() ? 'На главную' : 'Открыть в Telegram'}
          </button>
        </>
      )}
    </div>
  );
}
