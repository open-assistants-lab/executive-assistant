import 'dart:async';
import 'dart:io';

enum BackendStatus { starting, running, crashed, stopped }

class BackendService {
  final String _host;
  final Duration _pollInterval;
  Timer? _pollTimer;
  bool _stopped = false;

  final _statusController = StreamController<BackendStatus>.broadcast();
  final _healthController = StreamController<bool>.broadcast();

  BackendService({
    String host = '127.0.0.1:8080',
    Duration pollInterval = const Duration(milliseconds: 500),
  }) : _host = host,
       _pollInterval = pollInterval;

  Stream<BackendStatus> get status => _statusController.stream;
  Stream<bool> get health => _healthController.stream;
  BackendStatus get currentStatus => _currentStatus;
  BackendStatus _currentStatus = BackendStatus.stopped;
  bool get isRunning => _currentStatus == BackendStatus.running;

  Future<void> start() async {
    if (_pollTimer != null) return;
    _stopped = false;
    _currentStatus = BackendStatus.starting;
    _statusController.add(BackendStatus.starting);

    _pollTimer = Timer.periodic(_pollInterval, (_) => _checkHealth());
    // Do an immediate first check
    await _checkHealth();
  }

  Future<void> stop() async {
    _stopped = true;
    _pollTimer?.cancel();
    _pollTimer = null;
    _currentStatus = BackendStatus.stopped;
    _statusController.add(BackendStatus.stopped);
  }

  Future<void> _checkHealth() async {
    if (_stopped) return;
    try {
      final client = HttpClient();
      client.connectionTimeout = const Duration(seconds: 2);
      final request = await client.getUrl(Uri.parse('http://$_host/health'));
      final response = await request.close();
      client.close();

      if (_stopped) return;

      if (response.statusCode == 200) {
        if (_currentStatus != BackendStatus.running) {
          _currentStatus = BackendStatus.running;
          _statusController.add(BackendStatus.running);
        }
        _healthController.add(true);
      }
    } catch (_) {
      if (_stopped) return;
      if (_currentStatus == BackendStatus.running) {
        _currentStatus = BackendStatus.crashed;
        _statusController.add(BackendStatus.crashed);
      }
      _healthController.add(false);
    }
  }

  void dispose() {
    _stopped = true;
    _pollTimer?.cancel();
    _statusController.close();
    _healthController.close();
  }
}
