import PrivacyButton from '../components/PrivacyButton';

export default function Home({ onNavigate, user }) {
  const menuItems = [
    { title: 'Доступ к каналу', icon: '📢', page: 'channels' },
    { title: 'Доступ к группам', icon: '👥', page: 'channels' },
    { title: 'Справочный каталог', icon: '📋', page: 'catalog' },
    { title: 'Мои звания и подписки', icon: '⭐', page: 'subscription' }
  ];

  return (
    <div className="page">
      <h1 className="title">Главное меню</h1>

      {user && (
        <div className="user-info">
          <div>
            Привет, {user.first_name}! 👋
            {user.is_admin && <span className="admin-badge">АДМИН</span>}
          </div>
          {user.is_subscribed && user.subscription_end_date ? (
            <div style={{ fontSize: '14px', marginTop: '8px', color: '#4caf50', fontWeight: '500' }}>
               Подписка до: {new Date(user.subscription_end_date).toLocaleDateString('ru-RU')}
            </div>
          ) : (
            <div style={{ fontSize: '14px', marginTop: '8px', opacity: 0.9, color: '#ff9800' }}>
              🔒 Без подписки (только чтение в группах)
            </div>
          )}
        </div>
      )}

      <div className="menu">
        {menuItems.map((item, i) => (
          <button
            key={i}
            className="menu-btn"
            onClick={() => onNavigate(item.page)}
          >
            <span className="icon">{item.icon}</span>
            <span>{item.title}</span>
          </button>
        ))}
      </div>

      <PrivacyButton />
    </div>
  );
}
