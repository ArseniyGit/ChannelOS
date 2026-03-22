import { isTelegramMiniAppContext, redirectToTelegramBot } from '../utils/telegramAuth';

export default function PaymentCancel({ onNavigate }) {
  const handleBackToTariffs = () => {
    if (!isTelegramMiniAppContext() && redirectToTelegramBot('subscription')) {
      return;
    }
    onNavigate('subscription');
  };

  const handleGoHome = () => {
    if (!isTelegramMiniAppContext() && redirectToTelegramBot('home')) {
      return;
    }
    onNavigate('home');
  };

  return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
      <div style={{ fontSize: '64px', marginBottom: '20px' }}>❌</div>
      <h1 style={{ color: 'white', marginBottom: '10px' }}>Оплата отменена</h1>
      <p style={{ color: '#999', textAlign: 'center', marginBottom: '30px' }}>
        Вы отменили процесс оплаты.<br />
        Попробуйте еще раз, если хотите оформить подписку.
      </p>

      <button className="buy-btn" onClick={handleBackToTariffs} style={{ marginBottom: '15px' }}>
        {isTelegramMiniAppContext() ? 'Вернуться к тарифам' : 'Открыть в Telegram'}
      </button>

      <button
        className="buy-btn"
        onClick={handleGoHome}
        style={{ background: 'transparent', border: '1px solid #007BFF', color: '#007BFF' }}
      >
        {isTelegramMiniAppContext() ? 'На главную' : 'Открыть в Telegram'}
      </button>
    </div>
  );
}
