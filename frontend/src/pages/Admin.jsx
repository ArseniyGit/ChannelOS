import { useEffect, useState } from 'react';
import '../styles/Admin.css';
import Notification from '../components/Notification';
import { useNotification } from '../hooks/useNotification';
import { buildAuthHeaders } from '../utils/telegramAuth';
import { resolveMediaUrl, splitMediaUrls } from '../utils/mediaUrl';

const getPageTitle = (tab) => {
  const titles = {
    'users': 'Пользователи',
    'tariffs': 'Подписки и тарифы',
    'channels': 'Каналы и группы',
    'ad-tariffs': 'Тарифы рекламы',
    'companies': 'Справочный каталог',
    'ranks': 'Пользовательские звания',
    'advertisements': 'Реклама',
    'stats': 'Логи и статистика',
    'payments': 'Платежи'
  };
  return titles[tab] || 'Админ-панель';
};

export default function Admin({ onNavigate }) {
  const [activeTab, setActiveTab] = useState('users');
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [ranks, setRanks] = useState([]);
  const [tariffs, setTariffs] = useState([]);
  const [channels, setChannels] = useState([]);
  const [adTariffs, setAdTariffs] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [advertisements, setAdvertisements] = useState([]);
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showRankModal, setShowRankModal] = useState(false);
  const [showTariffModal, setShowTariffModal] = useState(false);
  const [showChannelModal, setShowChannelModal] = useState(false);
  const [showAdTariffModal, setShowAdTariffModal] = useState(false);
  const [showCompanyModal, setShowCompanyModal] = useState(false);
  const [showAdvertisementModal, setShowAdvertisementModal] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const { notification, showNotification, hideNotification } = useNotification();

  const getAuthHeaders = () => {
    return buildAuthHeaders();
  };

  const readJsonSafe = async (response) => {
    const raw = await response.text();
    if (!raw) return {};
    try {
      return JSON.parse(raw);
    } catch {
      return { detail: raw.slice(0, 300) };
    }
  };

  const buildErrorMessage = (response, data, fallback) => {
    if (typeof data?.detail === 'string' && data.detail.trim()) return data.detail;
    if (typeof data?.message === 'string' && data.message.trim()) return data.message;
    if (typeof data?.error === 'string' && data.error.trim()) return data.error;
    if (response) return `${fallback} (HTTP ${response.status})`;
    return fallback;
  };

  const normalizeNetworkError = (err, fallback) => {
    const message = String(err?.message || '');
    if (!message) return fallback;
    if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
      return 'Сеть/туннель недоступен. Проверьте cloudflared и backend.';
    }
    return message;
  };

  useEffect(() => {
    loadData();
    // loadData is intentionally recreated with activeTab-bound handlers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      switch (activeTab) {
        case 'stats':
          await loadStats();
          break;
        case 'users':
          await loadUsers();
          break;
        case 'tariffs':
          await loadTariffs();
          break;
        case 'channels':
          await loadChannels();
          break;
        case 'ad-tariffs':
          await Promise.all([loadAdTariffs(), loadChannels()]);
          break;
        case 'companies':
          await loadCompanies();
          break;
        case 'ranks':
          await loadRanks();
          break;
        case 'advertisements':
          await Promise.all([loadAdvertisements(), loadChannels()]);
          break;
        case 'payments':
          await loadPayments();
          break;
      }
    } catch (err) {
      console.error('Error loading data:', err);
    }
    setLoading(false);
  };

  const loadStats = async () => {
    const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/stats`, {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (data.success) {
      setStats(data.stats);
    }
  };

  const loadUsers = async () => {
    const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/users`, {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (data.success) {
      setUsers(data.users);
    }
  };

  const loadTariffs = async () => {
    const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/tariffs`, {
      headers: getAuthHeaders()
    });
    const data = await readJsonSafe(response);
    if (response.ok && data.success) {
      setTariffs(data.tariffs);
    } else {
      setTariffs([]);
    }
  };

  const loadChannels = async () => {
    const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/channels`, {
      headers: getAuthHeaders()
    });
    const data = await readJsonSafe(response);
    if (response.ok && data.success) {
      setChannels(data.channels);
    } else {
      setChannels([]);
    }
  };

  const loadAdTariffs = async () => {
    const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/advertisement-tariffs`, {
      headers: getAuthHeaders()
    });
    const data = await readJsonSafe(response);
    if (response.ok && data.success) {
      setAdTariffs(data.tariffs);
    } else {
      setAdTariffs([]);
    }
  };

  const loadCompanies = async () => {
    const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/companies`, {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (data.success) {
      setCompanies(data.companies);
    }
  };

  const loadPayments = async () => {
    const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/payments`, {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (data.success) {
      setPayments(data.payments);
    }
  };


  const loadRanks = async () => {
    const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/ranks`, {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (data.success) {
      setRanks(data.ranks);
    }
  };

  const loadAdvertisements = async () => {
    const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/advertisements`, {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (data.success) {
      setAdvertisements(data.advertisements);
    }
  };


  const handleCreateTariff = () => {
    setEditingItem(null);
    setShowTariffModal(true);
  };

  const handleEditTariff = (tariff) => {
    setEditingItem(tariff);
    setShowTariffModal(true);
  };

  const handleSaveTariff = async (tariffData) => {
    try {
      const url = editingItem
        ? `${import.meta.env.VITE_API_URL}/api/admin/tariffs/${editingItem.id}`
        : `${import.meta.env.VITE_API_URL}/api/admin/tariffs`;

      const method = editingItem ? 'PATCH' : 'POST';
      const action = editingItem ? 'изменён' : 'добавлен';

      const response = await fetch(url, {
        method,
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(tariffData)
      });

      const data = await readJsonSafe(response);
      if (response.ok && data.success) {
        showNotification(`🎉 Тариф успешно ${action}!`, 'success');
        setShowTariffModal(false);
        loadTariffs();
      } else {
        showNotification(buildErrorMessage(response, data, 'Ошибка при сохранении тарифа'), 'error');
      }
    } catch (err) {
      console.error('Error saving tariff:', err);
      showNotification(`❌ ${normalizeNetworkError(err, 'Ошибка при сохранении тарифа')}`, 'error');
    }
  };

  const handleDeleteTariff = async (tariffId) => {
    if (!window.confirm('Вы уверены? Тариф будет удалён навсегда!')) return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/tariffs/${tariffId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      const data = await readJsonSafe(response);
      
      if (response.ok && data.success) {
        showNotification('🗑️ Тариф успешно удалён!', 'success');
        loadTariffs();
      } else {
        showNotification(buildErrorMessage(response, data, 'Ошибка при удалении тарифа'), 'error');
      }
    } catch (err) {
      console.error('Error deleting tariff:', err);
      showNotification(`❌ ${normalizeNetworkError(err, 'Ошибка при удалении тарифа')}`, 'error');
    }
  };

  const handleCreateChannel = () => {
    setEditingItem(null);
    setShowChannelModal(true);
  };

  const handleEditChannel = (channel) => {
    setEditingItem(channel);
    setShowChannelModal(true);
  };

  const handleSaveChannel = async (channelData) => {
    try {
      const url = editingItem
        ? `${import.meta.env.VITE_API_URL}/api/admin/channels/${editingItem.id}`
        : `${import.meta.env.VITE_API_URL}/api/admin/channels`;
      const method = editingItem ? 'PATCH' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(channelData)
      });

      const data = await readJsonSafe(response);
      if (response.ok && data.success) {
        showNotification(`✅ Канал/группа ${editingItem ? 'обновлен' : 'добавлен'}!`, 'success');
        setShowChannelModal(false);
        loadChannels();
      } else {
        showNotification(buildErrorMessage(response, data, 'Ошибка при сохранении канала/группы'), 'error');
      }
    } catch (err) {
      console.error('Error saving channel:', err);
      showNotification(`❌ ${normalizeNetworkError(err, 'Ошибка при сохранении канала/группы')}`, 'error');
    }
  };

  const handleDeleteChannel = async (channelId) => {
    if (!window.confirm('Удалить этот канал/группу?')) return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/channels/${channelId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      const data = await readJsonSafe(response);

      if (response.ok && data.success) {
        showNotification('🗑️ Канал/группа удален', 'success');
        loadChannels();
      } else {
        showNotification(buildErrorMessage(response, data, 'Ошибка при удалении канала/группы'), 'error');
      }
    } catch (err) {
      console.error('Error deleting channel:', err);
      showNotification(`❌ ${normalizeNetworkError(err, 'Ошибка при удалении канала/группы')}`, 'error');
    }
  };

  const handleToggleChannelPaidMode = async (channel) => {
    if (channel.type !== 'group') return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/channels/${channel.id}`, {
        method: 'PATCH',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          paid_mode_enabled: !channel.paid_mode_enabled
        })
      });

      const data = await readJsonSafe(response);
      if (response.ok && data.success) {
        showNotification(
          data.channel?.paid_mode_enabled
            ? '💳 Платный режим включен'
            : '🆓 Платный режим выключен',
          'success'
        );
        loadChannels();
      } else {
        showNotification(buildErrorMessage(response, data, 'Ошибка при переключении платного режима'), 'error');
      }
    } catch (err) {
      console.error('Error toggling channel paid mode:', err);
      showNotification(`❌ ${normalizeNetworkError(err, 'Ошибка при переключении платного режима')}`, 'error');
    }
  };

  // Обработчики для тарифов рекламы
  const handleCreateAdTariff = () => {
    if (channels.length === 0) {
      showNotification('Сначала добавьте хотя бы один канал/группу', 'warning');
      return;
    }
    setEditingItem(null);
    setShowAdTariffModal(true);
  };

  const handleEditAdTariff = (tariff) => {
    setEditingItem(tariff);
    setShowAdTariffModal(true);
  };

  const handleSaveAdTariff = async (tariffData) => {
    try {
      const url = editingItem
        ? `${import.meta.env.VITE_API_URL}/api/admin/advertisement-tariffs/${editingItem.id}`
        : `${import.meta.env.VITE_API_URL}/api/admin/advertisement-tariffs`;

      const method = editingItem ? 'PATCH' : 'POST';
      const action = editingItem ? 'изменён' : 'добавлен';

      const response = await fetch(url, {
        method,
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(tariffData)
      });

      const data = await readJsonSafe(response);
      if (response.ok && data.success) {
        showNotification(`🎉 Тариф рекламы успешно ${action}!`, 'success');
        setShowAdTariffModal(false);
        loadAdTariffs();
      } else {
        showNotification(buildErrorMessage(response, data, 'Ошибка при сохранении тарифа рекламы'), 'error');
      }
    } catch (err) {
      console.error('Error saving ad tariff:', err);
      showNotification(`❌ ${normalizeNetworkError(err, 'Ошибка при сохранении тарифа рекламы')}`, 'error');
    }
  };

  const handleDeleteAdTariff = async (tariffId) => {
    if (!window.confirm('Вы уверены? Тариф рекламы будет удалён навсегда!')) return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/advertisement-tariffs/${tariffId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      const data = await readJsonSafe(response);

      if (response.ok && data.success) {
        showNotification('🗑️ Тариф рекламы успешно удалён!', 'success');
        loadAdTariffs();
      } else {
        showNotification(buildErrorMessage(response, data, 'Ошибка при удалении тарифа рекламы'), 'error');
      }
    } catch (err) {
      console.error('Error deleting ad tariff:', err);
      showNotification(`❌ ${normalizeNetworkError(err, 'Ошибка при удалении тарифа рекламы')}`, 'error');
    }
  };

  const handleCreateCompany = () => {
    setEditingItem(null);
    setShowCompanyModal(true);
  };

  const handleEditCompany = (company) => {
    setEditingItem(company);
    setShowCompanyModal(true);
  };

  const handleSaveCompany = async (companyData) => {
    try {
      const url = editingItem
        ? `${import.meta.env.VITE_API_URL}/api/admin/companies/${editingItem.id}`
        : `${import.meta.env.VITE_API_URL}/api/admin/companies`;

      const method = editingItem ? 'PATCH' : 'POST';
      const action = editingItem ? 'изменена' : 'добавлена';

      const response = await fetch(url, {
        method,
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(companyData)
      });

      const data = await response.json();
      if (data.success) {
        showNotification(`🎉 Компания успешно ${action}!`, 'success');
        setShowCompanyModal(false);
        loadCompanies();
      }
    } catch (err) {
      console.error('Error saving company:', err);
      showNotification('❌ Ошибка при сохранении компании', 'error');
    }
  };

  const handleDeleteCompany = async (companyId) => {
    if (!window.confirm('Удалить эту компанию?')) return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/companies/${companyId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      const data = await response.json();
      if (data.success) {
        showNotification('🗑️ Компания успешно удалена!', 'success');
        loadCompanies();
      }
    } catch (err) {
      console.error('Error deleting company:', err);
      showNotification('❌ Ошибка при удалении компании', 'error');
    }
  };

  // Handlers для Advertisements
  const handleCreateAdvertisement = () => {
    setEditingItem(null);
    setShowAdvertisementModal(true);
  };

  const handleEditAdvertisement = (ad) => {
    setEditingItem(ad);
    setShowAdvertisementModal(true);
  };

  const handleSaveAdvertisement = async (adData) => {
    try {
      const url = editingItem
        ? `${import.meta.env.VITE_API_URL}/api/admin/advertisements/${editingItem.id}`
        : `${import.meta.env.VITE_API_URL}/api/admin/advertisements`;

      const method = editingItem ? 'PATCH' : 'POST';
      const action = editingItem ? 'обновлена' : 'создана';

      const response = await fetch(url, {
        method,
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(adData)
      });

      const data = await readJsonSafe(response);
      if (response.ok && data.success) {
        showNotification(`✅ Реклама успешно ${action}!`, 'success');
        setShowAdvertisementModal(false);
        loadAdvertisements();
      } else {
        showNotification(buildErrorMessage(response, data, 'Ошибка при сохранении рекламы'), 'error');
      }
    } catch (err) {
      console.error('Error saving advertisement:', err);
      showNotification(`❌ ${normalizeNetworkError(err, 'Ошибка при сохранении рекламы')}`, 'error');
    }
  };

  const handleDeleteAdvertisement = async (adId) => {
    if (!window.confirm('Удалить эту рекламу?')) return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/advertisements/${adId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      const data = await readJsonSafe(response);
      if (response.ok && data.success) {
        showNotification('🗑️ Реклама успешно удалена!', 'success');
        loadAdvertisements();
      } else {
        showNotification(buildErrorMessage(response, data, 'Ошибка при удалении рекламы'), 'error');
      }
    } catch (err) {
      console.error('Error deleting advertisement:', err);
      showNotification(`❌ ${normalizeNetworkError(err, 'Ошибка при удалении рекламы')}`, 'error');
    }
  };

  const handlePublishAdvertisement = async (adId) => {
    if (!window.confirm('Опубликовать эту рекламу?')) return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/advertisements/${adId}/publish`, {
        method: 'POST',
        headers: getAuthHeaders()
      });

      const data = await readJsonSafe(response);
      if (response.ok && data.success) {
        showNotification('🚀 Реклама успешно опубликована!', 'success');
        loadAdvertisements();
      } else {
        showNotification(buildErrorMessage(response, data, 'Ошибка при публикации рекламы'), 'error');
      }
    } catch (err) {
      console.error('Error publishing advertisement:', err);
      showNotification(`❌ ${normalizeNetworkError(err, 'Ошибка при публикации рекламы')}`, 'error');
    }
  };


  // Handlers для Ranks
  const handleCreateRank = () => {
    setEditingItem(null);
    setShowRankModal(true);
  };

  const handleEditRank = (rank) => {
    setEditingItem(rank);
    setShowRankModal(true);
  };

  const handleSaveRank = async (rankData) => {
    try {
      const url = editingItem
        ? `${import.meta.env.VITE_API_URL}/api/admin/ranks/${editingItem.id}`
        : `${import.meta.env.VITE_API_URL}/api/admin/ranks`;

      const method = editingItem ? 'PATCH' : 'POST';
      const action = editingItem ? 'изменено' : 'добавлено';

      const response = await fetch(url, {
        method,
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(rankData)
      });

      const data = await response.json();
      if (data.success) {
        showNotification(`🎉 Звание успешно ${action}!`, 'success');
        setShowRankModal(false);
        loadRanks();
      }
    } catch (err) {
      console.error('Error saving rank:', err);
      showNotification('❌ Ошибка при сохранении звания', 'error');
    }
  };

  const handleDeleteRank = async (rankId) => {
    if (!window.confirm('Удалить это звание?')) return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/admin/ranks/${rankId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      const data = await response.json();
      if (data.success) {
        showNotification('🗑️ Звание успешно удалено!', 'success');
        loadRanks();
      } else {
        showNotification(data.detail || 'Ошибка при удалении', 'error');
      }
    } catch (err) {
      console.error('Error deleting rank:', err);
      showNotification('❌ Ошибка при удалении звания', 'error');
    }
  };

  return (
    <div className="admin-page">
      {/* Боковая панель (Sidebar) */}
      <aside className="admin-sidebar">
        <div className="admin-logo">🔧 Админ-панель</div>

        <button
          className={`sidebar-item ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          <span>👥</span>
          <span>Пользователи</span>
        </button>

        <button
          className={`sidebar-item ${activeTab === 'tariffs' ? 'active' : ''}`}
          onClick={() => setActiveTab('tariffs')}
        >
          <span>💰</span>
          <span>Подписки и тарифы</span>
        </button>

        <button
          className={`sidebar-item ${activeTab === 'channels' ? 'active' : ''}`}
          onClick={() => setActiveTab('channels')}
        >
          <span>📢</span>
          <span>Каналы и группы</span>
        </button>

        <button
          className={`sidebar-item ${activeTab === 'ad-tariffs' ? 'active' : ''}`}
          onClick={() => setActiveTab('ad-tariffs')}
        >
          <span>📊</span>
          <span>Тарифы рекламы</span>
        </button>

        <button
          className={`sidebar-item ${activeTab === 'companies' ? 'active' : ''}`}
          onClick={() => setActiveTab('companies')}
        >
          <span>🏢</span>
          <span>Справочный каталог</span>
        </button>

        <button
          className={`sidebar-item ${activeTab === 'ranks' ? 'active' : ''}`}
          onClick={() => setActiveTab('ranks')}
        >
          <span>🏆</span>
          <span>Пользовательские звания</span>
        </button>

        <button
          className={`sidebar-item ${activeTab === 'advertisements' ? 'active' : ''}`}
          onClick={() => setActiveTab('advertisements')}
        >
          <span>📢</span>
          <span>Реклама</span>
        </button>

        <button
          className={`sidebar-item ${activeTab === 'stats' ? 'active' : ''}`}
          onClick={() => setActiveTab('stats')}
        >
          <span>📊</span>
          <span>Логи и статистика</span>
        </button>

        <button
          className={`sidebar-item ${activeTab === 'payments' ? 'active' : ''}`}
          onClick={() => setActiveTab('payments')}
        >
          <span>💳</span>
          <span>Платежи</span>
        </button>

        <button className="sidebar-item sidebar-back" onClick={() => onNavigate('channels')}>
          <span>←</span>
          <span>Назад</span>
        </button>
      </aside>

      {/* Основной контент */}
      <main className="admin-main">
        <div className="admin-header">
          <h1>{getPageTitle(activeTab)}</h1>
        </div>

        <div className="admin-content">
          {loading ? (
            <div className="loading">
              <div className="loading-spinner"></div>
              <div>Загрузка данных...</div>
            </div>
          ) : (
            <>
              {activeTab === 'stats' && stats && (
                <StatsView stats={stats} onNavigate={setActiveTab} />
              )}
              {activeTab === 'users' && (
                <UsersView users={users} />
              )}
              {activeTab === 'tariffs' && (
                <TariffsView
                  tariffs={tariffs}
                  onEdit={handleEditTariff}
                  onDelete={handleDeleteTariff}
                  onCreate={handleCreateTariff}
                />
              )}
              {activeTab === 'channels' && (
                <ChannelsView
                  channels={channels}
                  onEdit={handleEditChannel}
                  onDelete={handleDeleteChannel}
                  onCreate={handleCreateChannel}
                  onTogglePaidMode={handleToggleChannelPaidMode}
                />
              )}
              {activeTab === 'ad-tariffs' && (
                <AdTariffsView
                  tariffs={adTariffs}
                  channels={channels}
                  onEdit={handleEditAdTariff}
                  onDelete={handleDeleteAdTariff}
                  onCreate={handleCreateAdTariff}
                />
              )}
              {activeTab === 'companies' && (
                <CompaniesView
                  companies={companies}
                  onEdit={handleEditCompany}
                  onDelete={handleDeleteCompany}
                  onCreate={handleCreateCompany}
                />
              )}
              {activeTab === 'ranks' && (
                <RanksView
                  ranks={ranks}
                  onEdit={handleEditRank}
                  onDelete={handleDeleteRank}
                  onCreate={handleCreateRank}
                />
              )}
              {activeTab === 'advertisements' && (
                <AdvertisementsView
                  advertisements={advertisements}
                  onEdit={handleEditAdvertisement}
                  onDelete={handleDeleteAdvertisement}
                  onCreate={handleCreateAdvertisement}
                  onPublish={handlePublishAdvertisement}
                />
              )}
              {activeTab === 'payments' && (
                <PaymentsView payments={payments} />
              )}
            </>
          )}
        </div>
      </main>


      {/* Модальное окно тарифа */}
      {showTariffModal && (
        <TariffModal
          tariff={editingItem}
          onSave={handleSaveTariff}
          onClose={() => setShowTariffModal(false)}
        />
      )}

      {/* Модальное окно тарифа рекламы */}
      {showChannelModal && (
        <ChannelModal
          channel={editingItem}
          onSave={handleSaveChannel}
          onClose={() => setShowChannelModal(false)}
        />
      )}

      {/* Модальное окно тарифа рекламы */}
      {showAdTariffModal && (
        <AdTariffModal
          tariff={editingItem}
          channels={channels}
          onSave={handleSaveAdTariff}
          onClose={() => setShowAdTariffModal(false)}
        />
      )}

      {/* Модальное окно компании */}
      {showCompanyModal && (
        <CompanyModal
          company={editingItem}
          onSave={handleSaveCompany}
          onClose={() => setShowCompanyModal(false)}
        />
      )}

      {/* Модальное окно звания */}
      {showRankModal && (
        <RankModal
          rank={editingItem}
          onSave={handleSaveRank}
          onClose={() => setShowRankModal(false)}
        />
      )}

      {/* Модальное окно рекламы */}
      {showAdvertisementModal && (
        <AdvertisementModal
          advertisement={editingItem}
          channels={channels}
          onSave={handleSaveAdvertisement}
          onClose={() => setShowAdvertisementModal(false)}
        />
      )}

      {/* Уведомления */}
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

// Компонент статистики
function StatsView({ stats, onNavigate }) {
  return (
    <div>
      <div className="table-header">
        <h2>Общая статистика системы</h2>
        <div style={{ color: '#999', fontSize: '14px' }}>
          Обновлено: {new Date().toLocaleString('ru-RU')}
        </div>
      </div>
      <div className="stats-grid">
        <div 
          className="stat-card stat-card-clickable" 
          onClick={() => onNavigate('users')}
          style={{ cursor: 'pointer' }}
        >
          <div className="stat-icon">👥</div>
          <div className="stat-value">{stats.total_users}</div>
          <div className="stat-label">Всего пользователей</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">⭐</div>
          <div className="stat-value">{stats.active_subscriptions}</div>
          <div className="stat-label">Активных подписок</div>
        </div>
        <div 
          className="stat-card stat-card-clickable" 
          onClick={() => onNavigate('payments')}
          style={{ cursor: 'pointer' }}
        >
          <div className="stat-icon">💳</div>
          <div className="stat-value">{stats.total_payments}</div>
          <div className="stat-label">Всего платежей</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">💰</div>
          <div className="stat-value">${stats.total_revenue.toFixed(2)}</div>
          <div className="stat-label">Общая выручка</div>
        </div>
        <div 
          className="stat-card stat-card-clickable" 
          onClick={() => onNavigate('tariffs')}
          style={{ cursor: 'pointer' }}
        >
          <div className="stat-icon">📋</div>
          <div className="stat-value">{stats.total_tariffs || 0}</div>
          <div className="stat-label">Тарифов</div>
        </div>
        <div
          className="stat-card stat-card-clickable"
          onClick={() => onNavigate('companies')}
          style={{ cursor: 'pointer' }}
        >
          <div className="stat-icon">🏢</div>
          <div className="stat-value">{stats.total_companies || 0}</div>
          <div className="stat-label">Компаний в каталоге</div>
        </div>
        <div
          className="stat-card stat-card-clickable"
          onClick={() => onNavigate('ranks')}
          style={{ cursor: 'pointer' }}
        >
          <div className="stat-icon">🏆</div>
          <div className="stat-value">{stats.total_ranks || 0}</div>
          <div className="stat-label">Пользовательских званий</div>
        </div>
      </div>
    </div>
  );
}

// Компонент списка пользователей
function UsersView({ users }) {
  const formatDate = (dateString) => {
    if (!dateString) return '—';
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  };

  return (
    <div>
      <div className="table-header">
        <h2>Все пользователи</h2>
        <div style={{ color: '#999', fontSize: '14px' }}>Всего: {users.length}</div>
      </div>
      {users.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">👥</div>
          <div className="empty-state-text">Пользователи не найдены</div>
          <div className="empty-state-subtext">Пользователи появятся после регистрации</div>
        </div>
      ) : (
        <div className="users-cards">
          {users.map(user => (
            <div key={user.id} className="user-card-admin">
              <div className="user-card-header">
                <div className="user-card-title">
                  <h3>{user.first_name || 'Без имени'}</h3>
                  {user.has_active_subscription ? (
                    <span className="badge badge-success">✓ Подписка активна</span>
                  ) : (
                    <span className="badge badge-inactive">✗ Нет подписки</span>
                  )}
                </div>
              </div>
              
              <div className="user-card-body">
                <div className="user-card-info">
                  <div className="user-info-item">
                    <span className="user-info-icon">🆔</span>
                    <div className="user-info-content">
                      <span className="user-info-label">Telegram ID:</span>
                      <span className="user-info-text">{user.telegram_id}</span>
                    </div>
                  </div>
                  
                  {user.username && (
                    <div className="user-info-item">
                      <span className="user-info-icon">@</span>
                      <div className="user-info-content">
                        <span className="user-info-label">Username:</span>
                        <span className="user-info-text">@{user.username}</span>
                      </div>
                    </div>
                  )}
                  
                  {user.current_rank && (
                    <div className="user-info-item">
                      <span className="user-info-icon">{user.current_rank.icon_emoji}</span>
                      <div className="user-info-content">
                        <span className="user-info-label">Ранг:</span>
                        <span className="user-info-text" style={{ color: user.current_rank.color }}>
                          {user.current_rank.name}
                        </span>
                      </div>
                    </div>
                  )}
                  
                  <div className="user-info-item">
                    <span className="user-info-icon">📅</span>
                    <div className="user-info-content">
                      <span className="user-info-label">Дней подписки:</span>
                      <span className="user-info-text">{user.total_subscription_days || 0} дней</span>
                    </div>
                  </div>
                  
                  {user.subscription_end_date && (
                    <div className="user-info-item">
                      <span className="user-info-icon">⏰</span>
                      <div className="user-info-content">
                        <span className="user-info-label">Подписка до:</span>
                        <span className="user-info-text">{formatDate(user.subscription_end_date)}</span>
                      </div>
                    </div>
                  )}
                  
                  {user.created_at && (
                    <div className="user-info-item">
                      <span className="user-info-icon">📆</span>
                      <div className="user-info-content">
                        <span className="user-info-label">Регистрация:</span>
                        <span className="user-info-text">{formatDate(user.created_at)}</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
              
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Компонент списка тарифов
function TariffsView({ tariffs, onEdit, onDelete, onCreate }) {
  return (
    <div>
      <div className="table-header">
        <h2>Тарифы</h2>
        <button className="btn-primary" onClick={onCreate}>
          <span style={{ fontSize: '18px' }}>+</span> Создать
        </button>
      </div>
      {tariffs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">💰</div>
          <div className="empty-state-text">Тарифы не найдены</div>
          <div className="empty-state-subtext">Создайте первый тариф для подписки</div>
        </div>
      ) : (
        <div className="tariffs-cards">
          {tariffs.map(tariff => (
            <div key={tariff.id} className="tariff-card-admin">
              <div className="tariff-card-header">
                <div className="tariff-card-title">
                  <h3>{tariff.name}</h3>
                  {tariff.is_active ? (
                    <span className="badge badge-success">Активен</span>
                  ) : (
                    <span className="badge badge-inactive">Неактивен</span>
                  )}
                </div>
                <div className="tariff-card-price">
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#28a745' }}>
                    ${parseFloat(tariff.price_usd).toFixed(2)}
                  </div>
                  {tariff.price_stars && (
                    <div style={{ fontSize: '18px', color: '#FFD700', marginTop: '8px' }}>
                      ⭐ {tariff.price_stars}
                    </div>
                  )}
                </div>
              </div>
              
              <div className="tariff-card-body">
                {tariff.description && (
                  <p className="tariff-description">{tariff.description}</p>
                )}
                <div className="tariff-duration">
                  📅 Срок: <strong>{tariff.duration_days} дней</strong>
                </div>
              </div>

              <div className="tariff-card-actions">
                <button className="btn-small btn-edit" onClick={() => onEdit(tariff)}>
                  ✏️ Редактировать
                </button>
                <button className="btn-small btn-danger" onClick={() => onDelete(tariff.id)}>
                  🗑️ Удалить
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ChannelsView({ channels, onEdit, onDelete, onCreate, onTogglePaidMode }) {
  const getTypeLabel = (type) => {
    if (type === 'channel') return 'Канал';
    if (type === 'group') return 'Группа';
    return type;
  };

  return (
    <div>
      <div className="table-header">
        <h2>Каналы и группы</h2>
        <button className="btn-primary" onClick={onCreate}>
          <span style={{ fontSize: '18px' }}>+</span> Добавить
        </button>
      </div>
      {channels.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📢</div>
          <div className="empty-state-text">Каналы и группы не добавлены</div>
          <div className="empty-state-subtext">Добавьте первую площадку для публикации</div>
        </div>
      ) : (
        <div className="tariffs-cards">
          {channels.map((channel) => (
            <div key={channel.id} className="tariff-card-admin">
              <div className="tariff-card-header">
                <div className="tariff-card-title">
                  <h3>
                    <span style={{ marginRight: '8px' }}>{channel.icon || '📢'}</span>
                    {channel.title}
                  </h3>
                  <div style={{ display: 'flex', gap: '8px', marginTop: '8px', flexWrap: 'wrap' }}>
                    {channel.is_active ? (
                      <span className="badge badge-success">Активен</span>
                    ) : (
                      <span className="badge badge-inactive">Неактивен</span>
                    )}
                    <span className="badge" style={{ background: '#6c757d' }}>
                      {getTypeLabel(channel.type)}
                    </span>
                    {channel.thread_id && (
                      <span className="badge" style={{ background: '#17a2b8' }}>
                        Topic #{channel.thread_id}
                      </span>
                    )}
                    {channel.type === 'group' && (
                      <span
                        className="badge"
                        style={{ background: channel.paid_mode_enabled ? '#dc3545' : '#28a745' }}
                      >
                        {channel.paid_mode_enabled ? 'Платный режим ВКЛ' : 'Платный режим ВЫКЛ'}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="tariff-card-body">
                <div className="tariff-duration">ID: <strong>{channel.id}</strong></div>
                <div className="tariff-duration" style={{ marginTop: '8px' }}>
                  Chat ID: <strong>{channel.telegram_chat_id}</strong>
                </div>
                {channel.link && (
                  <div className="tariff-duration" style={{ marginTop: '8px' }}>
                    Ссылка: <a href={channel.link} target="_blank" rel="noopener noreferrer">{channel.link}</a>
                  </div>
                )}
              </div>

              <div className="tariff-card-actions">
                {channel.type === 'group' && (
                  <button
                    className="btn-small"
                    style={{
                      background: channel.paid_mode_enabled ? '#ffc107' : '#28a745',
                      color: channel.paid_mode_enabled ? '#212529' : '#fff'
                    }}
                    onClick={() => onTogglePaidMode(channel)}
                  >
                    {channel.paid_mode_enabled ? 'Выключить платный режим' : 'Включить платный режим'}
                  </button>
                )}
                <button className="btn-small btn-edit" onClick={() => onEdit(channel)}>
                  ✏️ Редактировать
                </button>
                <button className="btn-small btn-danger" onClick={() => onDelete(channel.id)}>
                  🗑️ Удалить
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Компонент списка званий
function RanksView({ ranks, onEdit, onDelete, onCreate }) {
  return (
    <div>
      <div className="table-header">
        <h2>Пользовательские звания</h2>
        <button className="btn-primary" onClick={onCreate}>
          <span style={{ fontSize: '18px' }}>+</span> Создать
        </button>
      </div>
      {ranks.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🏆</div>
          <div className="empty-state-text">Звания не найдены</div>
          <div className="empty-state-subtext">Создайте первое звание для пользователей</div>
        </div>
      ) : (
        <div className="tariffs-cards">
          {ranks.map(rank => (
            <div key={rank.id} className="tariff-card-admin">
              <div className="tariff-card-header">
                <div className="tariff-card-title">
                  <h3>
                    <span style={{ marginRight: '8px' }}>{rank.icon_emoji}</span>
                    {rank.name}
                  </h3>
                  {rank.is_active ? (
                    <span className="badge badge-success">Активно</span>
                  ) : (
                    <span className="badge badge-inactive">Неактивно</span>
                  )}
                </div>
                <div className="tariff-card-price" style={{ color: rank.color || '#007BFF', fontSize: '14px' }}>
                  {rank.required_days} дней
                </div>
              </div>

              <div className="tariff-card-body">
                {rank.description && (
                  <p className="tariff-description">{rank.description}</p>
                )}
                <div className="tariff-duration">
                  📊 Порядок: <strong>{rank.sort_order}</strong>
                </div>
                {rank.color && (
                  <div className="tariff-duration" style={{ marginTop: '5px' }}>
                    🎨 Цвет: <span style={{ color: rank.color, fontWeight: 'bold' }}>{rank.color}</span>
                  </div>
                )}
              </div>

              <div className="tariff-card-actions">
                <button className="btn-small btn-edit" onClick={() => onEdit(rank)}>
                  ✏️ Редактировать
                </button>
                <button className="btn-small btn-danger" onClick={() => onDelete(rank.id)}>
                  🗑️ Удалить
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Компонент списка тарифов рекламы
function AdTariffsView({ tariffs, channels, onEdit, onDelete, onCreate }) {
  const getChannelTypeName = (type) => {
    const channel = channels.find((item) => String(item.id) === String(type));
    if (channel) {
      return `${channel.icon || (channel.type === 'channel' ? '📢' : '👥')} ${channel.title}`;
    }
    return type;
  };

  return (
    <div>
      <div className="table-header">
        <h2>Тарифы рекламы</h2>
        <button className="btn-primary" onClick={onCreate}>
          <span style={{ fontSize: '18px' }}>+</span> Создать тариф
        </button>
      </div>
      {tariffs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📊</div>
          <div className="empty-state-text">Тарифы рекламы не найдены</div>
          <div className="empty-state-subtext">Создайте первый тариф для размещения рекламы</div>
        </div>
      ) : (
        <div className="tariffs-cards">
          {tariffs.map(tariff => (
            <div key={tariff.id} className="tariff-card-admin">
              <div className="tariff-card-header">
                <div className="tariff-card-title">
                  <h3>{tariff.name}</h3>
                  <div style={{ display: 'flex', gap: '8px', marginTop: '8px', flexWrap: 'wrap' }}>
                    {tariff.is_active ? (
                      <span className="badge badge-success">Активен</span>
                    ) : (
                      <span className="badge badge-inactive">Неактивен</span>
                    )}
                    <span className="badge" style={{ background: '#6c757d' }}>
                      {getChannelTypeName(tariff.channel_type)}
                    </span>
                  </div>
                </div>
                <div className="tariff-card-price">
                  {tariff.price_usd && (
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#28a745', marginBottom: '8px' }}>
                      ${parseFloat(tariff.price_usd).toFixed(2)}
                    </div>
                  )}
                  {tariff.price_stars && (
                    <div style={{ fontSize: '18px', color: '#FFD700' }}>
                      ⭐ {tariff.price_stars}
                    </div>
                  )}
                </div>
              </div>

              <div className="tariff-card-body">
                {tariff.description && (
                  <p className="tariff-description">{tariff.description}</p>
                )}
                <div className="tariff-duration">
                  ⏱️ Длительность: <strong>{tariff.duration_hours} ч</strong>
                </div>
                <div className="tariff-duration" style={{ marginTop: '8px' }}>
                  📍 Порядок: <strong>#{tariff.sort_order}</strong>
                </div>
                {tariff.thread_id && (
                  <div className="tariff-duration" style={{ marginTop: '8px' }}>
                    🧵 Topic: <strong>#{tariff.thread_id}</strong>
                  </div>
                )}
              </div>

              <div className="tariff-card-actions">
                <button className="btn-small btn-edit" onClick={() => onEdit(tariff)}>
                  ✏️ Редактировать
                </button>
                <button className="btn-small btn-danger" onClick={() => onDelete(tariff.id)}>
                  🗑️ Удалить
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Компонент списка компаний
function CompaniesView({ companies, onEdit, onDelete, onCreate }) {
  return (
    <div>
      <div className="table-header">
        <h2>Справочный каталог</h2>
        <button className="btn-primary" onClick={onCreate}>
          <span style={{ fontSize: '18px' }}>+</span> Создать
        </button>
      </div>
      {companies.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🏢</div>
          <div className="empty-state-text">Компании не найдены</div>
          <div className="empty-state-subtext">Добавьте первую компанию в каталог</div>
        </div>
      ) : (
        <div className="tariffs-cards">
          {companies.map(company => (
            <div key={company.id} className="tariff-card-admin">
              <div className="tariff-card-header">
                <div className="tariff-card-title">
                  <h3>
                    <span style={{ marginRight: '8px' }}>{company.icon_emoji || '🏢'}</span>
                    {company.name}
                  </h3>
                  {company.is_active ? (
                    <span className="badge badge-success">Активна</span>
                  ) : (
                    <span className="badge badge-inactive">Неактивна</span>
                  )}
                </div>
                <div className="tariff-card-price" style={{ fontSize: '14px', color: '#666' }}>
                  {company.category}
                </div>
              </div>

              <div className="tariff-card-body">
                {company.description && (
                  <p className="tariff-description">{company.description}</p>
                )}
                <div className="tariff-duration">
                  {company.phone && (
                    <span>📞 {company.phone}</span>
                  )}
                  {company.address && (
                    <span style={{ marginLeft: company.phone ? '15px' : '0' }}>
                      📍 {company.address}
                    </span>
                  )}
                </div>
              </div>

              <div className="tariff-card-actions">
                <button className="btn-small btn-edit" onClick={() => onEdit(company)}>
                  ✏️ Редактировать
                </button>
                <button className="btn-small btn-danger" onClick={() => onDelete(company.id)}>
                  🗑️ Удалить
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Компонент списка платежей
function PaymentsView({ payments }) {
  const totalAmount = payments
    .filter(p => p.status === 'succeeded' || p.status === 'completed')
    .reduce((sum, p) => sum + p.amount, 0);

  const getPaymentSystemIcon = (system) => {
    if (!system || system === 'unknown') return '💳';
    const systemLower = (system || '').toLowerCase();
    if (systemLower.includes('star')) return '⭐';
    if (systemLower.includes('stripe')) return '💳';
    if (systemLower.includes('card')) return '💳';
    return '💰';
  };

  const getPaymentSystemName = (system) => {
    if (!system || system === 'unknown') return 'Неизвестно';
    const systemLower = (system || '').toLowerCase();
    if (systemLower.includes('star')) return '⭐ Telegram Stars';
    if (systemLower.includes('stripe')) return '💳 Stripe';
    if (systemLower.includes('card')) return '💳 Банковская карта';
    return system;
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div>
      <div className="table-header">
        <h2>История платежей</h2>
        <div className="payment-stats">
          <div className="stat-item">
            <span className="stat-label">Выручка:</span>
            <span className="stat-value">${totalAmount.toFixed(2)}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Всего:</span>
            <span className="stat-value">{payments.length}</span>
          </div>
        </div>
      </div>
      {payments.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">💳</div>
          <div className="empty-state-text">Платежи не найдены</div>
          <div className="empty-state-subtext">Платежи появятся после первой покупки</div>
        </div>
      ) : (
        <div className="payments-cards">
          {payments.map(payment => (
            <div key={payment.id} className="payment-card-admin">
              <div className="payment-card-header">
                <div className="payment-card-id">#{payment.id}</div>
                {payment.status === 'succeeded' || payment.status === 'completed' ? (
                  <span className="badge badge-success">✓ Успешно</span>
                ) : payment.status === 'pending' ? (
                  <span className="badge badge-warning">⏳ Ожидание</span>
                ) : (
                  <span className="badge badge-danger">✗ Отменён</span>
                )}
              </div>
              <div className="payment-card-body">
                <div className="payment-card-user">
                  <span className="payment-icon">👤</span>
                  <div className="payment-user-info">
                    <div className="payment-user-name">
                      {payment.user_name || 'Неизвестный пользователь'}
                    </div>
                    {payment.username && (
                      <div className="payment-user-username">@{payment.username}</div>
                    )}
                    {payment.user_telegram_id && (
                      <div className="payment-user-telegram-id">ID: {payment.user_telegram_id}</div>
                    )}
                  </div>
                </div>
                
                <div className="payment-card-amount">
                  <div className="payment-amount-value">
                    {payment.currency === 'USD'
                      ? `$${typeof payment.amount === 'number' ? payment.amount.toFixed(2) : parseFloat(payment.amount || 0).toFixed(2)}`
                      : `${typeof payment.amount === 'number' ? payment.amount.toFixed(2) : parseFloat(payment.amount || 0).toFixed(2)} ${payment.currency || ''}`.trim()
                    }
                  </div>
                  {payment.currency && payment.currency !== 'USD' && (
                    <div className="payment-amount-currency">
                      {payment.currency}
                    </div>
                  )}
                </div>
                
                <div className="payment-card-info">
                  <div className="payment-info-item payment-info-method">
                    <span className="payment-info-icon">{getPaymentSystemIcon(payment.payment_system)}</span>
                    <div className="payment-info-content">
                      <span className="payment-info-label">Метод оплаты:</span>
                      <span className="payment-info-text payment-method-name">
                        {getPaymentSystemName(payment.payment_system)}
                      </span>
                    </div>
                  </div>
                  
                  <div className="payment-info-item">
                    <span className="payment-info-icon">📅</span>
                    <div className="payment-info-content">
                      <span className="payment-info-label">Дата:</span>
                      <span className="payment-info-text">{formatDate(payment.created_at)}</span>
                    </div>
                  </div>
                  
                  {payment.transaction_id && (
                    <div className="payment-info-item">
                      <span className="payment-info-icon">🔑</span>
                      <div className="payment-info-content">
                        <span className="payment-info-label">Транзакция:</span>
                        <span className="payment-info-text payment-transaction-id">
                          {payment.transaction_id}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Компонент списка рекламы
function AdvertisementsView({ advertisements, onEdit, onDelete, onPublish }) {
  const formatDate = (dateString) => {
    if (!dateString) return '—';
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusBadge = (ad) => {
    if (ad.is_published) {
      return <span className="badge badge-success">✓ Опубликована</span>;
    }
    if (ad.status === 'pending') {
      return <span className="badge badge-warning">⏳ На модерации</span>;
    }
    if (ad.status === 'approved') {
      return <span className="badge badge-info">✓ Одобрена</span>;
    }
    if (ad.status === 'rejected') {
      return <span className="badge badge-danger">✗ Отклонена</span>;
    }
    return <span className="badge badge-inactive">—</span>;
  };

  const getDeleteAfterText = (hours) => {
    if (hours >= 168) return `${hours / 168} недель`;
    if (hours >= 24) return `${hours / 24} дней`;
    return `${hours} часов`;
  };

  return (
    <div>
      <div className="table-header">
        <h2>Рекламные объявления</h2>
        <div style={{ fontSize: '14px', color: '#666', fontStyle: 'italic' }}>
          Только оплаченные объявления
        </div>
      </div>
      {advertisements.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📢</div>
          <div className="empty-state-text">Оплаченных объявлений пока нет</div>
          <div className="empty-state-subtext">Пользователи могут создать и оплатить рекламу через приложение</div>
        </div>
      ) : (
        <div className="advertisements-cards">
          {advertisements.map(ad => (
            <div key={ad.id} className="advertisement-card-admin">
              <div className="advertisement-card-header">
                <div className="advertisement-card-title">
                  <h3>{ad.title}</h3>
                  {getStatusBadge(ad)}
                </div>
              </div>

              <div className="advertisement-card-body">
                <div className="advertisement-content">
                  <p>{ad.content}</p>
                  {ad.media_url && (
                    <div className="advertisement-media">
                      <span className="advertisement-media-icon">📎</span>
                      <a href={resolveMediaUrl(splitMediaUrls(ad.media_url)[0] || "")} target="_blank" rel="noopener noreferrer" className="advertisement-media-link">
                        Медиа файл
                      </a>
                    </div>
                  )}
                </div>

                <div className="advertisement-info">
                  <div className="advertisement-info-item">
                    <span className="advertisement-info-icon">⏰</span>
                    <div className="advertisement-info-content">
                      <span className="advertisement-info-label">Удалить через:</span>
                      <span className="advertisement-info-text">
                        {getDeleteAfterText(ad.delete_after_hours)}
                      </span>
                    </div>
                  </div>

                  {ad.scheduled_delete_date && (
                    <div className="advertisement-info-item">
                      <span className="advertisement-info-icon">📅</span>
                      <div className="advertisement-info-content">
                        <span className="advertisement-info-label">Удалить:</span>
                        <span className="advertisement-info-text">
                          {formatDate(ad.scheduled_delete_date)}
                        </span>
                      </div>
                    </div>
                  )}

                  <div className="advertisement-info-item">
                    <span className="advertisement-info-icon">📆</span>
                    <div className="advertisement-info-content">
                      <span className="advertisement-info-label">Создано:</span>
                      <span className="advertisement-info-text">
                        {formatDate(ad.created_at)}
                      </span>
                    </div>
                  </div>

                  {ad.publish_date && (
                    <div className="advertisement-info-item">
                      <span className="advertisement-info-icon">🚀</span>
                      <div className="advertisement-info-content">
                        <span className="advertisement-info-label">Опубликовано:</span>
                        <span className="advertisement-info-text">
                          {formatDate(ad.publish_date)}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="advertisement-card-actions">
                {!ad.is_published && ad.status === 'approved' && (
                  <button
                    className="btn-small btn-publish"
                    onClick={() => onPublish(ad.id)}
                  >
                    🚀 Опубликовать
                  </button>
                )}
                {!ad.is_published && ad.status === 'pending' && (
                  <button className="btn-small" disabled title="Сначала одобрите объявление (status=approved)">
                    ⏳ Ожидает одобрения
                  </button>
                )}
                <button className="btn-small" onClick={() => onEdit(ad)}>
                  ✏️ Редактировать
                </button>
                <button className="btn-small btn-danger" onClick={() => onDelete(ad.id)}>
                  🗑️ Удалить
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Модальное окно редактирования тарифа
function TariffModal({ tariff, onSave, onClose }) {
  const [formData, setFormData] = useState({
    name: tariff?.name || '',
    description: tariff?.description || '',
    price_usd: tariff?.price_usd || '',
    price_stars: tariff?.price_stars || '',
    duration_days: tariff?.duration_days || '',
    is_active: tariff?.is_active ?? true
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    const submitData = {
      name: formData.name,
      description: formData.description,
      duration_days: parseInt(formData.duration_days),
      is_active: formData.is_active,
      price_usd: parseFloat(formData.price_usd),
      price_stars: formData.price_stars ? parseInt(formData.price_stars) : null
    };

    onSave(submitData);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content admin-modal" onClick={(e) => e.stopPropagation()}>
        <h2>{tariff ? 'Редактировать тариф' : 'Создать тариф'}</h2>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Название: *</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              maxLength={100}
              required
            />
          </div>

          <div className="form-group">
            <label>Описание:</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              maxLength={500}
              rows={3}
            />
          </div>

          <div className="form-group">
            <label>Цена в долларах ($): *</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              max="999999"
              value={formData.price_usd}
              onChange={(e) => setFormData({ ...formData, price_usd: e.target.value })}
              placeholder="5.00"
              required
            />
          </div>

          <div className="form-group">
            <label>Цена в Telegram Stars (⭐):</label>
            <input
              type="number"
              step="1"
              min="0"
              max="999999"
              value={formData.price_stars}
              onChange={(e) => setFormData({ ...formData, price_stars: e.target.value })}
              placeholder="500"
            />
            <small style={{ color: '#999', fontSize: '12px', marginTop: '5px', display: 'block' }}>
              Оставьте пустым, если не используется
            </small>
          </div>

          <div className="form-group">
            <label>Срок (дней): *</label>
            <input
              type="number"
              min="1"
              max="3650"
              value={formData.duration_days}
              onChange={(e) => setFormData({ ...formData, duration_days: e.target.value })}
              required
            />
          </div>

          <div className="form-group checkbox">
            <label>
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              />
              Активен
            </label>
          </div>

          <div className="form-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Отмена
            </button>
            <button type="submit" className="btn-primary">
              Сохранить
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ChannelModal({ channel, onSave, onClose }) {
  const [formData, setFormData] = useState({
    telegram_chat_id: channel?.telegram_chat_id || '',
    title: channel?.title || '',
    type: channel?.type || 'channel',
    link: channel?.link || '',
    icon: channel?.icon || '',
    thread_id: channel?.thread_id || '',
    is_active: channel?.is_active ?? true,
    paid_mode_enabled: channel?.paid_mode_enabled ?? true,
    sort_order: channel?.sort_order || 0,
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
      telegram_chat_id: formData.telegram_chat_id,
      title: formData.title,
      type: formData.type,
      link: formData.link || null,
      icon: formData.icon || null,
      thread_id: formData.thread_id ? parseInt(formData.thread_id, 10) : null,
      is_active: formData.is_active,
      paid_mode_enabled: formData.type === 'group' ? formData.paid_mode_enabled : false,
      sort_order: parseInt(formData.sort_order, 10) || 0,
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content admin-modal" onClick={(e) => e.stopPropagation()}>
        <h2>{channel ? 'Редактировать канал/группу' : 'Добавить канал/группу'}</h2>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Telegram Chat ID: *</label>
            <input
              type="text"
              value={formData.telegram_chat_id}
              onChange={(e) => setFormData({ ...formData, telegram_chat_id: e.target.value })}
              placeholder="-1001234567890 или @username"
              required
            />
          </div>

          <div className="form-group">
            <label>Название: *</label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label>Тип: *</label>
            <select
              value={formData.type}
              onChange={(e) => setFormData({
                ...formData,
                type: e.target.value,
                paid_mode_enabled: e.target.value === 'group' ? formData.paid_mode_enabled : false
              })}
              required
            >
              <option value="channel">Канал</option>
              <option value="group">Группа</option>
            </select>
          </div>

          <div className="form-group">
            <label>Ссылка:</label>
            <input
              type="text"
              value={formData.link}
              onChange={(e) => setFormData({ ...formData, link: e.target.value })}
              placeholder="https://t.me/..."
            />
          </div>

          <div className="form-group">
            <label>Иконка:</label>
            <input
              type="text"
              value={formData.icon}
              onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
              placeholder="📢"
            />
          </div>

          <div className="form-group">
            <label>Topic ID (thread_id):</label>
            <input
              type="number"
              value={formData.thread_id}
              onChange={(e) => setFormData({ ...formData, thread_id: e.target.value })}
              placeholder="Опционально, только для групп с Topics"
            />
          </div>

          <div className="form-group">
            <label>Порядок сортировки:</label>
            <input
              type="number"
              min="0"
              value={formData.sort_order}
              onChange={(e) => setFormData({ ...formData, sort_order: e.target.value })}
            />
          </div>

          <div className="form-group checkbox">
            <label>
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              />
              Активен
            </label>
          </div>

          {formData.type === 'group' && (
            <div className="form-group checkbox">
              <label>
                <input
                  type="checkbox"
                  checked={formData.paid_mode_enabled}
                  onChange={(e) => setFormData({ ...formData, paid_mode_enabled: e.target.checked })}
                />
                Платный режим включен
              </label>
            </div>
          )}

          <div className="form-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Отмена
            </button>
            <button type="submit" className="btn-primary">
              Сохранить
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function AdTariffModal({ tariff, channels, onSave, onClose }) {
  const [formData, setFormData] = useState({
    name: tariff?.name || '',
    description: tariff?.description || '',
    channel_type: tariff?.channel_type || (channels?.[0]?.id ? String(channels[0].id) : ''),
    thread_id: tariff?.thread_id ?? '',
    duration_hours: tariff?.duration_hours || 24,
    price_usd: tariff?.price_usd || '',
    price_stars: tariff?.price_stars || '',
    is_active: tariff?.is_active ?? true,
    sort_order: tariff?.sort_order || 0
  });

  const selectedChannel = channels.find((channel) => String(channel.id) === String(formData.channel_type));
  const isGroupChannel = selectedChannel?.type === 'group';

  const handleSubmit = (e) => {
    e.preventDefault();

    const submitData = {
      name: formData.name,
      description: formData.description,
      channel_type: formData.channel_type,
      thread_id: formData.thread_id ? parseInt(formData.thread_id, 10) : null,
      duration_hours: parseInt(formData.duration_hours),
      price_usd: parseFloat(formData.price_usd),
      price_stars: formData.price_stars ? parseInt(formData.price_stars) : null,
      is_active: formData.is_active,
      sort_order: parseInt(formData.sort_order)
    };

    onSave(submitData);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content admin-modal" onClick={(e) => e.stopPropagation()}>
        <h2>{tariff ? 'Редактировать тариф рекламы' : 'Создать тариф рекламы'}</h2>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Название тарифа: *</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Например: Базовый - Главный канал"
              maxLength={100}
              required
            />
          </div>

          <div className="form-group">
            <label>Описание:</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Краткое описание тарифа"
              maxLength={500}
              rows={3}
            />
          </div>

          <div className="form-group">
            <label>Тип канала: *</label>
            <select
              value={formData.channel_type}
              onChange={(e) => {
                const channelType = e.target.value;
                const nextChannel = channels.find((channel) => String(channel.id) === String(channelType));
                setFormData((prev) => ({
                  ...prev,
                  channel_type: channelType,
                  thread_id: nextChannel?.type === 'group'
                    ? (prev.thread_id === '' ? (nextChannel.thread_id ?? '') : prev.thread_id)
                    : '',
                }));
              }}
              required
            >
              {channels.length === 0 ? (
                <option value="">Сначала добавьте канал/группу</option>
              ) : (
                channels.map((channel) => (
                  <option key={channel.id} value={String(channel.id)}>
                    {(channel.icon || (channel.type === 'channel' ? '📢' : '👥'))} {channel.title}
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="form-group">
            <label>Topic ID (thread_id):</label>
            <input
              type="number"
              min="1"
              value={formData.thread_id}
              onChange={(e) => setFormData({ ...formData, thread_id: e.target.value })}
              placeholder={isGroupChannel ? 'Например: 12345' : 'Доступно только для групп'}
              disabled={!isGroupChannel}
            />
            <small style={{ color: '#999', fontSize: '12px', marginTop: '5px', display: 'block' }}>
              Для каналов оставьте пустым. Для групп можно указать конкретный Topic для публикации.
            </small>
          </div>

          <div className="form-group">
            <label>Длительность (часы): *</label>
            <input
              type="number"
              value={formData.duration_hours}
              onChange={(e) => setFormData({ ...formData, duration_hours: e.target.value })}
              min="1"
              max="8760"
              required
            />
            <small style={{ color: '#999', fontSize: '12px', marginTop: '5px', display: 'block' }}>
              От 1 часа до 8760 часов (365 дней)
            </small>
          </div>

          <div className="form-group">
            <label>Цена в долларах ($): *</label>
            <input
              type="number"
              step="0.01"
              value={formData.price_usd}
              onChange={(e) => setFormData({ ...formData, price_usd: e.target.value })}
              min="0.01"
              max="999999"
              placeholder="10.00"
              required
            />
          </div>

          <div className="form-group">
            <label>Цена в Telegram Stars (⭐):</label>
            <input
              type="number"
              value={formData.price_stars}
              onChange={(e) => setFormData({ ...formData, price_stars: e.target.value })}
              min="0"
              max="999999"
              placeholder="500"
            />
            <small style={{ color: '#999', fontSize: '12px', marginTop: '5px', display: 'block' }}>
              Оставьте пустым, если не используется
            </small>
          </div>

          <div className="form-group">
            <label>Порядок сортировки:</label>
            <input
              type="number"
              value={formData.sort_order}
              onChange={(e) => setFormData({ ...formData, sort_order: e.target.value })}
              min="0"
            />
            <small style={{ color: '#999', fontSize: '12px', marginTop: '5px', display: 'block' }}>
              Меньшее значение = выше в списке
            </small>
          </div>

          <div className="form-group checkbox">
            <label>
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              />
              Активен
            </label>
          </div>

          <div className="form-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Отмена
            </button>
            <button type="submit" className="btn-primary">
              Сохранить
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Модальное окно редактирования рекламы
function AdvertisementModal({ advertisement, channels, onSave, onClose }) {
  const deleteAfterOptions = [
    { hours: 24, label: '24 часа' },
    { hours: 48, label: '48 часов (2 дня)' },
    { hours: 72, label: '72 часа (3 дня)' },
    { hours: 168, label: '168 часов (7 дней)' },
    { hours: 336, label: '336 часов (14 дней)' },
    { hours: 720, label: '720 часов (30 дней)' },
  ];

  const [formData, setFormData] = useState({
    title: advertisement?.title || '',
    content: advertisement?.content || '',
    media_url: advertisement?.media_url || '',
    delete_after_hours: advertisement?.delete_after_hours || 24,
    status: advertisement?.status || 'pending',
    price: advertisement?.price || '',
    channel_id: advertisement?.channel_id || ''
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(formData);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content admin-modal" onClick={(e) => e.stopPropagation()}>
        <h2>{advertisement ? 'Редактировать рекламу' : 'Создать рекламу'}</h2>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Заголовок:</label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              maxLength={255}
              required
            />
          </div>

          <div className="form-group">
            <label>Содержание:</label>
            <textarea
              value={formData.content}
              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
              required
              rows={6}
            />
          </div>

          <div className="form-group">
            <label>Изображения/фото (опционально):</label>
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={async (e) => {
                const files = Array.from(e.target.files);
                if (files.length === 0) return;

                const totalSize = files.reduce((sum, file) => sum + file.size, 0);
                if (totalSize > 10 * 1024 * 1024) {
                  alert('Общий размер файлов больше 10 МБ');
                  e.target.value = '';
                  return;
                }

                // Загружаем файлы по очереди
                const uploadedUrls = [];

                for (const file of files) {
                  const uploadFormData = new FormData();
                  uploadFormData.append('file', file);

                  try {
                    const response = await fetch(`${import.meta.env.VITE_API_URL}/api/upload-image`, {
                      method: 'POST',
                      headers: buildAuthHeaders(),
                      body: uploadFormData
                    });

                    const data = await response.json();

                    if (data.success) {
                      uploadedUrls.push(data.url);
                    } else {
                      alert(`Ошибка загрузки ${file.name}: ${data.detail || 'Неизвестная ошибка'}`);
                    }
                  } catch (err) {
                    console.error('Upload error:', err);
                    alert(`Ошибка при загрузке ${file.name}`);
                  }
                }

                if (uploadedUrls.length > 0) {
                  // Добавляем к существующим URL
                  const currentUrls = splitMediaUrls(formData.media_url);
                  const allUrls = [...currentUrls, ...uploadedUrls];
                  setFormData(prev => ({ ...prev, media_url: allUrls.join(',') }));
                }

                e.target.value = '';
              }}
              style={{ marginBottom: '10px' }}
            />
            {formData.media_url && (
              <div style={{ marginTop: '10px' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '10px' }}>
                  {splitMediaUrls(formData.media_url).map((url, index) => (
                    <div key={index} style={{ position: 'relative' }}>
                      <img
                        src={resolveMediaUrl(url)}
                        alt={`Preview ${index + 1}`}
                        style={{
                          width: '100px',
                          height: '100px',
                          borderRadius: '8px',
                          objectFit: 'cover'
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => {
                          const urls = splitMediaUrls(formData.media_url);
                          const newUrls = urls.filter((_, i) => i !== index);
                          setFormData({ ...formData, media_url: newUrls.join(',') });
                        }}
                        style={{
                          position: 'absolute',
                          top: '-5px',
                          right: '-5px',
                          padding: '4px 8px',
                          background: '#f44336',
                          color: 'white',
                          border: 'none',
                          borderRadius: '50%',
                          cursor: 'pointer',
                          fontSize: '12px',
                          lineHeight: '1'
                        }}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setFormData({ ...formData, media_url: '' })}
                  style={{
                    padding: '6px 12px',
                    background: '#f44336',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '12px'
                  }}
                >
                  Удалить все изображения
                </button>
              </div>
            )}
            <small style={{ display: 'block', marginTop: '5px', color: '#999', fontSize: '12px' }}>
              Можно загрузить несколько изображений. Общий размер: макс. 10 МБ
            </small>
          </div>

          <div className="form-group">
            <label>Удалить через:</label>
            <select
              value={formData.delete_after_hours}
              onChange={(e) => setFormData({ ...formData, delete_after_hours: parseInt(e.target.value) })}
              required
            >
              {deleteAfterOptions.map(option => (
                <option key={option.hours} value={option.hours}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Цена ($):</label>
            <input
              type="text"
              value={formData.price ? `$${formData.price} (рассчитана автоматически)` : 'Не указана'}
              readOnly
              disabled
              style={{ backgroundColor: '#f5f5f5', cursor: 'not-allowed', color: '#666' }}
            />
            <small style={{ color: '#666', fontSize: '12px', display: 'block', marginTop: '5px' }}>
              Цена рассчитывается автоматически при создании рекламы пользователем
            </small>
          </div>

          <div className="form-group">
            <label>Канал/Группа для размещения:</label>
            <select
              value={formData.channel_id}
              onChange={(e) => setFormData({ ...formData, channel_id: e.target.value })}
            >
              <option value="">Выберите канал/группу</option>
              {channels.map((channel) => (
                <option key={channel.id} value={String(channel.id)}>
                  {(channel.icon || (channel.type === 'channel' ? '📢' : '👥'))} {channel.title}
                </option>
              ))}
            </select>
          </div>

          {advertisement && (
            <div className="form-group">
              <label>Статус:</label>
              <select
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                required
              >
                <option value="pending">⏳ На модерации</option>
                <option value="approved">✓ Одобрена</option>
                <option value="rejected">✗ Отклонена</option>
                <option value="published">🚀 Опубликована</option>
              </select>
            </div>
          )}

          <div className="form-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Отмена
            </button>
            <button type="submit" className="btn-primary">
              Сохранить
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Модальное окно редактирования компании
function CompanyModal({ company, onSave, onClose }) {
  const [formData, setFormData] = useState({
    name: company?.name || '',
    category: company?.category || '',
    phone: company?.phone || '',
    address: company?.address || '',
    description: company?.description || '',
    icon_emoji: company?.icon_emoji || '🏢',
    is_active: company?.is_active ?? true
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(formData);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content admin-modal" onClick={(e) => e.stopPropagation()}>
        <h2>{company ? 'Редактировать компанию' : 'Добавить компанию'}</h2>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Название:</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              maxLength={255}
              required
            />
          </div>

          <div className="form-group">
            <label>Категория:</label>
            <input
              type="text"
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value })}
              maxLength={255}
              required
            />
          </div>

          <div className="form-group">
            <label>Телефон:</label>
            <input
              type="tel"
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              maxLength={50}
            />
          </div>

          <div className="form-group">
            <label>Адрес:</label>
            <input
              type="text"
              value={formData.address}
              onChange={(e) => setFormData({ ...formData, address: e.target.value })}
              maxLength={500}
            />
          </div>

          <div className="form-group">
            <label>Описание:</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              maxLength={5000}
            />
          </div>

          <div className="form-group">
            <label>Иконка (эмодзи):</label>
            <input
              type="text"
              value={formData.icon_emoji}
              onChange={(e) => setFormData({ ...formData, icon_emoji: e.target.value })}
              maxLength={10}
              placeholder="🏢"
            />
          </div>

          <div className="form-group checkbox">
            <label>
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              />
              Активна
            </label>
          </div>

          <div className="form-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Отмена
            </button>
            <button type="submit" className="btn-primary">
              Сохранить
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Модальное окно редактирования звания
function RankModal({ rank, onSave, onClose }) {
  const [formData, setFormData] = useState({
    name: rank?.name || '',
    description: rank?.description || '',
    icon_emoji: rank?.icon_emoji || '🏆',
    required_days: rank?.required_days || 0,
    color: rank?.color || '#007BFF',
    is_active: rank?.is_active ?? true,
    sort_order: rank?.sort_order || 0
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
      ...formData,
      required_days: parseInt(formData.required_days),
      sort_order: parseInt(formData.sort_order)
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content admin-modal" onClick={(e) => e.stopPropagation()}>
        <h2>{rank ? 'Редактировать звание' : 'Создать звание'}</h2>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Название:</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              maxLength={100}
              required
            />
          </div>

          <div className="form-group">
            <label>Описание:</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              maxLength={500}
              rows={3}
            />
          </div>

          <div className="form-group">
            <label>Иконка (эмодзи):</label>
            <input
              type="text"
              value={formData.icon_emoji}
              onChange={(e) => setFormData({ ...formData, icon_emoji: e.target.value })}
              maxLength={10}
              placeholder="🏆"
            />
          </div>

          <div className="form-group">
            <label>Требуемое количество дней:</label>
            <input
              type="number"
              min="0"
              max="36500"
              value={formData.required_days}
              onChange={(e) => setFormData({ ...formData, required_days: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label>Цвет (HEX):</label>
            <input
              type="text"
              value={formData.color}
              onChange={(e) => setFormData({ ...formData, color: e.target.value })}
              maxLength={20}
              placeholder="#007BFF"
            />
            <div style={{ marginTop: '5px', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  width: '30px',
                  height: '30px',
                  backgroundColor: formData.color,
                  border: '1px solid #ccc',
                  borderRadius: '4px'
                }}
              ></div>
              <span style={{ color: formData.color, fontWeight: 'bold' }}>
                {formData.name || 'Предпросмотр'}
              </span>
            </div>
          </div>

          <div className="form-group">
            <label>Порядок сортировки:</label>
            <input
              type="number"
              min="0"
              max="1000"
              value={formData.sort_order}
              onChange={(e) => setFormData({ ...formData, sort_order: e.target.value })}
              required
            />
          </div>

          <div className="form-group checkbox">
            <label>
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              />
              Активно
            </label>
          </div>

          <div className="form-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Отмена
            </button>
            <button type="submit" className="btn-primary">
              Сохранить
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
