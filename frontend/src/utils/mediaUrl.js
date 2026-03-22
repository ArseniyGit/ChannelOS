export function splitMediaUrls(mediaUrl) {
  if (!mediaUrl) {
    return [];
  }
  return String(mediaUrl)
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export function resolveMediaUrl(value) {
  const raw = (value || '').trim();
  if (!raw) {
    return '';
  }
  if (/^https?:\/\//i.test(raw)) {
    return raw;
  }
  if (raw.startsWith('/')) {
    return `${import.meta.env.VITE_API_URL}${raw}`;
  }
  return raw;
}

export function firstResolvedMediaUrl(mediaUrl) {
  const first = splitMediaUrls(mediaUrl)[0];
  return resolveMediaUrl(first);
}

