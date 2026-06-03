import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../../theme/app_theme.dart';

// ── Provider ──────────────────────────────────────────────────

class CanvasSurface {
  final String surfaceId;
  final String action;
  final String html;
  const CanvasSurface({required this.surfaceId, required this.action, required this.html});
}

class CanvasState {
  final List<CanvasSurface> surfaces;
  final String? lastAction;
  const CanvasState({this.surfaces = const [], this.lastAction});
}

class CanvasProvider extends StateNotifier<CanvasState> {
  CanvasProvider() : super(const CanvasState());

  void onCanvasUpdate(Map<String, dynamic> event) {
    final action = event['action'] as String;
    var surfaces = List<CanvasSurface>.from(state.surfaces);
    final surfaceId = event['surface_id'] as String;

    if (action == 'destroy') {
      surfaces.removeWhere((s) => s.surfaceId == surfaceId);
    } else if (action == 'update') {
      final idx = surfaces.indexWhere((s) => s.surfaceId == surfaceId);
      if (idx >= 0) {
        surfaces[idx] = CanvasSurface(
          surfaceId: surfaceId,
          action: action,
          html: event['html'] as String? ?? '',
        );
      }
    } else {
      surfaces.add(CanvasSurface(
        surfaceId: surfaceId,
        action: action,
        html: event['html'] as String? ?? '',
      ));
    }

    state = CanvasState(surfaces: surfaces, lastAction: action);
  }
}

final canvasProvider = StateNotifierProvider<CanvasProvider, CanvasState>(
  (ref) => CanvasProvider(),
);

// ── Widget ────────────────────────────────────────────────────

class CanvasTab extends ConsumerStatefulWidget {
  const CanvasTab({super.key});

  @override
  ConsumerState<CanvasTab> createState() => _CanvasTabState();
}

class _CanvasTabState extends ConsumerState<CanvasTab> {
  @override
  Widget build(BuildContext context) {
    final state = ref.watch(canvasProvider);

    if (state.surfaces.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Symbols.dashboard,
              size: 48,
              color: context.tokens.colors.textTertiary,
            ),
            const SizedBox(height: 16),
            Text(
              'Agent-generated content appears here',
              style: context.tokens.typography.textTheme.bodySmall,
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      itemCount: state.surfaces.length,
      itemBuilder: (_, i) {
        final surface = state.surfaces[i];
        return SizedBox(
          height: 400,
          child: WebViewWidget(
            controller: WebViewController()
              ..setJavaScriptMode(JavaScriptMode.unrestricted)
              ..loadHtmlString('''
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --primary: #3b82f6;
      --bg: #1e1e2e;
      --text: #cdd6f4;
      --border: #45475a;
    }
    body {
      margin: 0; padding: 16px;
      font-family: system-ui, -apple-system, sans-serif;
      color: var(--text);
      background: var(--bg);
    }
    input, textarea, select {
      background: #313244;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px;
      font-size: 14px;
      width: 100%;
      margin-bottom: 8px;
    }
    button {
      background: var(--primary);
      color: white;
      border: none;
      border-radius: 6px;
      padding: 10px 16px;
      cursor: pointer;
    }
    h2 { margin-top: 0; }
  </style>
</head>
<body>
  ${surface.html}
</body>
</html>
            '''),
          ),
        );
      },
    );
  }
}
