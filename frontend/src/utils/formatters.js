// ==========================================
// FORMATTERS & STATUS HELPERS
// ==========================================

export const STATUS_CONFIG = {
  NORMAL: {
    label: 'Normal Location',
    badgeClass: 'badge-success',
    severity: 'info',
    isAnomaly: false,
    description: 'Asset verified in designated storage zone',
  },
  MISPLACED: {
    label: 'Misplaced Asset',
    badgeClass: 'badge-warning',
    severity: 'warning',
    isAnomaly: true,
    description: 'Asset observed in an unexpected internal zone',
  },
  AUTHORIZED_EXIT: {
    label: 'Authorized Exit',
    badgeClass: 'badge-info',
    severity: 'info',
    isAnomaly: false,
    description: 'Asset at main gate with valid permit',
  },
  UNAUTHORIZED_EXIT: {
    label: 'Unauthorized Exit',
    badgeClass: 'badge-danger',
    severity: 'critical',
    isAnomaly: true,
    description: 'Security Alert: Asset at gate without permission',
  },
  UNKNOWN_ASSET: {
    label: 'Unknown Asset ID',
    badgeClass: 'badge-purple',
    severity: 'warning',
    isAnomaly: true,
    description: 'Unregistered RFID/tag detected',
  },
  MISSING_INVESTIGATION_REQUIRED: {
    label: 'Audit Investigation',
    badgeClass: 'badge-orange',
    severity: 'high',
    isAnomaly: true,
    description: 'Expected asset not found during audit',
  },
  INVALID_EVENT: {
    label: 'Invalid Event',
    badgeClass: 'badge-secondary',
    severity: 'warning',
    isAnomaly: true,
    description: 'Malformed payload or invalid zone',
  },
};

export const formatTimestamp = (isoString) => {
  if (!isoString) return '—';
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;

    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
      timeZone: 'UTC',
    }).format(date) + ' UTC';
  } catch {
    return String(isoString);
  }
};

export const getStatusMeta = (status) => {
  return (
    STATUS_CONFIG[status] || {
      label: status || 'Unknown',
      badgeClass: 'badge-secondary',
      severity: 'info',
      isAnomaly: false,
      description: '',
    }
  );
};
