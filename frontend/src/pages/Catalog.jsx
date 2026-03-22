import { useEffect, useState } from 'react';
import PrivacyButton from '../components/PrivacyButton';
import { buildAuthHeaders, getInitData } from '../utils/telegramAuth';

export default function Catalog({ onNavigate }) {
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [currentUser, setCurrentUser] = useState(null);

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
    }

    fetch(`${import.meta.env.VITE_API_URL}/api/companies`, {
      headers: buildAuthHeaders()
    })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setCompanies(data.companies);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error('Error loading companies:', err);
        setLoading(false);
      });
  }, []);

  const categories = [...new Set(companies.map(c => c.category))];

  const filteredCompanies = companies.filter(company => {
    const matchesSearch = company.name.toLowerCase().includes(search.toLowerCase()) ||
                         company.description?.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = !selectedCategory || company.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  if (loading) {
    return (
      <div className="page">
        <h1 className="title">Загрузка...</h1>
      </div>
    );
  }

  return (
    <div className="page">
      <h1 className="title">Справочный каталог</h1>

      {}
      <input
        type="text"
        placeholder="🔍 Поиск компаний..."
        className="search-input"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {}
      <div className="categories-filter">
        <button
          className={`category-chip ${!selectedCategory ? 'active' : ''}`}
          onClick={() => setSelectedCategory('')}
        >
          Все
        </button>
        {categories.map(cat => (
          <button
            key={cat}
            className={`category-chip ${selectedCategory === cat ? 'active' : ''}`}
            onClick={() => setSelectedCategory(cat)}
          >
            {cat}
          </button>
        ))}
      </div>

      {}
      <div className="companies-list">
        {filteredCompanies.length > 0 ? (
          filteredCompanies.map((company) => (
            <div key={company.id} className="company-card">
              <div className="company-icon">{company.icon_emoji}</div>
              <div className="company-info">
                <h3>{company.name}</h3>
                <div className="company-category">{company.category}</div>
                {company.description && (
                  <p className="company-description">{company.description}</p>
                )}
                {company.phone && (
                  <a href={`tel:${company.phone}`} className="company-phone">
                    📞 {company.phone}
                  </a>
                )}
                {company.address && (
                  <div className="company-address">📍 {company.address}</div>
                )}
              </div>
            </div>
          ))
        ) : (
          <div style={{ textAlign: 'center', padding: '40px', color: 'white' }}>
            🔍 Ничего не найдено
          </div>
        )}
      </div>
      {/* Кнопка политики конфиденциальности */}
      <PrivacyButton />


      {/* Нижнее меню навигации */}
      <div className="bottom-nav">
        <button className="nav-btn" onClick={() => onNavigate('channels')}>
          <span>📢</span>
          <span>Каналы</span>
        </button>
        <button className="nav-btn active" onClick={() => onNavigate('catalog')}>
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
    </div>
  );
}
