import './PrivacyButton.css';

export default function PrivacyButton() {
  const privacyUrl = import.meta.env.VITE_PRIVACY_POLICY_URL;

  // Если URL не задан, не показываем кнопку
  if (!privacyUrl || privacyUrl.trim() === '') {
    return null;
  }

  const handleClick = () => {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.openLink(privacyUrl);
    } else {
      window.open(privacyUrl, '_blank');
    }
  };

  return (
    <div className="privacy-button-container">
      <button className="privacy-button" onClick={handleClick}>
        <span className="privacy-icon">📄</span>
        <span className="privacy-text">Политика конфиденциальности и правила</span>
      </button>
    </div>
  );
}

