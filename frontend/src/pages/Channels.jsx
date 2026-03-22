import { useEffect, useState } from 'react';
import PrivacyButton from '../components/PrivacyButton';
import Notification from '../components/Notification';
import { useNotification } from '../hooks/useNotification';
import { buildAuthHeaders, getInitData } from '../utils/telegramAuth';

export default function Channels({ onNavigate, user }) {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState(user);
  const { notification, showNotification, hideNotification } = useNotification();

  useEffect(() => {
    const initData = getInitData();

    if (initData) {
      // Загружаем актуальную информацию о пользователе
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

      // Загружаем каналы
      fetch(`${import.meta.env.VITE_API_URL}/api/channels`, {
        headers: buildAuthHeaders()
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            setChannels(data.channels);
          }
        })
        .catch(err => {
          console.error('Error loading channels:', err);
        })
        .finally(() => {
          setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, []);

  const handleJoinChannel = (channel) => {
    if (channel.link) {
      window.Telegram?.WebApp?.openTelegramLink(channel.link);
    } else {
      showNotification('⚠️ Ссылка на канал не настроена', 'warning');
    }
  };

  if (loading) {
    return (
      <div className="page">
        <h1 className="title">Загрузка...</h1>
      </div>
    );
  }

  // ИСПРАВЛЕНИЕ: Проверяем подписку пользователя
  const hasActiveSubscription = currentUser?.is_subscribed || false;

  return (
    <div className="page">
      {/* Приветствие пользователя */}
      {currentUser && (
        <div className="user-info" style={{ marginBottom: '20px' }}>
          <div>
            Привет, {currentUser.first_name}! 👋
            {currentUser.is_admin && <span className="admin-badge">АДМИН</span>}
          </div>
          {currentUser.is_subscribed && currentUser.subscription_end_date ? (
            <div style={{ fontSize: '14px', marginTop: '8px', color: '#4caf50', fontWeight: '500' }}>
              Подписка до: {new Date(currentUser.subscription_end_date).toLocaleDateString('ru-RU')}
            </div>
          ) : (
            <div style={{ fontSize: '14px', marginTop: '8px', opacity: 0.9, color: '#ff9800' }}>
              ⚠️ Нет активной подписки
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: '20px', gap: '15px', width: '100%' }}>
        <h1 className="title" style={{ margin: 0 }}>Каналы и группы</h1>
        <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', flexWrap: 'wrap', width: '100%' }}>
          <button
            onClick={() => onNavigate('my-advertisements')}
            className="access-btn"
            style={{ width: 'auto', minWidth: '140px' }}
          >
            <span>📋</span>
            <span>Мои рекламы</span>
          </button>
          <button
            onClick={() => onNavigate('submit-advertisement')}
            className="access-btn"
            style={{ width: 'auto', minWidth: '140px', backgroundColor: '#28a745' }}
          >
            <span>📢</span>
            <span>Подать рекламу</span>
          </button>
        </div>
      </div>

      <div className="channels-list" style={{ alignItems: 'center' }}>
        {channels.map((channel) => (
          <div key={channel.id} className="channel-card" style={{ maxWidth: '600px', margin: '0 auto' }}>
            <div className="channel-info">
              <div className="channel-icon">{channel.icon}</div>
              <div className="channel-details">
                <h3>{channel.name}</h3>
                {channel.type === 'channel' ? (
                  <span className="channel-status status-inactive">
                    👁 Только чтение
                  </span>
                ) : channel.paid_mode_enabled ? (
                  hasActiveSubscription ? (
                    <span className="channel-status status-active">
                      ✓ Полный доступ
                    </span>
                  ) : (
                    <span className="channel-status status-inactive">
                      ✍️ Базовый доступ
                    </span>
                  )
                ) : (
                  <span className="channel-status status-active">
                    🆓 Свободный доступ
                  </span>
                )}
              </div>
            </div>

            <button className="access-btn" onClick={() => handleJoinChannel(channel)}>
              Перейти
            </button>
          </div>
        ))}
      </div>

      {/* ИСПРАВЛЕНИЕ: Показываем блок ТОЛЬКО если НЕТ подписки */}
      {!hasActiveSubscription && (
        <div style={{
          marginTop: '20px',
          padding: '20px',
          background: 'rgba(255, 255, 255, 0.95)',
          border: '2px solid #ff9800',
          borderRadius: '12px',
          textAlign: 'center',
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)'
        }}>
          <div style={{ fontSize: '32px', marginBottom: '10px' }}>🔒</div>
          <div style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '8px', color: '#ff9800' }}>
            Ограниченный доступ
          </div>
          <div style={{ fontSize: '14px', color: '#1e3a5f', marginBottom: '15px', fontWeight: '500' }}>
            В каналах доступ остаётся только на чтение. В группах с платным режимом без подписки доступен только <strong>базовый режим</strong>: текстовые сообщения и приглашение пользователей.
          </div>
          <div style={{ fontSize: '14px', color: '#2e7d32', fontWeight: '500' }}>
            💡 Оформите подписку для полного доступа: написание сообщений, отправка медиа, участие в обсуждениях.
          </div>
          <button
            className="buy-btn"
            onClick={() => onNavigate('subscription')}
            style={{ marginTop: '15px' }}
          >
            Оформить подписку
          </button>
        </div>
      )}

      {/* Кнопка политики конфиденциальности */}
      <PrivacyButton />


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

      {/* Уведомления */}
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
