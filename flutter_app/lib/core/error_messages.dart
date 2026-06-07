const _humanReadable = <String, String>{
  'Backend crashed': 'Something went wrong. Tap to reconnect.',
  'Connection lost': 'Connection was interrupted. Tap to reconnect.',
  'Connection refused': 'Could not reach the backend. Try restarting the app.',
  'Failed to connect': 'Could not reach the backend. Try restarting the app.',
  '401': 'Your API key is invalid. Go to Settings to update it.',
  'Unauthorized': 'Your API key is invalid. Go to Settings to update it.',
  '402': 'Your API provider account needs a payment method. Check your billing.',
  '429': 'You\'re sending too many requests. Waiting a moment…',
  'Rate limit': 'You\'re sending too many requests. Waiting a moment…',
  'timeout': 'The request timed out. Check your internet connection.',
  'timed out': 'The request timed out. Check your internet connection.',
  'SocketException': 'Could not reach the server. Check your internet.',
  'HttpException': 'Could not reach the server. Check your internet.',
};

String humanReadableError(String raw) {
  for (final entry in _humanReadable.entries) {
    if (raw.contains(entry.key)) {
      return entry.value;
    }
  }
  return raw;
}
