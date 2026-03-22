import { useState, useEffect } from 'react';
import Notification from '../components/Notification';
import { useNotification } from '../hooks/useNotification';
import { buildAuthHeaders, getInitData, getTelegramWebApp } from '../utils/telegramAuth';
import { resolveMediaUrl, splitMediaUrls } from '../utils/mediaUrl';

export default function SubmitAdvertisement({ onNavigate }) {
  const [formData, setFormData] = useState({
    title: '',
    content: '',
    media_url: '',
    delete_after_hours: 24,
    channel_id: '',
    tariff_id: null
  });
  const [uploadedImages, setUploadedImages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submittedAd, setSubmittedAd] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [isPaying, setIsPaying] = useState(false);
  const [adTariffs, setAdTariffs] = useState([]);
  const [channels, setChannels] = useState([]);
  const [loadingTariffs, setLoadingTariffs] = useState(false);
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

      fetch(`${import.meta.env.VITE_API_URL}/api/channels`, {
        headers: buildAuthHeaders()
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            setChannels(data.channels);
          }
        })
        .catch(err => console.error('Error loading channels:', err));
    }
  }, []);

  // Загружаем тарифы при выборе канала
  useEffect(() => {
    if (formData.channel_id) {
      loadAdTariffs(formData.channel_id);
    } else {
      setAdTariffs([]);
      setFormData(prev => ({ ...prev, tariff_id: null }));
    }
  }, [formData.channel_id]);

  const loadAdTariffs = async (channelType) => {
    setLoadingTariffs(true);
    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}/api/advertisement-tariffs?channel_type=${channelType}`,
        {
          headers: {
            'ngrok-skip-browser-warning': 'true'
          }
        }
      );
      const data = await response.json();
      if (data.success) {
        setAdTariffs(data.tariffs);
        // Автоматически выбираем первый тариф, если он есть
        if (data.tariffs.length > 0) {
          setFormData(prev => ({ ...prev, tariff_id: data.tariffs[0].id }));
        }
      }
    } catch (err) {
      console.error('Error loading ad tariffs:', err);
    } finally {
      setLoadingTariffs(false);
    }
  };


  const handlePaymentMethod = async (method) => {
    if (!submittedAd || isPaying) return;
    setIsPaying(true);

    try {
      const tg = getTelegramWebApp();
      
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/advertisements/${submittedAd.id}/pay`, {
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
              setShowPaymentModal(false);
              setFormData({
                title: '',
                content: '',
                media_url: '',
                delete_after_hours: 24,
                channel_id: '',
                tariff_id: null
              });
              setSubmittedAd(null);
              
              setTimeout(() => {
                showNotification('💡 Переходим в "Мои рекламы" — там будет статус модерации', 'info');
                setTimeout(() => {
                  onNavigate('my-advertisements');
                }, 2000);
              }, 2000);
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.title || !formData.content) {
      showNotification('❌ Заполните все обязательные поля', 'error');
      return;
    }

    if (!formData.channel_id) {
      showNotification('❌ Выберите канал/группу для размещения', 'error');
      return;
    }

    if (!formData.tariff_id) {
      showNotification('❌ Выберите тариф для размещения', 'error');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/advertisements/submit`, {
        method: 'POST',
        headers: buildAuthHeaders(
          { 'Content-Type': 'application/json' },
          { requireInitData: true }
        ),
        body: JSON.stringify({
          title: formData.title,
          content: formData.content,
          media_url: formData.media_url || null,
          delete_after_hours: parseInt(formData.delete_after_hours),
          channel_id: formData.channel_id,
          tariff_id: formData.tariff_id
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        const errorDetail = data.detail || data.message || 'Ошибка при отправке';
        showNotification(`❌ ${errorDetail}`, 'error');
        console.error('Error response:', data);
        return;
      }
      
      if (data.success) {
        setSubmittedAd(data.advertisement);
        setShowPaymentModal(true);
        showNotification('✅ Реклама создана. Пожалуйста, оплатите размещение.', 'success');
      } else {
        showNotification(`❌ ${data.detail || 'Ошибка при отправке'}`, 'error');
      }
    } catch (err) {
      console.error('Error submitting advertisement:', err);
      showNotification('❌ Ошибка при отправке рекламы. Проверьте подключение к интернету.', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <h1 className="title">📢 Подача рекламы</h1>


      <form onSubmit={handleSubmit} style={{ width: '100%', maxWidth: '600px' }}>
        <div className="channel-card" style={{ flexDirection: 'column', alignItems: 'stretch', marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '10px', fontWeight: '600', color: '#1a1a1a', fontSize: '14px' }}>
            Заголовок рекламы *
          </label>
          <input
            type="text"
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            required
            maxLength={255}
            placeholder="Краткое название вашей рекламы"
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '10px',
              border: '1px solid #e0e0e0',
              fontSize: '15px',
              background: 'rgba(255, 255, 255, 0.9)',
              color: '#1a1a1a'
            }}
          />
        </div>

        <div className="channel-card" style={{ flexDirection: 'column', alignItems: 'stretch', marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '10px', fontWeight: '600', color: '#1a1a1a', fontSize: '14px' }}>
            Текст рекламы *
          </label>
          <textarea
            value={formData.content}
            onChange={(e) => setFormData({ ...formData, content: e.target.value })}
            required
            rows={6}
            placeholder="Опишите ваше предложение, услугу или товар..."
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '10px',
              border: '1px solid #e0e0e0',
              fontSize: '15px',
              fontFamily: 'inherit',
              resize: 'vertical',
              background: 'rgba(255, 255, 255, 0.9)',
              color: '#1a1a1a'
            }}
          />
        </div>

        <div className="channel-card" style={{ flexDirection: 'column', alignItems: 'stretch', marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '10px', fontWeight: '600', color: '#1a1a1a', fontSize: '14px' }}>
            Изображения/фото (опционально)
          </label>
          <input
            type="file"
            accept="image/*"
            multiple
            onChange={async (e) => {
              const files = Array.from(e.target.files);
              if (files.length === 0) return;

              // Проверка общего размера
              const totalSize = files.reduce((sum, file) => sum + file.size, 0);
              if (totalSize > 10 * 1024 * 1024) {
                showNotification('❌ Общий размер файлов больше 10 МБ', 'error');
                e.target.value = '';
                return;
              }

              // Загружаем файлы по очереди
              const uploadedUrls = [];

              for (const file of files) {
                const uploadFormData = new FormData();
                uploadFormData.append('file', file);

                try {
                  showNotification(`⏳ Загрузка ${file.name}...`, 'info');

                  const response = await fetch(`${import.meta.env.VITE_API_URL}/api/upload-image`, {
                    method: 'POST',
                    headers: buildAuthHeaders({}, { requireInitData: true }),
                    body: uploadFormData
                  });

                  const data = await response.json();

                  if (data.success) {
                    uploadedUrls.push(data.url);
                  } else {
                    showNotification(`❌ ${file.name}: ${data.detail || 'Ошибка'}`, 'error');
                  }
                } catch (err) {
                  console.error('Upload error:', err);
                  showNotification(`❌ Ошибка загрузки ${file.name}`, 'error');
                }
              }

              if (uploadedUrls.length > 0) {
                const currentUrls = splitMediaUrls(formData.media_url);
                const allUrls = [...currentUrls, ...uploadedUrls];
                setUploadedImages(allUrls);
                setFormData(prev => ({ ...prev, media_url: allUrls.join(',') }));
                showNotification(`✅ Загружено ${uploadedUrls.length} изображений!`, 'success');
              }

              e.target.value = '';
            }}
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '10px',
              border: '2px dashed #e0e0e0',
              fontSize: '15px',
              background: 'rgba(255, 255, 255, 0.9)',
              color: '#1a1a1a',
              cursor: 'pointer'
            }}
          />
          {uploadedImages.length > 0 && (
            <div style={{ marginTop: '10px', display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
              {uploadedImages.map((url, index) => (
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
                      const newImages = uploadedImages.filter((_, i) => i !== index);
                      setUploadedImages(newImages);
                      setFormData({ ...formData, media_url: newImages.join(',') });
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
          )}
          <small style={{ display: 'block', marginTop: '8px', color: '#666', fontSize: '12px' }}>
            Можно загрузить несколько изображений. Общий размер: макс. 10 МБ
          </small>
        </div>

        <div className="channel-card" style={{ flexDirection: 'column', alignItems: 'stretch', marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '10px', fontWeight: '600', color: '#1a1a1a', fontSize: '14px' }}>
            Канал/Группа для размещения *
          </label>
          <select
            value={formData.channel_id}
            onChange={(e) => setFormData({ ...formData, channel_id: e.target.value })}
            required
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '10px',
              border: '1px solid #e0e0e0',
              fontSize: '15px',
              background: 'rgba(255, 255, 255, 0.9)',
              color: '#1a1a1a'
            }}
          >
            <option value="">Выберите канал/группу</option>
            {channels.map((channel) => (
              <option key={channel.id} value={channel.id}>
                {channel.icon || (channel.type === 'channel' ? '📢' : '👥')} {channel.name}
              </option>
            ))}
          </select>
        </div>

        {/* Тарифы рекламы */}
        {formData.channel_id && (
          <div className="channel-card" style={{ flexDirection: 'column', alignItems: 'stretch', marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '15px', fontWeight: '600', color: '#1a1a1a', fontSize: '14px' }}>
              Выберите тариф *
            </label>
            {loadingTariffs ? (
              <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
                Загрузка тарифов...
              </div>
            ) : adTariffs.length === 0 ? (
              <div style={{ padding: '20px', textAlign: 'center', color: '#f44336', background: '#ffebee', borderRadius: '10px' }}>
                ⚠️ Нет доступных тарифов для этого канала. Обратитесь к администратору.
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: adTariffs.length === 1 ? '1fr' : 'repeat(auto-fit, minmax(250px, 1fr))', gap: '12px' }}>
                {adTariffs.map(tariff => (
                  <div
                    key={tariff.id}
                    onClick={() => setFormData({ ...formData, tariff_id: tariff.id })}
                    style={{
                      position: 'relative',
                      padding: '18px',
                      border: formData.tariff_id === tariff.id ? '2px solid #007BFF' : '2px solid #e0e0e0',
                      borderRadius: '12px',
                      cursor: 'pointer',
                      background: formData.tariff_id === tariff.id
                        ? 'linear-gradient(135deg, rgba(0, 123, 255, 0.15) 0%, rgba(0, 123, 255, 0.05) 100%)'
                        : 'linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(245, 247, 250, 0.95) 100%)',
                      transition: 'all 0.3s ease',
                      boxShadow: formData.tariff_id === tariff.id
                        ? '0 4px 12px rgba(0, 123, 255, 0.2)'
                        : '0 2px 8px rgba(0, 0, 0, 0.05)',
                      transform: formData.tariff_id === tariff.id ? 'translateY(-2px)' : 'translateY(0)',
                    }}
                    onMouseEnter={(e) => {
                      if (formData.tariff_id !== tariff.id) {
                        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.1)';
                        e.currentTarget.style.transform = 'translateY(-1px)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (formData.tariff_id !== tariff.id) {
                        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.05)';
                        e.currentTarget.style.transform = 'translateY(0)';
                      }
                    }}
                  >
                    {formData.tariff_id === tariff.id && (
                      <div style={{
                        position: 'absolute',
                        top: '12px',
                        right: '12px',
                        background: '#007BFF',
                        color: 'white',
                        borderRadius: '50%',
                        width: '24px',
                        height: '24px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '14px',
                        fontWeight: 'bold'
                      }}>
                        ✓
                      </div>
                    )}

                    <div style={{ marginBottom: '12px' }}>
                      <div style={{
                        fontWeight: '700',
                        fontSize: '17px',
                        color: '#1a1a1a',
                        marginBottom: '10px',
                        lineHeight: '1.3'
                      }}>
                        {tariff.name}
                      </div>
                      <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                        marginBottom: '10px'
                      }}>
                        {tariff.price_usd && (
                          <div style={{
                            display: 'flex',
                            alignItems: 'baseline',
                            gap: '4px'
                          }}>
                            <span style={{
                              fontSize: '24px',
                              fontWeight: '800',
                              color: '#28a745',
                              lineHeight: '1'
                            }}>
                              ${tariff.price_usd}
                            </span>
                            <span style={{
                              fontSize: '12px',
                              color: '#999',
                              fontWeight: '500'
                            }}>
                              USD
                            </span>
                          </div>
                        )}
                        {tariff.price_stars && (
                          <div style={{
                            display: 'flex',
                            alignItems: 'baseline',
                            gap: '4px'
                          }}>
                            <span style={{
                              fontSize: '18px',
                              fontWeight: '700',
                              color: '#FFD700',
                              lineHeight: '1'
                            }}>
                              ⭐ {tariff.price_stars}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>

                    {tariff.description && (
                      <div style={{
                        fontSize: '13px',
                        color: '#555',
                        marginBottom: '12px',
                        lineHeight: '1.5',
                        minHeight: '40px'
                      }}>
                        {tariff.description}
                      </div>
                    )}

                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '8px 12px',
                      background: 'rgba(0, 123, 255, 0.08)',
                      borderRadius: '8px',
                      fontSize: '13px',
                      color: '#007BFF',
                      fontWeight: '600'
                    }}>
                      <span style={{ fontSize: '16px' }}>⏱️</span>
                      <span>
                        {tariff.duration_hours < 24
                          ? `${tariff.duration_hours} ч`
                          : tariff.duration_hours === 24
                            ? '1 день'
                            : `${Math.floor(tariff.duration_hours / 24)} дн.`
                        }
                      </span>
                    </div>

                    {tariff.thread_id && (
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '8px 12px',
                        background: 'rgba(40, 167, 69, 0.08)',
                        borderRadius: '8px',
                        fontSize: '13px',
                        color: '#2e7d32',
                        fontWeight: '600',
                        marginTop: '8px'
                      }}>
                        <span style={{ fontSize: '16px' }}>🧵</span>
                        <span>Публикация в Topic #{tariff.thread_id}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}


        <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
          <button
            type="submit"
            disabled={loading}
            className="buy-btn"
            style={{ flex: 1 }}
          >
            {loading ? 'Создание...' : '📤 Создать и оплатить'}
          </button>
          <button
            type="button"
            onClick={() => onNavigate('channels')}
            className="back-btn"
            style={{ padding: '12px 20px' }}
          >
            Отмена
          </button>
        </div>
      </form>

      {showPaymentModal && submittedAd && (
        <div 
          className="modal-overlay" 
          onClick={() => setShowPaymentModal(false)}
        >
          <div 
            className="modal-content" 
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '450px' }}
          >
            <h2 className="modal-title" style={{ marginBottom: '20px' }}>💳 Оплата рекламы</h2>

            <div className="modal-tariff-info" style={{
              background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
              padding: '20px',
              borderRadius: '12px',
              marginBottom: '20px'
            }}>
              <div style={{
                fontSize: '16px',
                fontWeight: '600',
                color: '#1a1a1a',
                marginBottom: '8px',
                lineHeight: '1.4'
              }}>
                {submittedAd.title}
              </div>

              {submittedAd.tariff_name && (
                <div style={{
                  fontSize: '13px',
                  color: '#666',
                  marginBottom: '12px',
                  padding: '6px 12px',
                  background: 'rgba(255, 255, 255, 0.7)',
                  borderRadius: '6px',
                  display: 'inline-block'
                }}>
                  📊 Тариф: {submittedAd.tariff_name}
                </div>
              )}

              <div style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                marginTop: '15px',
                marginBottom: '12px'
              }}>
                {submittedAd.price_usd && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    gap: '8px'
                  }}>
                    <div style={{
                      fontSize: '32px',
                      fontWeight: 'bold',
                      color: '#28a745',
                      lineHeight: '1'
                    }}>
                      ${submittedAd.price_usd}
                    </div>
                    <div style={{ fontSize: '14px', color: '#666' }}>
                      USD
                    </div>
                  </div>
                )}
                {submittedAd.price_stars && (
                  <div style={{
                    padding: '8px 14px',
                    background: 'rgba(255, 215, 0, 0.15)',
                    borderRadius: '8px',
                    fontSize: '16px',
                    color: '#FFD700',
                    fontWeight: '700',
                    display: 'inline-block',
                    width: 'fit-content'
                  }}>
                    ⭐ {submittedAd.price_stars} Stars
                  </div>
                )}
              </div>

              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '10px 14px',
                background: 'rgba(0, 123, 255, 0.1)',
                borderRadius: '8px',
                fontSize: '13px',
                color: '#007BFF',
                fontWeight: '600',
                marginBottom: '12px'
              }}>
                <span style={{ fontSize: '16px' }}>⏱️</span>
                <span>
                  Длительность: {submittedAd.duration_hours < 24
                    ? `${submittedAd.duration_hours} ч`
                    : submittedAd.duration_hours === 24
                      ? '1 день'
                      : `${Math.floor(submittedAd.duration_hours / 24)} дн.`
                  }
                </span>
              </div>

              <p style={{
                fontSize: '13px',
                color: '#555',
                margin: '0',
                lineHeight: '1.5'
              }}>
                ℹ️ После оплаты реклама отправляется на модерацию и публикуется после одобрения.
              </p>
            </div>

            <div className="payment-methods">
              <button
                onClick={() => handlePaymentMethod('stars')}
                className="payment-method-btn stars-btn"
                disabled={isPaying}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  border: '2px solid #FFD700',
                  background: 'linear-gradient(135deg, #FFF8DC 0%, #FFE4B5 100%)',
                  transition: 'all 0.3s ease'
                }}
              >
                <div className="payment-icon" style={{ fontSize: '28px' }}>⭐</div>
                <div className="payment-name" style={{ fontSize: '15px', fontWeight: '600', color: '#1a1a1a' }}>
                  Telegram Stars
                </div>
              </button>

              <button
                onClick={() => handlePaymentMethod('stripe')}
                className="payment-method-btn stripe-btn"
                disabled={isPaying}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  border: '2px solid #635BFF',
                  background: 'linear-gradient(135deg, #F0EFFF 0%, #E6E4FF 100%)',
                  transition: 'all 0.3s ease'
                }}
              >
                <div className="payment-icon" style={{ fontSize: '28px' }}>💳</div>
                <div className="payment-name" style={{ fontSize: '15px', fontWeight: '600', color: '#1a1a1a' }}>
                  Банковская карта
                </div>
              </button>
            </div>

            <button
              onClick={() => setShowPaymentModal(false)}
              className="modal-close-btn"
              style={{
                marginTop: '15px',
                padding: '12px',
                width: '100%',
                borderRadius: '10px',
                border: '1px solid #ddd',
                background: '#f5f5f5',
                color: '#666',
                fontSize: '14px',
                fontWeight: '500',
                cursor: 'pointer'
              }}
            >
              Отмена
            </button>
          </div>
        </div>
      )}

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
